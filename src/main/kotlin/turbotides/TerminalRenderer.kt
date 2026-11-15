package turbotides

import javax.imageio.ImageIO
import kotlin.math.*

private const val INK = 0x102b35
private const val CREAM = 0xffedce
private const val ORANGE = 0xff653b
private const val TEAL = 0x32b7ae

/** Two pixels per cell: ordinary UTF-8 half blocks and ANSI truecolor, no image protocol. */
class PixelCanvas(val width: Int, val height: Int, background: Int) {
    private val pixels = IntArray(width * height) { background }
    internal fun colorAt(x: Int, y: Int): Int = pixels[y * width + x]
    fun pixel(x: Int, y: Int, color: Int) {
        if (x in 0 until width && y in 0 until height) pixels[y * width + x] = color
    }
    fun rect(x: Int, y: Int, w: Int, h: Int, color: Int) {
        for (py in max(0, y) until min(height, y + h)) for (px in max(0, x) until min(width, x + w)) pixel(px, py, color)
    }
    fun line(x0: Int, y0: Int, x1: Int, y1: Int, color: Int) {
        val steps = max(abs(x1 - x0), abs(y1 - y0)).coerceAtLeast(1)
        for (i in 0..steps) pixel(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps, color)
    }
    fun sprite(name: String, x: Int, y: Int, w: Int, h: Int) {
        val img = sprites.getValue(name)
        // Reuse the same portrait crop as the original game. Goldie is a single sprite.
        val sw = if (name == "phippy") 24 else img.width
        val sh = if (name == "phippy") 30 else img.height
        for (py in 0 until h) {
            for (px in 0 until w) {
                val color = img.getRGB((if (name == "phippy") 20 else 0) + px * sw / w, py * sh / h)
                if (color ushr 24 > 128) pixel(x + px, y + py, color and 0xffffff)
            }
        }
    }
    fun ansi(): List<String> = (0 until height / 2).map { y ->
        buildString {
            var fg = -1
            var bg = -1
            for (x in 0 until width) {
                val top = pixels[y * 2 * width + x]
                val bottom = pixels[(y * 2 + 1) * width + x]
                if (top != fg) {
                    append(color(top, false))
                    fg = top
                }
                if (bottom != bg) {
                    append(color(bottom, true))
                    bg = bottom
                }
                // A solid cell needs no Unicode glyph. This preserves both pixels
                // and avoids tui4j's per-grapheme ICU work for most of the image.
                append(if (top == bottom) ' ' else '▀')
            }
            append("\u001b[0m")
        }
    }
    companion object {
        private val sprites by lazy { listOf("phippy", "goldie").associateWith { ImageIO.read(PixelCanvas::class.java.getResourceAsStream("/art/$it.png")) } }
        private val indexedColor = System.getenv("TURBOTIDES_COLOR") == "256" || (System.getenv("TERM_PROGRAM") == "Apple_Terminal" && System.getenv("TURBOTIDES_COLOR") != "truecolor")
        fun color(rgb: Int, background: Boolean = false): String {
            if (indexedColor) return "\u001b[${if (background) 48 else 38};5;${indexed(rgb)}m"
            return "\u001b[${if (background) 48 else 38};2;${rgb shr 16 and 255};${rgb shr 8 and 255};${rgb and 255}m"
        }
        private val indexedCache = java.util.concurrent.ConcurrentHashMap<Int, Int>()
        internal fun indexed(rgb: Int): Int = indexedCache.computeIfAbsent(rgb) {
            val levels = intArrayOf(0, 95, 135, 175, 215, 255)
            val channels = intArrayOf(rgb shr 16 and 255, rgb shr 8 and 255, rgb and 255)
            val indices = channels.map { channel -> levels.indices.minBy { abs(levels[it] - channel) } }
            val cubeError = channels.indices.sumOf { (channels[it] - levels[indices[it]]).toDouble().pow(2) }
            val gray = ((channels.average() - 8) / 10).roundToInt().coerceIn(0, 23)
            val grayError = channels.sumOf { (it - (8 + gray * 10)).toDouble().pow(2) }
            if (grayError < cubeError) 232 + gray else 16 + indices[0] * 36 + indices[1] * 6 + indices[2]
        }
    }
}

