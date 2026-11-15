package turbotides

/** ANSI reports presses, not releases. Driving modes are explicit; steering is a short pulse. */
class TerminalInput {
    var throttle = false
    var brake = false
    var drift = false
    var boost = false
    var rearView = false
    private var direction = 0f
    private var steeringUntil = 0L
    private val toggled = mutableMapOf<String, Long>()

    fun acceptToggle(key: String, now: Long): Boolean {
        val previous = toggled.put(key, now)
        return previous == null || now - previous > 220_000_000L
    }

    fun drive(key: String, now: Long) {
        when (key) {
            "w", "up" -> {
                throttle = true
                brake = false
            }
            "s", "down" -> {
                throttle = false
                brake = true
                boost = false
            }
            "a", "left" -> {
                direction = -1f
                steeringUntil = now + 180_000_000L
            }
            "d", "right" -> {
                direction = 1f
                steeringUntil = now + 180_000_000L
            }
            " " -> if (acceptToggle(key, now)) {
                drift = !drift
            }
            "b" -> if (acceptToggle(key, now)) {
                boost = !boost
            }
            "c" -> if (acceptToggle(key, now)) {
                rearView = !rearView
            }
        }
    }

    fun controls(now: Long) = Controls(throttle, brake, if (now < steeringUntil) direction else 0f, drift, boost)

    fun clear() {
        throttle = false
        brake = false
        drift = false
        boost = false
        rearView = false
        direction = 0f
        steeringUntil = 0
    }
}
