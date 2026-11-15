package turbotides

import kotlin.math.*
import kotlin.test.*

class RaceTest {
    @Test fun `nitro and pad acceleration cannot exceed top speed`() {
        val race = racing()
        repeat(60 * 120) {
            race.advance(Race.STEP, autopilot(race))
            assertTrue(race.player.speed <= 87f, "Boost speed exceeded its limit: ${race.player.speed}")
        }
    }

    private fun runFor(race: Race, seconds: Float, input: Controls = Controls()) {
        repeat((seconds * 120).roundToInt()) { race.advance(Race.STEP, input) }
    }

    private fun racing(circuit: Circuit = Circuit.SUNSET, difficulty: Difficulty = Difficulty.EASY): Race = Race(Track(circuit), difficulty).also {
        it.start()
        runFor(it, 3.5f)
    }

    private fun autopilot(race: Race): Controls {
        val corner = race.cornerForce()
        return Controls(throttle = true, steer = ((-race.player.lane * 3f - corner) / 11f).coerceIn(-1f, 1f), boost = true)
    }

    @Test fun `countdown blocks driving and starts one race`() {
        val race = Race(Track(Circuit.SUNSET))
        race.start()
        runFor(race, 2f, Controls(throttle = true))
        assertEquals(Phase.COUNTDOWN, race.phase)
        assertEquals(0f, race.player.distance)
        assertEquals(0f, race.elapsed)
        runFor(race, 2f, Controls(throttle = true))
        assertEquals(Phase.RACING, race.phase)
        assertTrue(race.player.distance > 0)
        val distance = race.player.distance
        race.start()
        assertEquals(distance, race.player.distance)
    }

    @Test fun `pause freezes cars time and countdown and resumes exactly`() {
        val race = racing()
        runFor(race, 6f, Controls(throttle = true))
        race.pause()
        val snapshot = listOf(race.elapsed, race.player.distance, race.nitro, race.rivals.first().distance)
        runFor(race, 5f, Controls(throttle = true, boost = true))
        assertEquals(snapshot, listOf(race.elapsed, race.player.distance, race.nitro, race.rivals.first().distance))
        race.resume()
        runFor(race, 0.5f, Controls(throttle = true))
        assertTrue(race.player.distance > snapshot[1])
        val countdownRace = Race(Track(Circuit.CINDER))
        countdownRace.start()
        countdownRace.pause()
        runFor(countdownRace, 8f)
        assertEquals(3.4f, countdownRace.countdown)
        countdownRace.resume()
        assertEquals(Phase.COUNTDOWN, countdownRace.phase)
    }

    @Test fun `physics agrees at 30 and 144 fps`() {
        fun simulate(hz: Int): Race {
            val race = Race(Track(Circuit.SUNSET))
            race.start()
            repeat(hz * 20) { race.advance(1f / hz, Controls(throttle = true)) }
            return race
        }
        val slow = simulate(30)
        val fast = simulate(144)
        assertEquals(slow.player.distance, fast.player.distance, 0.75f)
        assertEquals(slow.player.lane, fast.player.lane, 0.1f)
        assertEquals(slow.elapsed, fast.elapsed, 0.02f)
    }

    @Test fun `braking stops without reversing and grass slows car`() {
        val race = racing()
        repeat(600) { race.advance(Race.STEP, autopilot(race)) }
        assertTrue(race.player.speed > 60)
        race.player.lane = 10.5f
        runFor(race, 2f, Controls(throttle = true))
        assertTrue(race.player.speed <= 29)
        runFor(race, 4f, Controls(brake = true))
        assertEquals(0f, race.player.speed)
    }

    @Test fun `barriers and car contact are recoverable with bounded hit rate`() {
        val race = racing()
        runFor(race, 8f, Controls(throttle = true, steer = 1f))
        assertTrue(race.bumps > 0)
        assertTrue(abs(race.player.lane) <= race.track.barrier - 1)
        assertTrue(race.bumps < 15)
        repeat(400) { race.advance(Race.STEP, autopilot(race)) }
        assertTrue(abs(race.player.lane) < 4)
        val contact = racing()
        contact.rivals.first().distance = contact.player.distance
        contact.rivals.first().lane = contact.player.lane
        runFor(contact, 0.1f)
        assertEquals(1, contact.bumps)
    }

    @Test fun `drift earns nitro only after moving drift is released`() {
        val race = racing()
        runFor(race, 1f, Controls(drift = true, steer = 1f))
        assertEquals(0, race.driftBonuses)
        repeat(480) { race.advance(Race.STEP, autopilot(race)) }
        race.player.lane = -4f
        runFor(race, 0.6f, Controls(throttle = true, steer = 1f, drift = true))
        assertTrue(race.drifting)
        val before = race.nitro
        race.advance(Race.STEP, Controls(throttle = true))
        assertEquals(1, race.driftBonuses)
        assertTrue(race.nitro > before + 10f)
    }

