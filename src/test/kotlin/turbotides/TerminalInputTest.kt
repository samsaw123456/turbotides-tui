package turbotides

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class TerminalInputTest {
    @Test fun `steering expires and most recent opposing press wins`() {
        val input = TerminalInput()
        input.drive("a", 0)
        assertEquals(-1f, input.controls(100_000_000).steer)
        input.drive("right", 100_000_000)
        assertEquals(1f, input.controls(110_000_000).steer)
        assertEquals(0f, input.controls(290_000_000).steer)
    }

    @Test fun `brake disables throttle and boost until explicitly rearmed`() {
        val input = TerminalInput()
        input.drive("w", 0)
        input.drive("b", 0)
        assertTrue(input.controls(0).throttle)
        assertTrue(input.controls(0).boost)
        input.drive("down", 1)
        assertTrue(input.controls(1).brake)
        assertFalse(input.controls(1).throttle)
        assertFalse(input.controls(1).boost)
        input.drive("up", 2)
        assertTrue(input.controls(2).throttle)
        assertFalse(input.controls(2).brake)
    }

    @Test fun `clear removes all driving modes and repeat train does not toggle`() {
        val input = TerminalInput()
        for (key in listOf("w", "a", " ", "b", "c")) input.drive(key, 0)
        for (i in 1..10) input.drive(" ", i * 30_000_000L)
        assertTrue(input.drift)
        input.clear()
        assertEquals(Controls(), input.controls(100_000_000))
        assertFalse(input.rearView)
    }
}
