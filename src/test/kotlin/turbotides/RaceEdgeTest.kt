package turbotides

import kotlin.math.abs
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Adversarial rules tests supplement actual ANSI control/playthrough evidence. */
class RaceEdgeTest {
    private fun racing(): Race = Race(Track(Circuit.SUNSET)).also { race ->
        race.start()
        repeat(420) { race.advance(Race.STEP, Controls()) }
    }

    @Test fun `a stalled terminal advances at most a tenth of a second`() {
        val normal = racing()
        val stalled = racing()
        val controls = Controls(throttle = true, boost = true, steer = 1f)
        normal.advance(0.1f, controls)
        stalled.advance(30f, controls)
        assertEquals(normal.player.distance, stalled.player.distance)
        assertEquals(normal.player.lane, stalled.player.lane)
        assertEquals(normal.elapsed, stalled.elapsed)
        val elapsed = stalled.elapsed
        stalled.advance(-5f, controls)
        assertEquals(elapsed, stalled.elapsed)
    }

    @Test fun `contacts across the lap seam push away and recover`() {
        val race = racing()
        race.player.distance = race.track.length - 1f
        race.player.lane = 0f
        race.player.speed = 40f
        race.rivals.drop(1).forEach { it.finishTime = 1f }
        race.rivals.first().distance = race.track.length + 1f
        race.rivals.first().lane = 1f
        race.advance(Race.STEP, Controls(throttle = true))
        assertEquals(1, race.bumps)
        assertTrue(race.player.speed < 35f)
        assertTrue(race.player.lateralSpeed < 0f)
        repeat(60) { race.advance(Race.STEP, Controls(throttle = true, steer = 1f)) }
        assertTrue(race.player.speed > 35f)
        assertTrue(race.player.lane > 0f)
    }

    @Test fun `chaotic valid inputs never escape the road reverse or exceed speed limits`() {
        val random = Random(814)
        for (circuit in Circuit.entries) {
            val race = Race(Track(circuit))
            race.start()
            var lastDistance = 0f
            repeat(60 * 120) {
                val controls = Controls(
                    throttle = random.nextBoolean(),
                    brake = random.nextInt(5) == 0,
                    steer = random.nextInt(-1, 2).toFloat(),
                    drift = random.nextBoolean(),
                    boost = random.nextBoolean(),
                )
                race.advance(Race.STEP, controls)
                assertTrue(race.player.distance >= lastDistance, circuit.title)
                assertTrue(race.player.speed in 0f..87f, circuit.title)
                assertTrue(abs(race.player.lane) <= 12f, circuit.title)
                assertTrue(race.nitro in 0f..100f, circuit.title)
                lastDistance = race.player.distance
            }
        }
    }
}
