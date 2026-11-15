package turbotides

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class TerminalGameDiagnosticsTest {
    @Test fun `a recovered diagnostic destination clears the visible error`() {
        val dir = Files.createTempDirectory("tides-diagnostics")
        val target = dir.resolve("state.json")
        Files.createDirectory(target)
        Files.writeString(target.resolve("keep"), "isolated failure fixture")
        val game = TerminalGame(Records(dir.resolve("profile")), target)
        try {
            game.update(FrameTick())
            assertNotNull(game.diagnosticError)
            assertTrue(game.view().contains("Diagnostics unavailable"))
            Files.list(dir).use { entries ->
                assertEquals(listOf(target), entries.toList(), "A failed write must remove its temporary file")
            }
            Files.delete(target.resolve("keep"))
            Files.delete(target)
            // Diagnostics intentionally write at most ten times a second.
            Thread.sleep(120)
            game.update(FrameTick())
            assertTrue(Files.readString(target).contains("\"phase\":\"GARAGE\""))
            assertNull(game.diagnosticError)
            assertTrue(game.view().contains("Local records only"))
        } finally {
            game.close()
            dir.toFile().deleteRecursively()
        }
    }

    @Test fun `diagnostic writes preserve a preexisting sibling temporary name`() {
        val dir = Files.createTempDirectory("tides-diagnostic-sibling")
        // A one-letter destination also proves temporary creation has a valid prefix.
        val target = dir.resolve("s")
        val sibling = dir.resolve("s.tmp")
        Files.writeString(sibling, "unrelated user data")
        val game = TerminalGame(Records(dir.resolve("profile")), target)
        try {
            game.update(FrameTick())
            assertNull(game.diagnosticError)
            assertEquals("unrelated user data", Files.readString(sibling))
            assertTrue(Files.readString(target).contains("\"phase\":\"GARAGE\""))
            Files.list(dir).use { entries ->
                assertEquals(setOf(target, sibling), entries.toList().toSet(), "Successful writes must leave no temporary files")
            }
        } finally {
            game.close()
            dir.toFile().deleteRecursively()
        }
    }
}
