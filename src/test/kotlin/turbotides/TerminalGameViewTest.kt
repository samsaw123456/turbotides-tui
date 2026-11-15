package turbotides

import com.williamcallahan.tui4j.compat.bubbletea.KeyPressMessage
import com.williamcallahan.tui4j.compat.bubbletea.input.key.Key
import com.williamcallahan.tui4j.compat.bubbletea.input.key.KeyType
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotSame
import kotlin.test.assertSame
import kotlin.test.assertTrue

class TerminalGameViewTest {
    @Test fun `static ticks reuse art while input simulation and status changes refresh it`() {
        val dir = Files.createTempDirectory("tides-static-view")
        val records = Records(dir)
        records.save(mapOf("muted" to "true"))
        val game = TerminalGame(records)
        try {
            val garage = game.view()
            repeat(3) {
                game.update(FrameTick())
                assertSame(garage, game.view(), "Idle ticks must reuse the rendered string")
            }
            game.update(KeyPressMessage(Key(KeyType.KeyUp)))
            val selected = game.view()
            assertNotSame(garage, selected)
            assertEquals(2, game.menuFocus)
            game.update(FrameTick())
            assertSame(selected, game.view())
            val destination = dir.resolve("records.properties")
            Files.delete(destination)
            Files.createDirectory(destination)
            Files.writeString(destination.resolve("keep"), "isolated failure fixture")
            records.save(mapOf("paint" to "2"))
            val failed = game.view()
            assertNotSame(selected, failed)
            assertTrue(failed.contains("Cannot save records"))
            Files.delete(destination.resolve("keep"))
            Files.delete(destination)
            records.save(emptyMap())
            val recovered = game.view()
            assertNotSame(failed, recovered)
            assertTrue(recovered.contains("Local records only"))
            game.update(KeyPressMessage(Key(KeyType.KeyDown)))
            game.update(KeyPressMessage(Key(KeyType.keyCR)))
            val countdown = game.view()
            assertEquals(Phase.COUNTDOWN, game.race.phase)
            game.update(FrameTick())
            assertNotSame(countdown, game.view(), "Active simulation must continue rendering")
            game.update(KeyPressMessage(Key(KeyType.keyESC)))
            val paused = game.view()
            assertEquals(Phase.PAUSED, game.race.phase)
            game.update(FrameTick())
            assertSame(paused, game.view(), "Paused simulation must reuse its art")
        } finally {
            game.close()
            dir.toFile().deleteRecursively()
        }
    }
}
