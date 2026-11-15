package turbotides

import com.williamcallahan.tui4j.compat.bubbletea.KeyPressMessage
import com.williamcallahan.tui4j.compat.bubbletea.input.key.Key
import com.williamcallahan.tui4j.compat.bubbletea.input.key.KeyType
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class TerminalDifficultyTest {
    @Test fun `difficulty selector cycles both directions saves and starts selected race`() {
        val dir = Files.createTempDirectory("tides-level-menu")
        val records = Records(dir)
        records.save(mapOf("muted" to "true"))
        val game = TerminalGame(records)
        try {
            game.width = 64
            game.height = 24
            game.update(KeyPressMessage(Key(KeyType.KeyUp)))
            assertEquals(2, game.menuFocus)
            for ((key, expected) in listOf(
                KeyType.KeyRight to listOf(Difficulty.MEDIUM, Difficulty.HARD, Difficulty.SUPER_HARD, Difficulty.EASY),
                KeyType.KeyLeft to listOf(Difficulty.SUPER_HARD, Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY),
            )) {
                for (level in expected) {
                    game.update(KeyPressMessage(Key(key)))
                    assertEquals(level, game.difficulty)
                    assertEquals(level, game.race.difficulty)
                    assertEquals(level.name, Records(dir).setting("difficulty", "missing"))
                    assertTrue(game.view().lineSequence().first().contains(level.title), "Level must fit minimum-width header")
                    assertTrue(game.view().contains("Difficulty < ${level.title} >"))
                }
            }
            game.update(KeyPressMessage(Key(KeyType.KeyLeft)))
            game.update(KeyPressMessage(Key(KeyType.KeyDown)))
            game.update(KeyPressMessage(Key(KeyType.keyCR)))
            assertEquals(Phase.COUNTDOWN, game.race.phase)
            assertEquals(Difficulty.SUPER_HARD, game.race.difficulty)
            assertTrue(game.view().lineSequence().first().contains("Super Hard"))
        } finally {
            game.close()
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `legacy setting names load into matching new levels without rewriting profile`() {
        val mappings = listOf("CRUISE" to Difficulty.EASY, "RACE" to Difficulty.MEDIUM) +
            Difficulty.entries.map { it.name to it } + ("invalid" to Difficulty.EASY)
        for ((stored, expected) in mappings) {
            val dir = Files.createTempDirectory("tides-level-legacy")
            val path = dir.resolve("records.properties")
            val original = "difficulty=$stored\nmuted=true\nbest.SUNSET.CRUISE=51.25\n"
            Files.writeString(path, original)
            val game = TerminalGame(Records(dir))
            try {
                assertEquals(expected, game.difficulty)
                assertEquals(expected, game.race.difficulty)
                assertTrue(game.view().contains(expected.title))
                assertEquals(original, Files.readString(path), "Loading legacy profile must not rewrite it")
            } finally {
                game.close()
                dir.toFile().deleteRecursively()
            }
        }
    }
}
