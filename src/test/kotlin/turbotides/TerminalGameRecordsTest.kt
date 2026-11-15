package turbotides

import com.williamcallahan.tui4j.compat.bubbletea.KeyPressMessage
import com.williamcallahan.tui4j.compat.bubbletea.input.key.Key
import com.williamcallahan.tui4j.compat.bubbletea.input.key.KeyType
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class TerminalGameRecordsTest {
    @Test fun `finished result reports pending save and settings recovery preserves earned best`() {
        val dir = Files.createTempDirectory("tides-game-records")
        val game = TerminalGame(Records(dir))
        try {
            val destination = dir.resolve("records.properties")
            Files.createDirectory(destination)
            Files.writeString(destination.resolve("keep"), "isolated failure fixture")
            val race = game.race
            race.start()
            repeat(120 * 100) {
                race.advance(
                    Race.STEP,
                    Controls(
                        throttle = true,
                        steer = ((-race.player.lane * 3f - race.cornerForce()) / 11f).coerceIn(-1f, 1f),
                        boost = true,
                    ),
                )
            }
            assertEquals(Phase.FINISHED, race.phase)
            game.update(FrameTick())
            assertNotNull(game.records.error)
            assertFalse(game.newBest)
            assertNull(game.records.best(Circuit.SUNSET, Difficulty.CRUISE))
            assertTrue(game.view().contains("Personal best pending save"))
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            game.update(KeyPressMessage(Key(KeyType.KeyRunes, charArrayOf('m'))))
            assertNull(game.records.error)
            assertTrue(game.newBest)
            assertTrue(game.view().contains("New personal best!"))
            assertFalse(game.view().contains("pending save"))
            assertEquals(race.elapsed, Records(dir).best(Circuit.SUNSET, Difficulty.CRUISE))
            assertEquals("true", Records(dir).setting("muted", "false"))
            game.update(FrameTick())
            assertTrue(game.newBest)
            assertEquals(Phase.FINISHED, game.race.phase)
        } finally {
            game.close()
            dir.toFile().deleteRecursively()
        }
    }
}
