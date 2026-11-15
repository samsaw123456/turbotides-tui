package turbotides

import com.williamcallahan.tui4j.compat.bubbletea.*
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.time.Duration

class FrameTick : Message

class TerminalGame(val records: Records, private val telemetry: Path? = null) :
    Model,
    AutoCloseable {
    var circuit = Circuit.entries.firstOrNull { it.name == records.setting("circuit", "SUNSET") } ?: Circuit.SUNSET
    var paint = records.setting("paint", "0").toIntOrNull()?.coerceIn(0, 4) ?: 0
    var difficulty = Difficulty.entries.firstOrNull { it.name == records.setting("difficulty", "CRUISE") } ?: Difficulty.CRUISE
    var race = Race(Track(circuit), difficulty, paint)
    val input = TerminalInput()
    var width = 100
    var height = 34
    var menuFocus = 3
    var overview = true
    var muted = records.setting("muted", "false").toBoolean()
    var reducedMotion = records.setting("reducedMotion", "false").toBoolean()
    var help = false
    var focused = true
    var newBest = false
    var diagnosticError: String? = null
    private val renderer = TerminalRenderer()
    private val audio = TerminalAudio(muted)
    val audioStatus get() = audio.status
    private var lastFrame = System.nanoTime()
    private var lastDiagnostic = 0L
    private var saved = false
    private var previousMessage = ""
    val tooSmall get() = width < 64 || height < 24

    override fun init(): Command = tick()
    private fun tick(): Command = Command.tick(Duration.ofMillis(25)) { FrameTick() }
    override fun update(msg: Message): UpdateResult<TerminalGame> {
        val now = System.nanoTime()
        var command: Command? = null
        when (msg) {
            is WindowSizeMessage -> {
                width = msg.width()
                height = msg.height()
                if (tooSmall) pause()
            }
            is BlurMessage -> {
                focused = false
                pause()
            }
            is FocusMessage -> {
                focused = true
                input.clear()
            }
            is KeyPressMessage -> {
                if (msg.key() == "q" || msg.key() == "ctrl+c") return UpdateResult(this, Command.quit())
                key(msg.key(), now)
            }
            is FrameTick -> {
                val delta = ((now - lastFrame) / 1_000_000_000.0).toFloat().coerceIn(0f, 0.1f)
                val before = race.phase
                if (!help && focused && !tooSmall) race.advance(delta, input.controls(now))
                if (before != Phase.RACING && race.phase == Phase.RACING) audio.cue("go", muted)
                if (race.phase == Phase.FINISHED && !saved) {
                    newBest = records.finish(race)
                    saved = true
                    input.clear()
                    audio.cue("finish", muted)
                }
                if (race.messageTime > 0 && previousMessage != race.message) {
                    previousMessage = race.message
                    if (race.message != "GO!") audio.cue(if (race.message.contains("bump") || race.message.contains("paint")) "bump" else "bonus", muted)
                }
                audio.update(race, muted)
                lastFrame = now
                command = tick()
            }
        }
        if (telemetry != null && now - lastDiagnostic > 100_000_000L) {
            diagnostic(now)
            lastDiagnostic = now
        }
        return UpdateResult(this, command)
    }

    private fun key(key: String, now: Long) {
        if (tooSmall || !focused) return
        if (key == "m" && input.acceptToggle(key, now)) {
            muted = !muted
            saveSettings()
            return
        }
        if (key == "n" && input.acceptToggle(key, now)) {
            reducedMotion = !reducedMotion
            saveSettings()
            return
        }
        if (key == "?" && input.acceptToggle(key, now)) {
            if (!help) pause()
            help = !help
            return
        }
        if (help) {
            if (key == "esc" || key == "enter") help = false
            return
        }
        if (key == "esc" && input.acceptToggle(key, now)) {
            when (race.phase) {
                Phase.GARAGE -> Unit
                Phase.FINISHED -> garage()
                Phase.PAUSED -> {
                    input.clear()
                    race.resume()
                }
                else -> pause()
            }
            return
        }
        if (key == "r" && race.phase != Phase.GARAGE && input.acceptToggle(key, now)) {
            start()
            return
        }
        when (race.phase) {
            Phase.GARAGE -> garageKey(key, now)
            Phase.COUNTDOWN, Phase.RACING -> input.drive(key, now)
            Phase.PAUSED -> when (key) {
                "enter" -> {
                    input.clear()
                    race.resume()
                }
                "g" -> garage()
            }
            Phase.FINISHED -> when (key) {
                "enter" -> start()
                "g" -> garage()
            }
        }
    }

    private fun garageKey(key: String, now: Long) {
        when (key) {
            "up", "w", "shift+tab" -> menuFocus = Math.floorMod(menuFocus - 1, 4)
            "down", "s", "tab" -> menuFocus = (menuFocus + 1) % 4
            "left", "a" -> change(-1)
            "right", "d" -> change(1)
            "p" -> if (input.acceptToggle(key, now)) {
                overview = !overview
            }
            "enter" -> if (input.acceptToggle(key, now)) {
                if (menuFocus == 3) start() else change(1)
            }
        }
    }
    private fun change(direction: Int) {
        when (menuFocus) {
            1 -> paint = Math.floorMod(paint + direction, 5)
            2 -> difficulty = if (difficulty == Difficulty.CRUISE) Difficulty.RACE else Difficulty.CRUISE
            else -> circuit = Circuit.entries[Math.floorMod(circuit.ordinal + direction, Circuit.entries.size)]
        }
        race = Race(Track(circuit), difficulty, paint)
        saveSettings()
    }
    private fun saveSettings() = records.save(mapOf("circuit" to circuit.name, "paint" to paint.toString(), "difficulty" to difficulty.name, "muted" to muted.toString(), "reducedMotion" to reducedMotion.toString()))
    private fun start() {
        input.clear()
        race = Race(Track(circuit), difficulty, paint)
        race.start()
        saved = false
        newBest = false
        previousMessage = ""
    }
    private fun garage() {
        input.clear()
        race = Race(Track(circuit), difficulty, paint)
        help = false
    }
    private fun pause() {
        race.pause()
        input.clear()
    }
    override fun view(): String = renderer.render(this)
    override fun close() = audio.close()

    private fun diagnostic(now: Long) {
        val controls = input.controls(now)
        val fields = linkedMapOf<String, Any?>(
            "phase" to race.phase.name, "circuit" to circuit.name, "paint" to paint, "difficulty" to difficulty.name,
            "focus" to focused, "countdown" to race.countdown, "time" to race.elapsed,
            "distance" to race.player.distance, "length" to race.track.length, "lane" to race.player.lane,
            "speed" to race.player.speed, "lap" to race.lap, "position" to race.position,
            "nitro" to race.nitro, "driftCharge" to race.driftCharge, "drifting" to race.drifting,
            "boosting" to race.boosting, "pads" to race.pads, "bumps" to race.bumps, "driftBonuses" to race.driftBonuses,
            "rearView" to input.rearView, "reducedMotion" to reducedMotion, "muted" to muted,
            "throttle" to input.throttle, "brake" to input.brake, "steer" to controls.steer,
            "drift" to input.drift, "boost" to input.boost, "width" to width, "height" to height,
            "help" to help, "menuFocus" to menuFocus, "overview" to overview,
            "best" to records.best(circuit, difficulty), "saveError" to (records.error != null),
        )
        val json = fields.entries.joinToString(",", "{", "}") { (k, v) -> "\"$k\":" + if (v is String) "\"$v\"" else v.toString() }
        try {
            val target = telemetry!!.toAbsolutePath()
            Files.createDirectories(target.parent)
            val temp = target.resolveSibling("${target.fileName}.tmp")
            Files.writeString(temp, json)
            Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING)
        } catch (e: Exception) {
            diagnosticError = "Diagnostics unavailable: ${e.message}"
        }
    }
}
