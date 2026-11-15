package turbotides

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.util.Properties

class Records(private val directory: Path) {
    private val properties = Properties()
    private val pendingBests = mutableMapOf<String, Float>()
    var error: String? = null
        private set
    init {
        try {
            val file = directory.resolve("records.properties")
            if (Files.exists(file)) Files.newInputStream(file).use(properties::load)
        } catch (e: Exception) {
            error = "Cannot load records: ${e.message}"
        }
    }
    fun setting(key: String, fallback: String): String = properties.getProperty(key, fallback)
    fun best(circuit: Circuit, difficulty: Difficulty): Float? {
        // Read old pace records without rewriting the user's file on startup.
        // Keeping both keys also preserves records if an older version is used.
        val legacy = when (difficulty) {
            Difficulty.EASY -> "CRUISE"
            Difficulty.MEDIUM -> "RACE"
            else -> null
        }
        val prefix = "best.${circuit.name}."
        return listOfNotNull(recordedTime(prefix + difficulty.name), legacy?.let { recordedTime(prefix + it) }).minOrNull()
    }
    private fun recordedTime(key: String): Float? = properties.getProperty(key)?.toFloatOrNull()?.takeIf { it.isFinite() && it > 0 }
    fun pendingBest(circuit: Circuit, difficulty: Difficulty): Float? = pendingBests["best.${circuit.name}.${difficulty.name}"]
    fun finish(race: Race): Boolean {
        if (race.phase != Phase.FINISHED || race.elapsed >= (best(race.track.circuit, race.difficulty) ?: Float.MAX_VALUE)) return false
        val key = "best.${race.track.circuit.name}.${race.difficulty.name}"
        val fastest = minOf(race.elapsed, pendingBests[key] ?: Float.MAX_VALUE)
        pendingBests[key] = fastest
        return save(emptyMap()) && fastest == race.elapsed
    }
    fun save(values: Map<String, String>): Boolean {
        // Only publish a best/settings snapshot after the replacement succeeds.
        // A failed write must remain retryable and must not claim a saved best.
        val updated = Properties().apply {
            putAll(properties)
            putAll(values)
            // Keep earned records across failed writes and subsequent races.
            // A later settings save must not erase the only pending best.
            putAll(pendingBests.mapValues { it.value.toString() })
        }
        var temporary: Path? = null
        var stored = false
        try {
            Files.createDirectories(directory)
            temporary = Files.createTempFile(directory, "records-", ".tmp")
            Files.newOutputStream(temporary).use { updated.store(it, "Turbo Tides TUI local records") }
            try {
                Files.move(temporary, directory.resolve("records.properties"), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
            } catch (_: java.nio.file.AtomicMoveNotSupportedException) {
                Files.move(temporary, directory.resolve("records.properties"), StandardCopyOption.REPLACE_EXISTING)
            }
            properties.putAll(updated)
            pendingBests.clear()
            error = null
            stored = true
        } catch (e: Exception) {
            error = "Cannot save records: ${e.message}"
        } finally {
            try {
                temporary?.let { Files.deleteIfExists(it) }
            } catch (e: Exception) {
                // Permission or device failure can also prevent cleanup. Keep
                // racing, preserving the original failure and visible warning.
                val cleanup = "Cannot clean up temporary records: ${e.message}"
                error = error?.let { "$it; $cleanup" } ?: cleanup
            }
        }
        return stored
    }
}