class TerminalRenderer {
    fun render(game: TerminalGame): String {
        val w = game.width.coerceIn(1, 180)
        val h = game.height.coerceIn(1, 65)
        if (game.tooSmall) return listOf("Turbo Tides TUI", "Resize to at least 64 x 24.", "Race paused. Q quits.").take(h).joinToString("\n") { it.take(w) }
        val race = game.race
        val lines = mutableListOf<String>()
        lines += text("  TURBO TIDES   ${game.circuit.title}  ·  ${game.circuit.route}", w, CREAM, INK)
        lines += text(if (race.phase == Phase.GARAGE) "  Three laps · six racers · ${game.difficulty.title} pace     Best ${time(game.records.best(game.circuit, game.difficulty))}" else "  ${race.position}/6   Lap ${race.lap}/3   ${time(race.elapsed)}   ${(race.player.speed * 3.6f).roundToInt()} km/h   Nitro ${race.nitro.toInt()}%", w, CREAM, INK)
        val artHeight = (h - if (race.phase == Phase.GARAGE) 10 else 9) * 2
        val canvas = PixelCanvas(w, artHeight, INK)
        if (race.phase == Phase.GARAGE && game.overview) map(canvas, game) else road(canvas, game)
        val art = canvas.ansi().toMutableList()
        if (game.help) {
            overlay(art, w, listOf("Driving in a terminal", "W / Up: throttle on     S / Down: brake", "A / Left: steer left    D / Right: steer right", "Tap to nudge; keyboard repeat sustains steering.", "Space: drift mode; steer >0.45s to charge nitro.", "B: nitro mode   C: rear view (steering mirrored)", "Esc: pause / resume   R: restart   Q: quit", "M: sound   N: reduced motion   ?: help", "G: garage while paused or finished", "Throttle, drift, boost and rear view are modes.", "Focus loss pauses if your terminal reports it.", "Enter / Esc / ?: close help; then resume."))
        } else {
            when (race.phase) {
                Phase.COUNTDOWN -> overlay(art, w, listOf("${ceil(race.countdown).toInt().coerceAtLeast(1)}", "W / Up to arm throttle · Get ready!"))
                Phase.PAUSED -> overlay(art, w, listOf("Race paused", "Enter / Esc: resume   R: restart   G: garage", "Driving modes cleared. W / Up to accelerate."))
                Phase.FINISHED -> overlay(
                    art,
                    w,
                    listOf(
                        "Finished ${race.position}/6 · ${time(race.elapsed)}",
                        when {
                            game.newBest -> "New personal best!"
                            game.records.pendingBest(game.circuit, game.difficulty) == race.elapsed -> "Personal best pending save; check the warning below."
                            else -> "Every finish counts. Try another racing line."
                        },
                        "Best lap ${time(race.bestLap)} · Pads ${race.pads} · Drifts ${race.driftBonuses}",
                        race.order.joinToString("  ") { it.name },
                        "Enter / R: retry   Esc / G: garage",
                    ),
                )
                else -> Unit
            }
        }
        lines += art
        if (race.phase == Phase.GARAGE) {
            val labels = listOf("Circuit  < ${game.circuit.title} >", "Paint    < ${PAINT_NAMES[game.paint]} >", "Rivals   < ${game.difficulty.title} >", "Start race  [Enter]")
            labels.forEachIndexed { index, label -> lines += text(" ${if (game.menuFocus == index) "▶" else " "} $label", w, if (game.menuFocus == index) INK else CREAM, if (game.menuFocus == index) TEAL else INK) }
            lines += text("  ↑↓ / W S / Tab: select   ←→ / A D: change   P: preview", w)
        } else {
            val mode = if (game.input.throttle) {
                "THROTTLE"
            } else if (game.input.brake) {
                "BRAKE"
            } else {
                "COAST"
            }
            lines += text("  $mode   Drift ${on(game.input.drift)}   Nitro ${on(game.input.boost)}   ${if (game.input.rearView) "REAR VIEW · mirrored" else "Forward view"}", w, if (race.boosting) TEAL else CREAM)
            val message = if (race.messageTime > 0) {
                race.message
            } else if (abs(race.player.lane) > race.track.roadHalfWidth) {
                "Grass slows you down — steer back onto the road"
            } else {
                "Mint strips add turbo. Drift + steer, then exit drift to bank nitro."
            }
            lines += text("  $message", w, ORANGE)
            lines += text("  W/↑ gas  S/↓ brake  A D/←→ steer  Space drift  B nitro", w)
            lines += text("  C rear  Esc pause  R restart  M sound  N motion  ? help  Q quit", w)
        }
        lines += text("  ${if (game.muted) "Muted" else game.audioStatus} · Motion ${if (game.reducedMotion) "reduced" else "full"} · ? help · Q quit", w, TEAL)
        lines += text("  ${game.records.error ?: game.diagnosticError ?: "Local records only · Turbo Tides terminal edition"}", w, if (game.records.error != null || game.diagnosticError != null) ORANGE else 0x8fb0b7)
        return lines.take(h - 1).joinToString("\n")
    }
    private fun on(value: Boolean) = if (value) "ON" else "off"
    private fun text(value: String, w: Int, fg: Int = CREAM, bg: Int = INK) = PixelCanvas.color(fg) + PixelCanvas.color(bg, true) + value.take(w).padEnd(w) + "\u001b[0m"
    private fun overlay(lines: MutableList<String>, w: Int, content: List<String>) {
        val top = ((lines.size - content.size) / 2).coerceAtLeast(0)
        content.take(lines.size).forEachIndexed { i, s -> lines[top + i] = text(s.take(w).padStart((w + s.length.coerceAtMost(w)) / 2), w) }
    }
    private fun map(c: PixelCanvas, game: TerminalGame) {
        val track = game.race.track
        val xScale = (c.width * 0.62f) / (track.maxX - track.minX)
        val yScale = (c.height - 8f) / (track.maxZ - track.minZ)
        fun point(distance: Float): Pair<Int, Int> {
            val p = track.frame(distance).center
            return (4 + (p.x - track.minX) * xScale).toInt() to (4 + (p.z - track.minZ) * yScale).toInt()
        }
        for (i in 0..500) {
            val (x, y) = point(track.length * i / 500f)
            c.rect(x - 1, y - 1, 3, 3, 0x38545c)
        }
        for (i in 0..500) {
            val (x, y) = point(track.length * i / 500f)
            c.pixel(x, y, game.circuit.accent.toInt(16))
        }
        for (i in 0..2) {
            val (x, y) = point(track.padDistance(i))
            c.rect(x - 1, y - 1, 3, 3, TEAL)
        }
        val (x, y) = point(0f)
        c.rect(x - 1, y - 1, 3, 3, CREAM)
        c.sprite("phippy", (c.width * .76).toInt(), c.height / 2 - 13, 15, 20)
        c.sprite("goldie", (c.width * .82).toInt(), c.height / 2 + 5, 8, 12)
        c.line((c.width * .73).toInt(), c.height - 3, c.width - 4, c.height - 3, TEAL)
    }

