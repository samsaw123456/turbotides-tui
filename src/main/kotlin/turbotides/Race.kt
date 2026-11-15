package turbotides

import kotlin.math.*

enum class Phase { GARAGE, COUNTDOWN, RACING, PAUSED, FINISHED }
enum class Difficulty(val title: String, val pace: Float) { CRUISE("Cruise", 0.91f), RACE("Race", 1f) }

data class Controls(
    val throttle: Boolean = false,
    val brake: Boolean = false,
    val steer: Float = 0f,
    val drift: Boolean = false,
    val boost: Boolean = false,
)

class Racer(val name: String, val paint: Int, var distance: Float, var lane: Float) {
    var speed = 0f
    var lateralSpeed = 0f
    var finishTime: Float? = null
}

class Race(val track: Track, val difficulty: Difficulty = Difficulty.CRUISE, paint: Int = 0) {
    companion object {
        const val STEP = 1f / 120f
        const val LAPS = 3
        const val MAX_SPEED = 62f
    }

    val player = Racer("You", paint, 0f, -3f)
    val rivals = listOf("Phippy", "Goldie", "Hazel", "Kube", "Zee").mapIndexed { i, name ->
        Racer(name, (i + 1) % 5, 7f + i / 2 * 7f, if (i % 2 == 0) 3f else -3f)
    }
    var phase = Phase.GARAGE
        private set
    private var beforePause = Phase.RACING
    var countdown = 3.4f
        private set
    var elapsed = 0f
        private set
    var nitro = 65f
        private set
    var drifting = false
        private set
    var boosting = false
        private set
    var driftCharge = 0f
        private set
    var message = ""
        private set
    var messageTime = 0f
        private set
    var bumps = 0
        private set
    var pads = 0
        private set
    var driftBonuses = 0
        private set
    var bestLap: Float? = null
        private set
    private var lapStart = 0f
    private var completedLaps = 0
    private var contactCooldown = 0f
    private val padLap = IntArray(3) { -1 }
    private var padBoost = 0f
    private var accumulator = 0f
    val lap get() = (floor(player.distance / track.length).toInt() + 1).coerceIn(1, LAPS)
    val order get() = (rivals + player).sortedWith(compareBy<Racer> { it.finishTime ?: Float.MAX_VALUE }.thenByDescending { it.distance })
    val position get() = order.indexOf(player) + 1

    fun start() {
        if (phase == Phase.GARAGE) phase = Phase.COUNTDOWN
    }

    fun pause() {
        if (phase == Phase.COUNTDOWN || phase == Phase.RACING) {
            beforePause = phase
            phase = Phase.PAUSED
            accumulator = 0f
            boosting = false
        }
    }

    fun resume() {
        if (phase == Phase.PAUSED) phase = beforePause
    }

    fun advance(delta: Float, controls: Controls) {
        if (phase != Phase.COUNTDOWN && phase != Phase.RACING) return
        // A stalled window must not fast-forward the race or tunnel through cars.
        accumulator += delta.coerceIn(0f, 0.1f)
        while (accumulator >= STEP) {
            tick(controls)
            accumulator -= STEP
        }
    }

    private fun tick(controls: Controls) {
        if (phase == Phase.COUNTDOWN) {
            countdown -= STEP
            if (countdown <= 0f) {
                phase = Phase.RACING
                say("GO!", 1.4f)
            }
            return
        }
        if (phase != Phase.RACING) return
        elapsed += STEP
        messageTime = (messageTime - STEP).coerceAtLeast(0f)
        contactCooldown -= STEP
        padBoost -= STEP
        updatePlayer(controls)
        rivals.forEachIndexed { index, rival -> updateRival(rival, index) }
        resolveContacts()
        val laps = floor(player.distance / track.length).toInt()
        if (laps > completedLaps) {
            val time = elapsed - lapStart
            bestLap = min(bestLap ?: Float.MAX_VALUE, time)
            lapStart = elapsed
            completedLaps = laps
            if (laps < LAPS) say(if (laps == LAPS - 1) "Final lap!" else "Lap ${laps + 1}")
        }
        if (player.distance >= track.length * LAPS) {
            player.finishTime = elapsed
            boosting = false
            drifting = false
            phase = Phase.FINISHED
            accumulator = 0f
        }
    }

