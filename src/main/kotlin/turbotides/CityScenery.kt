package turbotides

import kotlin.math.*

/** Original Turbo Tides city palettes and architecture, adapted to two-pixel terminal cells. */
object CityScenery {
    private const val STONE = 0xe8dcc1
    private const val GLASS = 0x54777c
    private const val TREE = 0x52785e
    private val houses = intArrayOf(0xcfa38d, 0xabc6b7, 0xe6c981, 0xc4b2aa, 0xd2d7bd)
    private val masonry = intArrayOf(0x839b9d, 0xac9c86, 0x8f9698, 0xbdad91)

    fun skyline(c: PixelCanvas, circuit: Circuit, horizon: Int, progress: Float, rear: Boolean) {
        val phase = progress - floor(progress)
        val drift = (sin(phase * PI * 2) * c.width * .035).roundToInt()
        fun x(fraction: Float): Int {
            val position = (c.width * fraction).roundToInt() + drift
            return if (rear) c.width - 1 - position else position
        }
        when (circuit) {
            Circuit.SAN_FRANCISCO -> {
                for (px in 0 until c.width) {
                    val worldX = if (rear) c.width - 1 - px else px
                    val top = horizon - 2 - (horizon * .2 * (1 + sin(worldX * .075 + phase * PI * 2))).toInt()
                    c.rect(px, top, 1, horizon - top, 0x91a79a)
                }
                c.rect(0, horizon - 2, c.width, 2, 0x63999b)
                bridge(c, x(.25f), horizon, (c.width * .43f).roundToInt())
                val center = x(.78f)
                val tall = max(6, horizon - 1)
                for (y in 0 until tall) {
                    val half = max(0, y * max(2, c.width / 34) / tall)
                    c.rect(center - half, horizon - tall + y, half * 2 + 1, 1, if (y % 3 == 0) 0xb8c1b8 else 0xeee0c8)
                }
                c.line(center, horizon - tall - 2, center, horizon - tall, STONE)
                for (i in 0..8) {
                    val bx = x(.52f + i * .052f)
                    val tallHouse = 2 + i % 3
                    c.rect(bx - 2, horizon - tallHouse, 4, tallHouse, houses[i % houses.size])
                    c.rect(bx - 2, horizon - tallHouse - 1, 4, 1, 0x78685b)
                }
            }
            Circuit.SILICON_VALLEY -> {
                for (px in 0 until c.width) {
                    val worldX = if (rear) c.width - 1 - px else px
                    val top = horizon - 3 - (horizon * .28 * (1 + sin(worldX * .055 + .8))).toInt()
                    c.rect(px, top, 1, horizon - top, 0x8ca775)
                }
                val center = x(.32f)
                val width = max(12, c.width / 3)
                c.rect(center - width / 2, horizon - 4, width, 4, 0xcdd6c5)
                c.rect(center - width / 2 + 2, horizon - 5, width - 4, 1, 0x294c62)
                c.rect(center - width / 2 + 1, horizon - 3, width - 2, 2, 0x537f89)
                c.rect(center - width / 5, horizon - 3, width * 2 / 5, 3, 0x7d9d70)
                val dish = x(.81f)
                c.line(dish, horizon, dish, horizon - 5, 0xd3cbb3)
                c.line(dish - 4, horizon - 7, dish, horizon - 4, STONE)
                c.line(dish, horizon - 4, dish + 4, horizon - 7, STONE)
                c.line(dish, horizon - 4, dish + 1, horizon - 8, GLASS)
            }
            Circuit.NEW_YORK -> {
                for (i in 0..15) {
                    val tall = max(3, horizon * (35 + (i * 19 % 40)) / 100)
                    val width = max(3, c.width / 18)
                    val bx = x(i / 15f)
                    c.rect(bx - width / 2, horizon - tall, width, tall, 0x78939a)
                    c.rect(bx - width / 2 + 1, horizon - tall + 1, 1, tall - 1, 0x9eb2b3)
                }
                steppedTower(c, x(.24f), horizon, max(7, horizon - 2), max(5, c.width / 12), 0xc7c1ad)
                val crown = x(.78f)
                c.rect(crown - 3, horizon - horizon * 2 / 3, 7, horizon * 2 / 3, 0xb0ada0)
                for (i in 0..3) c.rect(crown - 3 + i, horizon - horizon * 2 / 3 - i, 7 - i * 2, 1, 0xcbd6d4)
                c.line(crown, 1, crown, horizon - horizon * 2 / 3 - 2, STONE)
            }
            Circuit.CHICAGO -> {
                c.rect(0, horizon - 3, c.width, 3, 0x428fa7)
                for (i in 0..9) {
                    val bx = x(i / 11f)
                    val tall = 3 + i * 7 % max(4, horizon / 2)
                    c.rect(bx - 2, horizon - tall, 5, tall, 0x859c9b)
                }
                val tower = x(.26f)
                val unit = max(2, c.width / 55)
                for (i in -1..1) {
                    val tall = horizon - 2 - abs(i) * 3
                    c.rect(tower + i * unit, horizon - tall, unit, tall, 0x354950)
                    c.line(tower + i * unit, horizon - tall + 1, tower + i * unit, horizon, 0x617676)
                }
                c.line(tower, 0, tower, 3, STONE)
                c.line(tower + unit - 1, 0, tower + unit - 1, 3, STONE)
                for (fraction in listOf(.62f, .73f)) {
                    val bx = x(fraction)
                    val tall = max(5, horizon * 2 / 3)
                    c.rect(bx - 2, horizon - tall, 5, tall, 0x6c7e7c)
                    for (y in horizon - tall until horizon step 2) c.rect(bx - 3, y, 7, 1, 0xd8cfb5)
                }
            }
            else -> Unit
        }
    }

