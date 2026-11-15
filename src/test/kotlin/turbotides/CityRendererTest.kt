package turbotides

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CityRendererTest {
    private val cities = listOf(Circuit.SAN_FRANCISCO, Circuit.SILICON_VALLEY, Circuit.NEW_YORK, Circuit.CHICAGO)
    private val sizes = listOf(64 to 30, 100 to 50, 180 to 112)
    private val asphalt = setOf(0x374851, 0x3b4d57)
    private val grass = setOf(0x3a7162, 0x3e7969)

    @Test fun `city frontage preserves visible asphalt edges and grass recovery at every size`() = withGame { game ->
        for (circuit in cities) {
            select(game, circuit)
            for ((width, height) in sizes) {
                for (progress in listOf(.02f, .2f, .5f, .85f)) {
                    game.race.player.distance = game.race.track.length * progress
                    hideRivals(game)
                    for (rear in listOf(false, true)) {
                        game.input.rearView = rear
                        game.race.player.lane = 0f
                        val baseline = draw(game, width, height)
                        val row = height - 5
                        val road = (0 until width).filter { baseline.colorAt(it, row) in asphalt }
                        assertTrue(road.isNotEmpty(), "Missing asphalt in $circuit $width/$rear/$progress")
                        val left = road.min()
                        val right = road.max()
                        assertTrue((0 until left).any { baseline.colorAt(it, row) in grass }, "Left recovery grass was covered by scenery")
                        assertTrue((right + 1 until width).any { baseline.colorAt(it, row) in grass }, "Right recovery grass was covered by scenery")
                        for (lane in listOf(-9.8f, 9.8f)) {
                            game.race.player.lane = lane
                            val center = playerCenter(draw(game, width, height), row)
                            val screenRight = (lane > 0) != rear
                            assertTrue(
                                if (screenRight) center > right else center < left,
                                "Offroad car must visibly cross asphalt in $circuit $width/$rear/$progress: $center outside $left..$right",
                            )
                        }
                    }
                }
            }
        }
    }

    @Test fun `city buildings never hide player at either barrier in either camera`() = withGame { game ->
        for (circuit in cities) {
            select(game, circuit)
            for ((width, height) in sizes) {
                for (progress in listOf(.02f, .2f, .5f, .85f)) {
                    game.race.player.distance = game.race.track.length * progress
                    hideRivals(game)
                    for (rear in listOf(false, true)) {
                        game.input.rearView = rear
                        val centers = listOf(-12f, 0f, 12f).map { lane ->
                            game.race.player.lane = lane
                            val canvas = draw(game, width, height)
                            val row = height - 5
                            val center = playerCenter(canvas, row)
                            val left = (center - 1 downTo 0).first { canvas.colorAt(it, row) != 0xff653b }
                            val right = (center + 1 until width).first { canvas.colorAt(it, row) != 0xff653b }
                            assertEquals(0x102b35, canvas.colorAt(left, row), "Left tire must remain visible")
                            assertEquals(0x102b35, canvas.colorAt(right, row), "Right tire must remain visible")
                            assertTrue(left > 0 && right < width - 1, "Full player must fit at $circuit $width/$rear/$progress/$lane")
                            center
                        }
                        assertTrue(if (rear) centers[0] > centers[1] && centers[1] > centers[2] else centers[0] < centers[1] && centers[1] < centers[2])
                    }
                }
            }
        }
    }

    @Test fun `city scenery is deterministic without advancing or modifying driving state`() = withGame { game ->
        for (circuit in cities) {
            select(game, circuit)
            game.race.player.distance = game.race.track.length * .37f
            game.race.player.lane = 2f
            game.race.player.speed = 41f
            game.race.player.lateralSpeed = -3f
            val before = state(game)
            for ((width, height) in sizes) {
                for (rear in listOf(false, true)) {
                    game.input.rearView = rear
                    val first = pixels(draw(game, width, height))
                    assertEquals(first, pixels(draw(game, width, height)), "Frozen $circuit scene flickered")
                    assertEquals(before, state(game), "Rendering must not change race state")
                }
            }
        }
    }

    @Test fun `city skyline has no lap wrap seam in either view`() {
        for (circuit in cities) {
            for ((width, height) in sizes) {
                for (rear in listOf(false, true)) {
                    fun skyline(progress: Float): List<Int> {
                        val canvas = PixelCanvas(width, height, 0)
                        CityScenery.skyline(canvas, circuit, (height * .27f).toInt(), progress, rear)
                        return pixels(canvas)
                    }
                    assertEquals(skyline(0f), skyline(1f), "Skyline jumped at lap wrap in $circuit $width/$rear")
                }
            }
        }
    }

    private fun select(game: TerminalGame, circuit: Circuit) {
        game.circuit = circuit
        game.race = Race(Track(circuit))
    }

    private fun hideRivals(game: TerminalGame) {
        game.race.rivals.forEach { it.distance = game.race.player.distance + game.race.track.length / 2 }
    }

    private fun draw(game: TerminalGame, width: Int, height: Int): PixelCanvas = PixelCanvas(width, height, 0).also { TerminalRenderer().road(it, game) }

    // Locate the visible cream player marker surrounded by orange bodywork,
    // independently of the renderer's lane sign and projection arithmetic.
    private fun playerCenter(canvas: PixelCanvas, row: Int): Int = (1 until canvas.width - 1).single { x ->
        canvas.colorAt(x, row) == 0xffedce && canvas.colorAt(x - 1, row) == 0xff653b && canvas.colorAt(x + 1, row) == 0xff653b
    }

    private fun pixels(canvas: PixelCanvas): List<Int> = (0 until canvas.height).flatMap { y -> (0 until canvas.width).map { x -> canvas.colorAt(x, y) } }

    private fun state(game: TerminalGame): List<Any?> = with(game.race) {
        listOf(phase, elapsed, countdown, nitro, pads, bumps, driftBonuses, player.distance, player.lane, player.speed, player.lateralSpeed, rivals.map { listOf(it.distance, it.lane, it.speed) })
    }

    private fun withGame(check: (TerminalGame) -> Unit) {
        val directory = Files.createTempDirectory("tides-city-render")
        val records = Records(directory)
        records.save(mapOf("muted" to "true"))
        val game = TerminalGame(records)
        try {
            check(game)
        } finally {
            game.close()
            directory.toFile().deleteRecursively()
        }
    }
}