    private fun updatePlayer(input: Controls) {
        val offroad = abs(player.lane) > track.roadHalfWidth
        val wasDrifting = drifting
        drifting = input.drift && abs(input.steer) > 0.1f && player.speed > 22f && !offroad
        boosting = input.boost && nitro > 0.5f && input.throttle && !input.brake && !offroad
        val topSpeed = when {
            offroad -> 28f
            boosting || padBoost > 0 -> 87f
            drifting -> 57f
            else -> MAX_SPEED
        }
        val acceleration = when {
            input.brake -> -46f
            input.throttle -> if (boosting || padBoost > 0) 40f else 23f
            else -> -10f
        }
        if (player.speed < topSpeed || acceleration < 0f) {
            player.speed = (player.speed + acceleration * STEP).coerceAtLeast(0f)
            if (acceleration > 0f) player.speed = min(player.speed, topSpeed)
        }
        if (player.speed > topSpeed) player.speed = max(topSpeed, player.speed - 34f * STEP)
        if (boosting) nitro = max(0f, nitro - 26f * STEP) else nitro = min(100f, nitro + 3f * STEP)
        if (drifting) driftCharge += STEP
        if (wasDrifting && !drifting) {
            if (driftCharge >= 0.45f) {
                nitro = min(100f, nitro + 12f + min(driftCharge, 3f) * 10f)
                driftBonuses++
                say("Drift bonus +nitro", 1.1f)
            }
            driftCharge = 0f
        }
        val steering = input.steer.coerceIn(-1f, 1f) * (if (drifting) 14f else 11f) * (player.speed / 28f).coerceIn(0f, 1f)
        val cornerForce = cornerForce()
        val targetLateral = steering + cornerForce
        player.lateralSpeed += (targetLateral - player.lateralSpeed) * min(1f, STEP * if (drifting) 3f else 8f)
        player.lane += player.lateralSpeed * STEP
        if (abs(player.lane) > track.barrier - 1f) {
            player.lane = player.lane.coerceIn(-track.barrier + 1f, track.barrier - 1f)
            player.lateralSpeed *= -0.4f
            if (contactCooldown <= 0f) {
                player.speed *= 0.65f
                bumps++
                contactCooldown = 0.7f
                say("Barrier bump - keep going!", 1f)
            }
        }
        player.distance += player.speed * STEP
        for (i in 0..2) {
            val currentLap = floor(player.distance / track.length).toInt()
            if (player.speed > 1f &&
                padLap[i] != currentLap &&
                abs(track.relativeDistance(player.distance, track.padDistance(i))) < 3f &&
                abs(player.lane - track.padLane(i)) < 2.2f
            ) {
                padBoost = 1.6f
                padLap[i] = currentLap
                nitro = min(100f, nitro + 16f)
                pads++
                say("Turbo pad!", 1f)
            }
        }
    }

    // Keep full steering effective even in the sharpest bend while boosting.
    fun cornerForce(): Float = (track.curvature(player.distance) * player.speed * player.speed * 0.065f).coerceIn(-4.5f, 4.5f)

    private fun updateRival(rival: Racer, index: Int) {
        if (rival.finishTime != null) return
        val bend = abs(track.curvature(rival.distance))
        val pace = (54.5f + index * 1.4f) * difficulty.pace
        val target = (pace - bend * 190f).coerceAtLeast(34f) + if (sin(elapsed * 0.65f + index * 2f) > 0.85f) 11f else 0f
        rival.speed += (target - rival.speed) * STEP * 0.8f
        val preferredLane = (if (index % 2 == 0) 3.8f else -3.8f) + sin(elapsed * 0.4f + index) * 1.1f
        rival.lane += (preferredLane - rival.lane) * STEP
        rival.distance += rival.speed * STEP
        if (rival.distance >= track.length * LAPS) rival.finishTime = elapsed
    }

    private fun resolveContacts() {
        if (contactCooldown > 0f) return
        for (rival in rivals) {
            if (rival.finishTime != null) continue
            if (abs(track.relativeDistance(rival.distance, player.distance)) < 3.5f && abs(rival.lane - player.lane) < 2f) {
                player.speed *= 0.8f
                player.lateralSpeed += if (player.lane < rival.lane) -5f else 5f
                contactCooldown = 0.8f
                bumps++
                say("Trading paint!", 0.8f)
                break
            }
        }
    }

    private fun say(text: String, duration: Float = 1.8f) {
        message = text
        messageTime = duration
    }
}