    private fun bridge(c: PixelCanvas, center: Int, horizon: Int, width: Int) {
        val left = center - width / 3
        val right = center + width / 3
        val deck = horizon - 2
        val top = max(0, horizon / 7)
        val thick = max(1, c.width / 90)
        c.rect(center - width / 2, deck, width, 2, 0xb84d36)
        for (tower in listOf(left, right)) {
            c.rect(tower - thick - 1, top, thick, horizon - top, 0xc95237)
            c.rect(tower + 1, top, thick, horizon - top, 0xc95237)
            for (y in top..deck step max(2, (deck - top) / 3)) c.rect(tower - thick - 1, y, thick * 2 + 2, 1, 0xd95d3b)
        }
        for (px in left..right) {
            val fraction = (px - left).toFloat() / max(1, right - left)
            val cable = top + ((deck - top - 1) * (1 - (2 * fraction - 1).pow(2))).roundToInt()
            c.pixel(px, cable, 0xd95d3b)
            if ((px - left) % 3 == 0) c.line(px, cable, px, deck, 0xe88760)
        }
        c.line(center - width / 2, deck, left, top, 0xd95d3b)
        c.line(right, top, center + width / 2, deck, 0xd95d3b)
    }

    private fun steppedTower(c: PixelCanvas, x: Int, base: Int, height: Int, width: Int, color: Int) {
        for (i in 0..3) {
            val w = max(1, width - i * 2)
            val top = base - height * (4 + i) / 8
            c.rect(x - w / 2, top, w, base - top, color)
            if (w > 3) c.line(x - w / 2 + 1, top + 1, x - w / 2 + 1, base, GLASS)
        }
        c.line(x, base - height - 2, x, base - height * 7 / 8, STONE)
    }

