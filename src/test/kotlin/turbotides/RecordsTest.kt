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
            assertNull(loaded.best(Circuit.SUNSET, Difficulty.EASY))
            assertEquals(123.5f, loaded.best(Circuit.CINDER, Difficulty.MEDIUM))
            assertNull(loaded.best(Circuit.CINDER, Difficulty.EASY))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `legacy pace records load without writing and fastest valid record wins`() {
        val dir = Files.createTempDirectory("tides-legacy-records")
        try {
            val destination = dir.resolve("records.properties")
            val original = """
                difficulty=CRUISE
                best.SUNSET.CRUISE=61.25
                best.SUNSET.EASY=65.0
                best.SUNSET.RACE=52.5
                best.SUNSET.MEDIUM=51.0
                best.SUNSET.HARD=49.0
                best.SUNSET.SUPER_HARD=47.0
            """.trimIndent()
            Files.writeString(destination, original)
            val records = Records(dir)
            assertEquals(61.25f, records.best(Circuit.SUNSET, Difficulty.EASY))
            assertEquals(51f, records.best(Circuit.SUNSET, Difficulty.MEDIUM))
            assertEquals(49f, records.best(Circuit.SUNSET, Difficulty.HARD))
            assertEquals(47f, records.best(Circuit.SUNSET, Difficulty.SUPER_HARD))
            assertNull(records.best(Circuit.CINDER, Difficulty.EASY))
            assertEquals(original, Files.readString(destination), "Loading must not migrate or rewrite the file")
            assertEquals("CRUISE", records.setting("difficulty", "missing"), "Stored settings remain available to the compatibility parser")
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `malformed legacy and new records do not mask valid alternatives or other difficulties`() {
        val dir = Files.createTempDirectory("tides-invalid-migration")
        try {
            val records = Records(dir)
            assertTrue(
                records.save(
                    mapOf(
                        "best.SUNSET.CRUISE" to "NaN",
                        "best.SUNSET.EASY" to "65.0",
                        "best.SUNSET.RACE" to "52.5",
                        "best.SUNSET.MEDIUM" to "Infinity",
                        "best.SUNSET.HARD" to "0",
                        "best.SUNSET.SUPER_HARD" to "-47.0",
                        "best.CINDER.CRUISE" to "invalid",
                        "best.CINDER.EASY" to "-1",
                    ),
                ),
            )
            val loaded = Records(dir)
            assertEquals(65f, loaded.best(Circuit.SUNSET, Difficulty.EASY))
            assertEquals(52.5f, loaded.best(Circuit.SUNSET, Difficulty.MEDIUM))
            assertNull(loaded.best(Circuit.SUNSET, Difficulty.HARD))
            assertNull(loaded.best(Circuit.SUNSET, Difficulty.SUPER_HARD))
            assertNull(loaded.best(Circuit.CINDER, Difficulty.EASY))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `failed new best save and repair preserve legacy records and all four difficulty slots`() {
        val dir = Files.createTempDirectory("tides-migration-repair")
        try {
            val records = Records(dir)
            assertTrue(
                records.save(
                    mapOf(
                        "best.SUNSET.CRUISE" to "100.0",
                        "best.SUNSET.EASY" to "95.0",
                        "best.SUNSET.RACE" to "90.0",
                        "best.SUNSET.MEDIUM" to "85.0",
                        "best.SUNSET.HARD" to "80.0",
                        "best.SUNSET.SUPER_HARD" to "75.0",
                    ),
                ),
            )
            val race = completedRace(boost = true)
            assertTrue(race.elapsed < 95f)
            val destination = dir.resolve("records.properties")
            Files.delete(destination)
            Files.createDirectory(destination)
            Files.writeString(destination.resolve("keep"), "isolated replacement failure")
            assertFalse(records.finish(race))
            assertEquals(95f, records.best(Circuit.SUNSET, Difficulty.EASY))
            assertEquals(race.elapsed, records.pendingBest(Circuit.SUNSET, Difficulty.EASY))
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            assertTrue(records.save(mapOf("difficulty" to "SUPER_HARD")))
            val loaded = Records(dir)
            assertEquals(race.elapsed, loaded.best(Circuit.SUNSET, Difficulty.EASY))
            assertEquals(85f, loaded.best(Circuit.SUNSET, Difficulty.MEDIUM))
            assertEquals(80f, loaded.best(Circuit.SUNSET, Difficulty.HARD))
            assertEquals(75f, loaded.best(Circuit.SUNSET, Difficulty.SUPER_HARD))
            assertEquals("100.0", loaded.setting("best.SUNSET.CRUISE", "missing"))
            assertEquals("90.0", loaded.setting("best.SUNSET.RACE", "missing"))
            assertEquals("SUPER_HARD", loaded.setting("difficulty", "missing"))
            assertNull(records.pendingBest(Circuit.SUNSET, Difficulty.EASY))
            assertNull(records.error)
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
            assertNull(records.best(Circuit.SUNSET, Difficulty.EASY))
            assertNotNull(records.error)
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            assertTrue(records.finish(race))
            assertEquals(race.elapsed, Records(dir).best(Circuit.SUNSET, Difficulty.EASY))
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
            assertNull(records.best(Circuit.SUNSET, Difficulty.EASY))
            assertEquals(fast.elapsed, records.pendingBest(Circuit.SUNSET, Difficulty.EASY))
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            assertTrue(records.save(mapOf("muted" to "true")))
            assertNull(records.error)
            assertNull(records.pendingBest(Circuit.SUNSET, Difficulty.EASY))
            val reloaded = Records(dir)
            assertEquals(fast.elapsed, reloaded.best(Circuit.SUNSET, Difficulty.EASY))
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