    @Test fun `turbo pads trigger once per pass and boost consumes fuel`() {
        val race = racing()
        race.player.distance = race.track.padDistance(0) - 2f
        race.player.lane = race.track.padLane(0)
        race.player.speed = 10f
        runFor(race, 0.5f)
        assertEquals(1, race.pads)
        val fuel = race.nitro
        runFor(race, 1f, Controls(throttle = true, boost = true))
        assertTrue(race.nitro < fuel)
        assertTrue(race.nitro >= 0)
    }

    @Test fun `every circuit and difficulty can finish three laps and freeze the result`() {
        for (circuit in Circuit.entries) {
            for (difficulty in Difficulty.entries) {
                val race = racing(circuit, difficulty)
                repeat(180 * 120) {
                    if (race.phase == Phase.RACING) race.advance(Race.STEP, autopilot(race))
                }
                assertEquals(Phase.FINISHED, race.phase, circuit.title)
                assertEquals(3, race.lap)
                assertTrue(race.position in 1..6, circuit.title)
                if (difficulty == Difficulty.EASY) assertEquals(1, race.position, "Easy must be approachable on ${circuit.title}")
                assertTrue(race.bestLap!! > 10)
                assertEquals(race.elapsed, race.player.finishTime)
                val time = race.elapsed
                runFor(race, 5f, Controls(throttle = true))
                assertEquals(time, race.elapsed)
            }
        }
    }

    @Test fun `left and right steer in the requested direction through every bend even with nitro`() {
        for (circuit in Circuit.entries) {
            for (direction in listOf(-1f, 1f)) {
                repeat(32) { sample ->
                    val race = racing(circuit)
                    race.player.distance = race.track.length * sample / 32f
                    race.player.lane = 0f
                    race.player.speed = 80f
                    race.rivals.forEach { it.finishTime = 1f }
                    runFor(race, 0.4f, Controls(throttle = true, steer = direction, boost = true))
                    assertTrue(race.player.lane * direction > 1f, "$circuit steering $direction failed at $sample")
                }
            }
        }
    }

    @Test fun `stopped steering cannot move the car and brake wins over throttle`() {
        val race = racing()
        runFor(race, 3f, Controls(steer = 1f, drift = true, boost = true))
        assertEquals(-3f, race.player.lane)
        assertEquals(0f, race.player.distance)
        assertFalse(race.boosting)
        race.player.speed = 60f
        runFor(race, 2f, Controls(throttle = true, brake = true, boost = true))
        assertEquals(0f, race.player.speed)
        assertFalse(race.boosting)
    }

    @Test fun `pad cannot be farmed while parked or revisited but resets next lap and race`() {
        val race = racing()
        fun place(lap: Int, speed: Float) {
            race.player.distance = race.track.padDistance(0) + lap * race.track.length
            race.player.lane = race.track.padLane(0)
            race.player.lateralSpeed = 0f
            race.player.speed = speed
        }
        place(0, 0f)
        runFor(race, 4f)
        assertEquals(0, race.pads)
        place(0, 2f)
        runFor(race, 4f, Controls(brake = true))
        assertEquals(1, race.pads)
        place(0, 2f)
        runFor(race, 0.1f)
        assertEquals(1, race.pads)
        place(1, 2f)
        runFor(race, 0.1f)
        assertEquals(2, race.pads)
        val retry = racing()
        retry.player.distance = retry.track.padDistance(0)
        retry.player.lane = retry.track.padLane(0)
        retry.player.speed = 2f
        runFor(retry, 0.1f)
        assertEquals(1, retry.pads)
    }

    @Test fun `finished rivals cannot block a later finisher`() {
        val race = racing()
        race.rivals.forEach {
            it.distance = race.player.distance
            it.lane = race.player.lane
            it.finishTime = 1f
        }
        runFor(race, 0.5f, Controls(throttle = true))
        assertEquals(0, race.bumps)
    }

    @Test fun `waiting loses race and restarting creates clean state`() {
        val race = racing(difficulty = Difficulty.MEDIUM)
        runFor(race, 95f)
        assertEquals(6, race.position)
        assertTrue(race.rivals.all { it.finishTime != null })
        repeat(150 * 120) { race.advance(Race.STEP, autopilot(race)) }
        assertEquals(Phase.FINISHED, race.phase)
        assertEquals(6, race.position)
        val retry = Race(race.track)
        retry.start()
        assertEquals(Phase.COUNTDOWN, retry.phase)
        assertEquals(0f, retry.elapsed)
        assertEquals(65f, retry.nitro)
        assertEquals(0, retry.bumps)
        assertEquals(0, retry.driftBonuses)
        assertNull(retry.player.finishTime)
    }
}
