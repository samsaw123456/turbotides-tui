package turbotides

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class RendererTest {
    @Test fun `time rounding carries seconds into minutes`() {
        assertEquals("1:00.00", TerminalRenderer.time(59.999f))
        assertEquals("2:00.00", TerminalRenderer.time(119.999f))
        assertEquals("0:00.01", TerminalRenderer.time(.01f))
        assertEquals("--:--.--", TerminalRenderer.time(null))
    }

    @Test fun `car centre crosses rendered road edge when physics says grass`() {
        val directory = Files.createTempDirectory("tides-render")
        val game = TerminalGame(Records(directory))
        try {
            val renderer = TerminalRenderer()
            game.race.player.distance = 100f
            val baseline = PixelCanvas(120, 62, 0)
            game.race.player.lane = 0f
            renderer.road(baseline, game)
            // Find the actual asphalt's right edge in rendered output, independently of the lane projection.
            val row = 57
            val roadEdge = (60 until 120).filter { baseline.colorAt(it, row) in setOf(0x374851, 0x3b4d57) }.max()
            game.race.player.lane = 9.8f
            val grass = PixelCanvas(120, 62, 0)
            renderer.road(grass, game)
            val center = (60 until 119).single { x -> grass.colorAt(x, row) == 0xffedce && grass.colorAt(x - 1, row) == 0xff653b && grass.colorAt(x + 1, row) == 0xff653b }
            assertTrue(center > roadEdge, "Offroad player centre must visibly cross asphalt edge: $center <= $roadEdge")
            game.input.rearView = true
            val rear = PixelCanvas(120, 62, 0)
            renderer.road(rear, game)
            val rearCenter = (1 until 60).single { x -> rear.colorAt(x, row) == 0xffedce && rear.colorAt(x - 1, row) == 0xff653b && rear.colorAt(x + 1, row) == 0xff653b }
            assertEquals(120 - center, rearCenter)
        } finally {
            game.close()
            directory.toFile().deleteRecursively()
        }
    }

    @Test fun `barrier positions keep the full player visible at all supported sizes`() {
        val directory = Files.createTempDirectory("tides-bounds")
        val game = TerminalGame(Records(directory))
        try {
            val renderer = TerminalRenderer()
            game.race.player.distance = 100f
            for ((width, height) in listOf(64 to 30, 120 to 62, 180 to 112)) {
                for (lane in listOf(-12f, 12f)) {
                    game.race.player.lane = lane
                    val canvas = PixelCanvas(width, height, 0)
                    renderer.road(canvas, game)
                    val row = height - 5
                    val center = (1 until width - 1).single { x -> canvas.colorAt(x, row) == 0xffedce && canvas.colorAt(x - 1, row) == 0xff653b && canvas.colorAt(x + 1, row) == 0xff653b }
                    val bodyLeft = (center downTo 0).first { canvas.colorAt(it, row) != 0xff653b && it != center }
                    val bodyRight = (center until width).first { canvas.colorAt(it, row) != 0xff653b && it != center }
                    assertTrue(bodyLeft >= 0 && bodyRight < width, "Entire player body must fit at barrier $lane in $width columns")
                }
            }
        } finally {
            game.close()
            directory.toFile().deleteRecursively()
        }
    }
}
