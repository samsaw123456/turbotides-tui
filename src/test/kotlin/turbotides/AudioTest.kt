package turbotides

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class AudioTest {
    private fun mixer() = PcmMixer(TerminalAudio.SOUND_NAMES.associateWith(TerminalAudio::load))

    @Test fun `original audio assets decode and produce a bounded nonzero mix`() {
        for (name in TerminalAudio.SOUND_NAMES) {
            val samples = TerminalAudio.load(name)
            assertTrue(samples.size >= 3000, name)
            assertTrue(samples.any { it != 0.toShort() }, name)
        }
        val output = ByteArray(44100)
        mixer().render(SoundState(Phase.RACING, 87f, boosting = true), output)
        assertTrue(output.any { it != 0.toByte() })
    }

    @Test fun `mute and pause silence actual samples clear cues and recover music`() {
        for (silent in listOf(SoundState(muted = true), SoundState(phase = Phase.PAUSED))) {
            val currentMixer = mixer()
            val output = ByteArray(44100)
            currentMixer.cue("finish")
            currentMixer.render(silent, output)
            assertTrue(output.all { it == 0.toByte() })
            currentMixer.render(SoundState(), output)
            val freshMusic = ByteArray(output.size)
            mixer().render(SoundState(), freshMusic)
            assertContentEquals(freshMusic, output)
        }
    }

    @Test fun `engine speed and cues audibly change the generated samples`() {
        val idle = ByteArray(44100)
        val fast = ByteArray(44100)
        mixer().render(SoundState(phase = Phase.RACING), idle)
        mixer().render(SoundState(phase = Phase.RACING, speed = 62f), fast)
        assertFalse(idle.contentEquals(fast))
        for (cue in TerminalAudio.CUE_NAMES) {
            val plain = ByteArray(44100)
            val withCue = ByteArray(44100)
            mixer().render(SoundState(), plain)
            mixer().also { it.cue(cue) }.render(SoundState(), withCue)
            assertFalse(plain.contentEquals(withCue), cue)
        }
    }
}
