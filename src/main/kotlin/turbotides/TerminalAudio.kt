package turbotides

import java.io.BufferedInputStream
import java.util.concurrent.ConcurrentLinkedQueue
import javax.sound.sampled.AudioFormat
import javax.sound.sampled.AudioSystem
import javax.sound.sampled.SourceDataLine
import kotlin.math.roundToInt

/** Plays the original Turbo Tides WAVs without blocking the terminal's update loop. */
class TerminalAudio(initialMuted: Boolean = false) : AutoCloseable {
    @Volatile private var running = true

    @Volatile private var state = SoundState(muted = initialMuted)

    @Volatile private var unavailable: String? = null

    @Volatile private var line: SourceDataLine? = null
    private val cues = ConcurrentLinkedQueue<String>()
    private val worker = Thread(::play, "turbo-tides-audio").apply {
        isDaemon = true
        start()
    }

    val status: String
        get() = unavailable?.let { "Sound unavailable: $it" }
            ?: if (state.muted) {
                "Muted"
            } else if (line == null) {
                "Sound starting"
            } else {
                "Sound on"
            }

    fun update(race: Race, muted: Boolean) {
        state = SoundState(race.phase, race.player.speed, race.boosting, muted)
        if (muted || race.phase == Phase.PAUSED) cues.clear()
    }

    fun cue(name: String, muted: Boolean = false) {
        if (!muted && !state.muted && state.phase != Phase.PAUSED && name in CUE_NAMES) cues.offer(name)
    }

    private fun play() {
        try {
            val mixer = PcmMixer(SOUND_NAMES.associateWith(::load))
            val format = AudioFormat(SAMPLE_RATE.toFloat(), 16, 1, true, false)
            val output = AudioSystem.getSourceDataLine(format)
            line = output
            output.open(format, SAMPLE_RATE / 10 * 2)
            output.start()
            val block = ByteArray(SAMPLE_RATE / 50 * 2)
            while (running) {
                val current = state
                while (true) {
                    val cue = cues.poll() ?: break
                    if (!current.muted && current.phase != Phase.PAUSED) mixer.cue(cue)
                }
                mixer.render(current, block)
                output.write(block, 0, block.size)
            }
        } catch (exception: Exception) {
            if (running) unavailable = exception.javaClass.simpleName
        } finally {
            line?.close()
            line = null
        }
    }

    override fun close() {
        running = false
        line?.close()
        worker.join(1000)
    }

    companion object {
        internal const val SAMPLE_RATE = 22050
        internal val CUE_NAMES = setOf("go", "bonus", "bump", "finish")
        internal val SOUND_NAMES = CUE_NAMES + setOf("engine", "music")

        internal fun load(name: String): ShortArray {
            val stream = requireNotNull(TerminalAudio::class.java.getResourceAsStream("/audio/$name.wav")) {
                "Missing sound: $name"
            }
            AudioSystem.getAudioInputStream(BufferedInputStream(stream)).use { wav ->
                require(wav.format.sampleRate == SAMPLE_RATE.toFloat() && wav.format.sampleSizeInBits == 16 && wav.format.channels == 1 && !wav.format.isBigEndian) {
                    "Unsupported sound format: $name"
                }
                val bytes = wav.readAllBytes()
                return ShortArray(bytes.size / 2) { index ->
                    ((bytes[index * 2].toInt() and 255) or (bytes[index * 2 + 1].toInt() shl 8)).toShort()
                }
            }
        }
    }
}

internal data class SoundState(
    val phase: Phase = Phase.GARAGE,
    val speed: Float = 0f,
    val boosting: Boolean = false,
    val muted: Boolean = false,
)

/** One deterministic PCM mixer used by the device worker and audio signal tests. */
internal class PcmMixer(private val sounds: Map<String, ShortArray>) {
    private var musicPosition = 0
    private var enginePosition = 0.0
    private val voices = mutableListOf<Voice>()

    private class Voice(val samples: ShortArray, var position: Int = 0)

    fun cue(name: String) {
        // A stuck input or repeated collision must not accumulate unbounded audio work.
        if (voices.size < 8) sounds[name]?.let { voices.add(Voice(it)) }
    }

    fun render(state: SoundState, output: ByteArray) {
        if (state.muted || state.phase == Phase.PAUSED) {
            output.fill(0)
            voices.clear()
            musicPosition = 0
            enginePosition = 0.0
            return
        }
        val racing = state.phase == Phase.RACING
        val music = sounds.getValue("music")
        val engine = sounds.getValue("engine")
        val pitch = 0.65 + state.speed / 60.0
        if (!racing) enginePosition = 0.0
        for (i in output.indices step 2) {
            var sample = music[musicPosition].toDouble() * if (racing) 0.1 else 0.18
            musicPosition = (musicPosition + 1) % music.size
            if (racing) {
                val index = enginePosition.toInt()
                val fraction = enginePosition - index
                val interpolated = engine[index] * (1.0 - fraction) + engine[(index + 1) % engine.size] * fraction
                sample += interpolated * if (state.boosting) 0.14 else 0.085
                enginePosition = (enginePosition + pitch) % engine.size
            }
            val iterator = voices.iterator()
            while (iterator.hasNext()) {
                val voice = iterator.next()
                sample += voice.samples[voice.position++] * 0.3
                if (voice.position == voice.samples.size) iterator.remove()
            }
            val pcm = sample.roundToInt().coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
            output[i] = pcm.toByte()
            output[i + 1] = (pcm shr 8).toByte()
        }
    }
}
