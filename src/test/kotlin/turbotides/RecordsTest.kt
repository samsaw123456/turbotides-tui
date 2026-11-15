package turbotides

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RecordsTest {
    @Test fun `preferences reload and malformed records do not become bests`() {
        val dir = Files.createTempDirectory("tides-records")
        try {
            val records = Records(dir)
            records.save(mapOf("paint" to "3", "best.SUNSET.CRUISE" to "NaN", "best.CINDER.RACE" to "123.5"))
            val loaded = Records(dir)
            assertEquals("3", loaded.setting("paint", "0"))
            assertNull(loaded.best(Circuit.SUNSET, Difficulty.CRUISE))
            assertEquals(123.5f, loaded.best(Circuit.CINDER, Difficulty.RACE))
            assertNull(loaded.best(Circuit.CINDER, Difficulty.CRUISE))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `unwritable destination reports failure without crashing`() {
        val file = Files.createTempFile("tides-not-directory", ".tmp")
        try {
            val records = Records(file)
            records.save(mapOf("paint" to "2"))
            assertNotNull(records.error)
        } finally {
            Files.deleteIfExists(file)
        }
    }

    @Test fun `failed replacement preserves saved state cleans temporary file and can retry`() {
        val dir = Files.createTempDirectory("tides-replacement")
        try {
            val records = Records(dir)
            assertTrue(records.save(mapOf("paint" to "1")))
            val destination = dir.resolve("records.properties")
            Files.delete(destination)
            Files.createDirectory(destination)
            // A nonempty directory cannot be replaced by the completed file.
            Files.writeString(destination.resolve("keep"), "unrelated file")
            assertFalse(records.save(mapOf("paint" to "2")))
            assertEquals("1", records.setting("paint", "0"))
            assertNotNull(records.error)
            Files.list(dir).use { entries ->
                assertEquals(listOf(destination), entries.toList())
            }
            assertEquals("unrelated file", Files.readString(destination.resolve("keep")))
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            assertTrue(records.save(mapOf("paint" to "2")))
            assertNull(records.error)
            assertEquals("2", Records(dir).setting("paint", "0"))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `failed finish save does not claim a best and remains retryable`() {
        val dir = Files.createTempDirectory("tides-finish-save")
        try {
            val records = Records(dir)
            val race = completedRace(boost = true)
            val destination = dir.resolve("records.properties")
            Files.createDirectory(destination)
            Files.writeString(destination.resolve("keep"), "unrelated file")
            assertFalse(records.finish(race))
            assertNull(records.best(Circuit.SUNSET, Difficulty.CRUISE))
            assertNotNull(records.error)
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            assertTrue(records.finish(race))
            assertEquals(race.elapsed, Records(dir).best(Circuit.SUNSET, Difficulty.CRUISE))
            assertFalse(records.finish(race))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `a settings save recovers pending bests without replacing them with a slower finish`() {
        val dir = Files.createTempDirectory("tides-pending-best")
        try {
            val records = Records(dir)
            val fast = completedRace(boost = true)
            val slow = completedRace(boost = false)
            assertTrue(fast.elapsed < slow.elapsed)
            val destination = dir.resolve("records.properties")
            Files.createDirectory(destination)
            Files.writeString(destination.resolve("keep"), "unrelated file")
            assertFalse(records.finish(fast))
            assertFalse(records.finish(slow))
            assertNull(records.best(Circuit.SUNSET, Difficulty.CRUISE))
            assertEquals(fast.elapsed, records.pendingBest(Circuit.SUNSET, Difficulty.CRUISE))
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            assertTrue(records.save(mapOf("muted" to "true")))
            assertNull(records.error)
            assertNull(records.pendingBest(Circuit.SUNSET, Difficulty.CRUISE))
            val reloaded = Records(dir)
            assertEquals(fast.elapsed, reloaded.best(Circuit.SUNSET, Difficulty.CRUISE))
            assertEquals("true", reloaded.setting("muted", "false"))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    private fun completedRace(boost: Boolean): Race {
        val race = Race(Track(Circuit.SUNSET))
        race.start()
        repeat(120 * 100) {
            race.advance(
                Race.STEP,
                Controls(
                    throttle = true,
                    steer = ((-race.player.lane * 3f - race.cornerForce()) / 11f).coerceIn(-1f, 1f),
                    boost = boost,
                ),
            )
        }
        assertEquals(Phase.FINISHED, race.phase)
        return race
    }
}