    internal fun road(c: PixelCanvas, game: TerminalGame) {
        val race = game.race
        val track = race.track
        val rear = game.input.rearView
        val sign = if (rear) -1f else 1f
        val frame = track.frame(race.player.distance)
        val horizon = (c.height * .27f).toInt()
        val playerY = c.height - 5
        val sky = when (game.circuit) {
            Circuit.CINDER -> 0xecaa78
            Circuit.NEW_YORK, Circuit.CHICAGO -> 0x8fbac6
            else -> 0xf7c594
        }
        c.rect(0, 0, c.width, horizon, sky)
        c.rect(c.width * 3 / 4, 2, 5, 5, 0xffedce)
        scenery(c, game.circuit, horizon)
        val centers = FloatArray(c.height)
        val scales = FloatArray(c.height)
        val distances = FloatArray(c.height)
        for (y in horizon until c.height) {
            val t = (y - horizon + 1f) / (c.height - horizon)
            val depth = (y - horizon).toFloat() / (playerY - horizon)
            val ahead = if (y <= playerY) 160f * (1f - depth).pow(2) else -(y - playerY) * 2f
            val p = track.frame(race.player.distance + sign * ahead).center - frame.center
            val lateral = (p.x * frame.right.x + p.z * frame.right.z) * sign
            val scale = (c.width * .32f / track.roadHalfWidth) * t
            val center = c.width / 2f + (lateral * scale * .65f).coerceIn(-c.width * .65f, c.width * .65f)
            centers[y] = center
            scales[y] = scale
            distances[y] = ahead
            val stripe = (track.wrap(race.player.distance + sign * ahead) / 7).toInt() % 2 == 0
            val ground = when (game.circuit) {
                Circuit.CINDER -> if (stripe) 0x995137 else 0xa85c40
                Circuit.SUNSET -> if (stripe) 0x279b91 else 0x268d85
                else -> if (stripe) 0x3a7162 else 0x3e7969
            }
            c.rect(0, y, c.width, 1, ground)
            val half = track.roadHalfWidth * scale
            c.rect((center - half - scale * 1.5f).toInt(), y, (half * 2 + scale * 3).toInt().coerceAtLeast(1), 1, if (stripe) CREAM else ORANGE)
            c.rect((center - half).toInt(), y, (half * 2).toInt().coerceAtLeast(1), 1, if (stripe) 0x374851 else 0x3b4d57)
            if (stripe) for (lane in listOf(-3f, 3f)) c.rect((center + lane * scale).toInt(), y, max(1, (scale * .15).toInt()), 1, 0xc2c4b5)
            for (i in 0..2) {
                if (abs(track.relativeDistance(race.player.distance + sign * ahead, track.padDistance(i))) < 3f) {
                    c.rect((center + (track.padLane(i) * sign - 2.2f) * scale).toInt(), y, max(1, (4.4f * scale).toInt()), 1, TEAL)
                }
            }
            if (track.wrap(race.player.distance + sign * ahead) < 2.8f) {
                for (x in (center - half).toInt()..(center + half).toInt()) c.pixel(x, y, if ((x / 2 + y) % 2 == 0) CREAM else INK)
            }
        }
        race.rivals.sortedByDescending { track.relativeDistance(it.distance, race.player.distance) * sign }.forEach { rival ->
            val delta = track.relativeDistance(rival.distance, race.player.distance) * sign
            if (delta > -5 && delta < 160) {
                val y = (horizon until c.height).minBy { abs(distances[it] - delta) }
                val x = (centers[y] + rival.lane * sign * scales[y]).toInt()
                car(c, x, y, max(1, scales[y].roundToInt()), PAINTS[rival.paint].toInt(16), false)
            }
        }
        // Fixed road-centred camera makes forward steering unambiguously screen-relative.
        val playerX = (centers[playerY] + race.player.lane * sign * scales[playerY]).roundToInt()
        val lean = if (game.reducedMotion) 0 else (race.player.lateralSpeed * sign * .12f).roundToInt()
        if (race.boosting && !game.reducedMotion) {
            c.rect(playerX - 2, playerY + 3, 2, 2, TEAL)
            c.rect(playerX + 1, playerY + 3, 2, 2, TEAL)
        }
        car(c, playerX, playerY, max(2, scales[playerY].roundToInt()), PAINTS[game.paint].toInt(16), true, lean)
        if (race.drifting) {
            c.pixel(playerX - 4, playerY + 2, CREAM)
            c.pixel(playerX + 4, playerY + 2, CREAM)
        }
    }
    private fun car(c: PixelCanvas, x: Int, y: Int, size: Int, paint: Int, player: Boolean, lean: Int = 0) {
        c.rect(x - size - 1, y - 1, size * 2 + 3, 4, INK)
        c.rect(x - size, y - 2, size * 2 + 1, 5, paint)
        c.rect(x - size + 1 + lean, y - 3, max(1, size * 2 - 1), 2, 0x193c4c)
        c.rect(x - size, y + 1, 1, 1, CREAM)
        c.rect(x + size, y + 1, 1, 1, CREAM)
        if (player) c.pixel(x, y, CREAM)
    }
    private fun scenery(c: PixelCanvas, circuit: Circuit, horizon: Int) {
        when (circuit) {
            Circuit.SUNSET -> {
                for (x in listOf(c.width / 8, c.width * 7 / 8)) {
                    c.line(x, horizon, x + 1, 3, 0x755748)
                    c.line(x - 5, 4, x + 5, 3, 0x266d60)
                    c.line(x - 3, 1, x + 4, 6, 0x266d60)
                }
            }
            Circuit.CINDER -> for (x in 0 until c.width step 17) {
                for (dy in 0..8) c.rect(x - dy, horizon - 8 + dy, dy * 2 + 6, 1, 0xa35f43)
            }
            Circuit.SAN_FRANCISCO -> {
                for (x in listOf(c.width / 5, c.width * 4 / 5)) {
                    c.rect(x, 1, 2, horizon, 0xb94432)
                    c.rect(x - 2, 3, 6, 1, ORANGE)
                }
                c.line(c.width / 5, 2, c.width / 2, horizon - 2, ORANGE)
                c.line(c.width / 2, horizon - 2, c.width * 4 / 5, 2, ORANGE)
            }
            Circuit.SILICON_VALLEY -> {
                c.rect(c.width / 10, horizon - 4, c.width / 3, 4, 0xddd3b0)
                c.rect(c.width / 10 + 2, horizon - 5, c.width / 3 - 4, 2, 0x426c7c)
            }
            else -> for (x in 0 until c.width step 7) {
                val tall = 3 + (x * 17 % max(4, horizon - 2))
                c.rect(x, horizon - tall, 5, tall, 0x3d6273)
                for (y in horizon - tall + 1 until horizon step 3) {
                    c.pixel(x + 1, y, CREAM)
                    c.pixel(x + 3, y, CREAM)
                }
                if (circuit == Circuit.CHICAGO && x == 14) {
                    c.line(x, 0, x, horizon, INK)
                    c.line(x + 3, 0, x + 3, horizon, INK)
                }
            }
        }
    }
    companion object {
        fun time(value: Float?): String {
            if (value == null) return "--:--.--"
            val centiseconds = (value * 100).roundToLong().coerceAtLeast(0)
            return "%d:%02d.%02d".format(java.util.Locale.ROOT, centiseconds / 6000, (centiseconds / 100) % 60, centiseconds % 100)
        }
    }
}