    fun roadside(
        c: PixelCanvas,
        circuit: Circuit,
        track: Track,
        distance: Float,
        rear: Boolean,
        horizon: Int,
        centers: FloatArray,
        scales: FloatArray,
        distances: FloatArray,
    ) {
        if (circuit !in listOf(Circuit.SAN_FRANCISCO, Circuit.SILICON_VALLEY, Circuit.NEW_YORK, Circuit.CHICAGO)) return
        val sign = if (rear) -1f else 1f
        for (y in horizon until c.height) {
            val scale = scales[y]
            val center = centers[y]
            val block = (track.wrap(distance + sign * distances[y]) / 12).toInt()
            val progress = track.wrap(distance + sign * distances[y]) / track.length
            for (side in listOf(-1, 1)) {
                val screenSide = side * sign
                val inner = center + screenSide * (track.barrier + .8f) * scale
                val outer = center + screenSide * 24f * scale
                val paving = if (block % 2 == 0) 0xc8c4b4 else 0xb9b7aa
                c.rect(min(inner, outer).toInt(), y, abs(outer - inner).roundToInt().coerceAtLeast(1), 1, paving)
                c.pixel(inner.toInt(), y, STONE)
                if (circuit == Circuit.CHICAGO && side == 1) {
                    val shore = center + screenSide * 25f * scale
                    if (screenSide > 0) c.rect(shore.toInt(), y, c.width, 1, 0x428fa7) else c.rect(0, y, shore.toInt(), 1, 0x428fa7)
                }
                if (circuit == Circuit.SAN_FRANCISCO && side == -1 && bayfront(progress)) {
                    val shore = center + screenSide * 24f * scale
                    val water = if (block % 3 == 0) 0x63999b else 0x578e93
                    if (screenSide > 0) c.rect(shore.toInt(), y, c.width, 1, water) else c.rect(0, y, shore.toInt(), 1, water)
                }
            }
        }
        // Equal world-distance spacing keeps buildings stationary on the course,
        // including when the rear camera reverses the projection.
        val count = (track.length / 23f).roundToInt().coerceAtLeast(1)
        val stations = (0 until count).mapNotNull { index ->
            val ahead = track.relativeDistance((index + .45f) * track.length / count, distance) * sign
            if (ahead in 0f..155f) index to ahead else null
        }.sortedByDescending { it.second }
        for ((index, ahead) in stations) {
            val y = (horizon until c.height - 4).minBy { abs(distances[it] - ahead) }
            val scale = scales[y]
            val progress = (index + .45f) / count
            for (side in listOf(-1, 1)) {
                val screenSide = (side * sign).toInt()
                val x = (centers[y] + screenSide * 23f * scale).roundToInt()
                val size = max(2, (12f * scale).roundToInt())
                when (circuit) {
                    Circuit.SAN_FRANCISCO -> {
                        if (side == -1 && bayfront(progress)) {
                            waterfront(c, centers[y], y, scale, screenSide, index)
                        } else {
                            house(c, x, y, size, max(4, ((12 + index % 3 * 2) * scale).roundToInt()), index + if (side < 0) 0 else 2, screenSide)
                        }
                    }
                    Circuit.SILICON_VALLEY -> {
                        campus(c, x, y, max(4, (21f * scale).roundToInt()), max(3, (8f * scale).roundToInt()), screenSide)
                        tree(c, (centers[y] + screenSide * 16f * scale).roundToInt(), y, max(2, (5f * scale).roundToInt()))
                    }
                    Circuit.NEW_YORK -> {
                        if (side == 1 && index % 11 in 5..8) {
                            tree(c, x, y, max(3, (8f * scale).roundToInt()))
                        } else {
                            block(c, x, y, size, max(5, ((21 + index % 4 * 5) * scale).roundToInt()), index, screenSide, false)
                        }
                    }
                    Circuit.CHICAGO -> {
                        if (side == -1) {
                            block(c, x, y, size, max(5, ((15 + index % 3 * 4) * scale).roundToInt()), index, screenSide, true)
                            railway(c, (centers[y] + screenSide * 17.5f * scale).roundToInt(), y, scale, index)
                        } else {
                            tree(c, (centers[y] + screenSide * 18f * scale).roundToInt(), y, max(2, (5f * scale).roundToInt()))
                        }
                    }
                    else -> Unit
                }
            }
        }
    }

    private fun bayfront(progress: Float) = progress > .88f || progress < .22f

    private fun waterfront(c: PixelCanvas, center: Float, base: Int, scale: Float, side: Int, index: Int) {
        val edge = (center + side * 23f * scale).roundToInt()
        val rail = max(1, (2f * scale).roundToInt())
        val span = max(2, (12f * scale).roundToInt())
        c.line(edge - span / 2, base - rail, edge + span / 2, base - rail, 0x8b9a91)
        c.line(edge, base - rail, edge, base, 0x8b9a91)
        if (index % 4 == 0) {
            val end = (center + side * 35f * scale).roundToInt()
            c.rect(min(edge, end), base, abs(end - edge), max(1, scale.roundToInt()), 0xbda98b)
            val boat = (center + side * 43f * scale).roundToInt()
            val width = max(3, (8f * scale).roundToInt())
            c.rect(boat - width / 2, base - max(1, (2f * scale).roundToInt()), width, max(1, scale.roundToInt()), STONE)
            c.rect(boat - width / 4, base - max(2, (4f * scale).roundToInt()), max(1, width / 2), max(1, (2f * scale).roundToInt()), 0x658087)
        }
    }

