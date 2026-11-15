package turbotides

import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class DifficultyTest {
    @Test fun `every difficulty step materially improves rival race times on every circuit`() {
        for (circuit in Circuit.entries) {
            val times = Difficulty.entries.map { difficulty ->
                val race = racing(circuit, difficulty)
                while (race.rivals.any { it.finishTime == null } && race.elapsed < 120f) {
                    val before = race.rivals.map { it.speed to it.distance }
                    race.advance(Race.STEP, Controls())
                    race.rivals.forEachIndexed { index, rival ->
                        val acceleration = (rival.speed - before[index].first) / Race.STEP
                        val advance = rival.distance - before[index].second
                        assertTrue(rival.speed in 0f..87f, "$circuit/$difficulty exceeded the player boost speed")
                        assertTrue(acceleration in -46.001f..40.001f, "$circuit/$difficulty acceleration $acceleration exceeded physical limits")
                        assertTrue(advance in 0f..(87f * Race.STEP + .001f), "$circuit/$difficulty jumped forward by $advance")
                        assertTrue(abs(rival.lane) < race.track.roadHalfWidth, "Rival left the driving surface")
                    }
                }
                assertTrue(race.rivals.all { it.finishTime != null }, "$circuit/$difficulty did not complete three laps")
                race.rivals.map { it.finishTime!! }
            }
            for (level in 1 until times.size) {
                assertTrue(
                    times[level].min() < times[level - 1].min() - 3f,
                    "$circuit needs a meaningful leader gap between ${Difficulty.entries[level - 1]} and ${Difficulty.entries[level]}: $times",
                )
                assertTrue(times[level].max() < times[level - 1].max() - 3f, "$circuit backmarkers must also get harder: $times")
            }
            println("${circuit.name} rival finish ranges: " + Difficulty.entries.mapIndexed { i, difficulty -> "${difficulty.name}=${times[i].min()}..${times[i].max()}" }.joinToString())
        }
    }

    @Test fun `rivals never change pace to compensate for the player position`() {
        for (difficulty in Difficulty.entries) {
            val behind = racing(Circuit.SAN_FRANCISCO, difficulty)
            val ahead = racing(Circuit.SAN_FRANCISCO, difficulty)
            behind.player.distance = -behind.track.length / 3
            ahead.player.distance = ahead.track.length * 2
            repeat(20 * 120) {
                behind.advance(Race.STEP, Controls())
                ahead.advance(Race.STEP, Controls())
            }
            assertEquals(rivalState(behind), rivalState(ahead), "$difficulty rubber-banded toward the player")
        }
    }

    @Test fun `difficulty never changes player acceleration braking steering or nitro`() {
        val races = Difficulty.entries.map { racing(Circuit.SUNSET, it) }
        // Isolate player handling from contacts; rival collisions are tested separately.
        races.forEach { race -> race.rivals.forEach { it.finishTime = 1f } }
        repeat(20 * 120) { step ->
            val controls = Controls(
                throttle = step < 18 * 120,
                brake = step >= 18 * 120,
                steer = if (step / 100 % 2 == 0) .7f else -.7f,
                drift = step / 70 % 3 == 0,
                boost = step / 70 % 3 != 0,
            )
            races.forEach { it.advance(Race.STEP, controls) }
            val expected = playerState(races.first())
            races.drop(1).forEach { assertEquals(expected, playerState(it), "Difficulty changed the player's physics") }
        }
    }

    @Test fun `rival simulation agrees across refresh rates and resets after a finished field`() {
        for (difficulty in Difficulty.entries) {
            fun simulate(hz: Int): Race = Race(Track(Circuit.CINDER), difficulty).also { race ->
                race.start()
                repeat(hz * 20) { race.advance(1f / hz, Controls()) }
            }
            val slow = simulate(30)
            val fast = simulate(144)
            slow.rivals.zip(fast.rivals).forEach { (a, b) ->
                assertEquals(a.distance, b.distance, .8f)
                assertEquals(a.speed, b.speed, .4f)
                assertEquals(a.lane, b.lane, .02f)
            }
            repeat(120 * 100) { slow.advance(Race.STEP, Controls()) }
            assertTrue(slow.rivals.all { it.finishTime != null })
            val retry = Race(slow.track, difficulty)
            retry.start()
            assertEquals(Phase.COUNTDOWN, retry.phase)
            assertEquals(difficulty, retry.difficulty)
            retry.rivals.forEach { rival ->
                assertEquals(0f, rival.speed)
                assertNull(rival.finishTime)
            }
            val frozen = rivalState(retry)
            retry.pause()
            repeat(120) { retry.advance(Race.STEP, Controls(throttle = true)) }
            assertEquals(frozen, rivalState(retry))
        }
    }

    private fun racing(circuit: Circuit, difficulty: Difficulty): Race = Race(Track(circuit), difficulty).also { race ->
        race.start()
        while (race.phase == Phase.COUNTDOWN) race.advance(Race.STEP, Controls())
    }

    private fun rivalState(race: Race): List<List<Float?>> = race.rivals.map { listOf(it.distance, it.lane, it.speed, it.finishTime) }

    private fun playerState(race: Race): List<Any> = with(race) {
        listOf(player.distance, player.speed, player.lane, player.lateralSpeed, nitro, driftCharge, pads, bumps, driftBonuses, elapsed)
    }
}
