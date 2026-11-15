package turbotides

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.util.Properties

class Records(private val directory: Path) {
    private val properties = Properties()
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
    fun best(circuit: Circuit, difficulty: Difficulty): Float? = properties.getProperty("best.${circuit.name}.${difficulty.name}")
        ?.toFloatOrNull()?.takeIf { it.isFinite() && it > 0 }
    fun finish(race: Race): Boolean {
        if (race.phase != Phase.FINISHED || race.elapsed >= (best(race.track.circuit, race.difficulty) ?: Float.MAX_VALUE)) return false
        return save(mapOf("best.${race.track.circuit.name}.${race.difficulty.name}" to race.elapsed.toString()))
    }
    fun save(values: Map<String, String>): Boolean {
        // Only publish a best/settings snapshot after the replacement succeeds.
        // A failed write must remain retryable and must not claim a saved best.
        val updated = Properties().apply {
            putAll(properties)
            putAll(values)
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
            properties.putAll(values)
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