    private fun house(c: PixelCanvas, x: Int, base: Int, width: Int, height: Int, index: Int, side: Int) {
        val left = x - width / 2
        val top = base - height
        val trim = max(1, width / 10)
        c.rect(left, top, width, height, houses[index % houses.size])
        c.rect(if (side > 0) left + width - trim else left, top, trim, height, 0xa38e7b)
        for (dy in 0..max(1, width / 5)) c.rect(left + dy, top - dy, max(1, width - dy * 2), 1, 0x78685b)
        c.rect(left, top + 1, width, trim, STONE)
        val bay = max(2, width / 3)
        val bayX = x - bay / 2
        c.rect(bayX - 1, top + height / 4, bay + 2, height * 2 / 3, STONE)
        for (floor in 0..1) {
            val wy = top + height / 4 + floor * height / 3
            c.rect(bayX, wy + 1, bay, max(1, height / 5), GLASS)
            if (bay > 3) c.line(x, wy + 1, x, wy + max(1, height / 5), STONE)
            c.rect(left + trim, wy + 1, max(1, width / 6), max(1, height / 5), GLASS)
        }
        c.rect(left + trim, base - max(2, height / 4), max(1, width / 5), max(2, height / 4), 0x6d675b)
        c.rect(left, base, width, 1, STONE)
    }

    private fun campus(c: PixelCanvas, x: Int, base: Int, width: Int, height: Int, side: Int) {
        val left = x - width / 2
        val top = base - height
        c.rect(left, top, width, height, 0xcdd6c5)
        c.rect(left + 1, top - max(1, height / 4), width - 2, max(1, height / 4), 0x294c62)
        for (px in left + 2 until left + width - 1 step max(2, width / 5)) c.line(px, top - max(1, height / 4), px, top - 1, 0x688b96)
        c.rect(left, top + max(1, height / 4), width, max(1, height / 2), 0x537f89)
        for (px in left + 2 until left + width step max(3, width / 6)) c.line(px, top + 1, px, base - 1, 0xcdd6c5)
        c.rect(if (side > 0) left else left + width - 2, base - max(2, height / 2), 2, max(2, height / 2), 0x33565d)
    }

    private fun block(c: PixelCanvas, x: Int, base: Int, width: Int, height: Int, index: Int, side: Int, chicago: Boolean) {
        val left = x - width / 2
        val top = base - height
        c.rect(left, top, width, height, if (chicago) if (index % 2 == 0) 0xac7b60 else 0xc7b99c else masonry[index % masonry.size])
        c.rect(if (side > 0) left + width - max(1, width / 5) else left, top, max(1, width / 5), height, 0x766e61)
        c.rect(left - 1, top - 1, width + 2, 1, 0x617575)
        val floor = max(3, height / (if (chicago) 5 else 7))
        for (y in top + 2 until base - floor step floor) {
            for (wx in left + 1 until left + width - 1 step max(2, width / 4)) c.rect(wx, y, max(1, width / 7), max(1, floor - 2), 0x38545d)
        }
        c.rect(left + 1, base - floor, max(1, width - 2), floor, 0x38545d)
        c.rect(left, base - floor - 1, width, max(1, floor / 3), if (index % 2 == 0) 0x98604c else 0xd3b36d)
        c.line(x, base - floor + 1, x, base, STONE)
    }

    private fun tree(c: PixelCanvas, x: Int, base: Int, height: Int) {
        c.line(x, base - height / 2, x, base, 0x796f55)
        val radius = max(1, height / 3)
        for (y in -radius..radius) {
            val half = max(1, radius - abs(y) / 2)
            c.rect(x - half, base - height + radius + y, half * 2 + 1, 1, if (y < 0) 0x6f9464 else TREE)
        }
    }

    private fun railway(c: PixelCanvas, x: Int, base: Int, scale: Float, index: Int) {
        val level = base - max(3, (8f * scale).roundToInt())
        val width = max(4, (18f * scale).roundToInt())
        c.rect(x - width / 2, level, width, max(1, scale.roundToInt()), 0x5c6e6d)
        c.line(x, level, x, base, 0x6a7b77)
        c.line(x - width / 3, level, x, level + max(1, (3 * scale).roundToInt()), 0x6a7b77)
        if (index % 5 in 1..3) {
            val tall = max(2, (3.5f * scale).roundToInt())
            c.rect(x - width / 2, level - tall, width - 1, tall, 0xddd7bb)
            c.rect(x - width / 2 + 1, level - tall + 1, width - 3, max(1, tall / 2), 0x4a6970)
            for (wx in x - width / 2 + 2 until x + width / 2 - 1 step max(2, (3 * scale).roundToInt())) c.line(wx, level - tall, wx, level - 1, 0xddd7bb)
            c.rect(x - width / 2, level - 1, width - 1, 1, 0xba6749)
        }
    }
}
