package turbotides

import kotlin.math.*

data class Point3(val x: Float, val y: Float, val z: Float) {
    operator fun plus(other: Point3) = Point3(x + other.x, y + other.y, z + other.z)
    operator fun minus(other: Point3) = Point3(x - other.x, y - other.y, z - other.z)
    operator fun times(scale: Float) = Point3(x * scale, y * scale, z * scale)
    fun length() = sqrt(x * x + y * y + z * z)
    fun normal(): Point3 = this * (1f / length().coerceAtLeast(0.0001f))
}

data class RoadFrame(val center: Point3, val forward: Point3) {
    // Camera-right is forward cross world-up. This convention is shared by
    // steering, road geometry, turbo pads and the chase camera.
    val right = Point3(-forward.z, 0f, forward.x).normal()
    val heading = atan2(forward.x, forward.z) * 180f / PI.toFloat()
    fun at(lane: Float, height: Float = 0f) = center + right * lane + Point3(0f, height, 0f)
}

enum class Circuit(val title: String, val route: String, val description: String, val accent: String, val previewAngle: Float) {
    SUNSET("Sunset Run", "Coastal circuit", "Palm-lined bends above a warm turquoise sea.", "ff9c6a", 0.4f),
    CINDER("Cinder Ring", "Canyon circuit", "Rolling red-rock climbs and tightening corners.", "e7b27b", 0.5f),
    SAN_FRANCISCO("San Francisco", "Golden Gate Run", "Cross the orange bridge, then climb the city hills.", "ff8963", 0.15f),
    SILICON_VALLEY("Silicon Valley", "Campus Sprint", "Sweep past solar roofs and the circular campus.", "a3d788", 0.6f),
    NEW_YORK("New York City", "Midtown Mile", "Four city blocks, a green park and a towering skyline.", "f1cf65", 0.8f),
    CHICAGO("Chicago", "Lakeshore Loop", "Race beneath the elevated train beside Lake Michigan.", "8ed3e6", 0.15f),
}

class Track(val circuit: Circuit) {
    val roadHalfWidth = 9f
    val barrier = 13f
    private val points: List<Point3>
    private val distances: FloatArray
    val length: Float
    val minX: Float
    val maxX: Float
    val minZ: Float
    val maxZ: Float
    val elevation: Float
    val center: Point3
    val radius: Float

    init {
        // Dense source samples are indexed by distance, not angle: speed stays
        // constant even through differently sized bends and elevated sections.
        points = (0..1024).map { i ->
            val angle = i / 1024f * PI.toFloat() * 2f
            when (circuit) {
                Circuit.SUNSET -> Point3(
                    170f * cos(angle) + 26f * cos(3f * angle),
                    7f + 4.5f * sin(2f * angle),
                    122f * sin(angle) + 16f * sin(3f * angle),
                )
                Circuit.CINDER -> Point3(
                    154f * cos(angle) + 33f * cos(2f * angle),
                    12f + 8f * sin(3f * angle),
                    133f * sin(angle) + 24f * sin(2f * angle),
                )
                Circuit.SAN_FRANCISCO -> Point3(
                    182f * cos(angle) + 20f * cos(2f * angle),
                    12f + 30f * ((1f - cos(angle)) / 2f).pow(2),
                    146f * sin(angle) + 10f * sin(3f * angle),
                )
                Circuit.SILICON_VALLEY -> Point3(
                    207f * cos(angle) + 22f * cos(2f * angle),
                    8f + 3f * sin(2f * angle),
                    131f * sin(angle) + 9f * sin(3f * angle),
                )
                Circuit.NEW_YORK -> Point3(
                    180f * (cos(angle) - 0.09f * cos(3f * angle)),
                    7f + 1.2f * sin(2f * angle),
                    163f * (sin(angle) + 0.09f * sin(3f * angle)),
                )
                Circuit.CHICAGO -> Point3(
                    141f * cos(angle) + 12f * cos(3f * angle),
                    9f + 3f * sin(2f * angle),
                    206f * sin(angle),
                )
            }
        }
        distances = FloatArray(points.size)
        for (i in 1..points.lastIndex) distances[i] = distances[i - 1] + (points[i] - points[i - 1]).length()
        length = distances.last()
        minX = points.minOf { it.x }
        maxX = points.maxOf { it.x }
        minZ = points.minOf { it.z }
        maxZ = points.maxOf { it.z }
        elevation = points.maxOf { it.y } - points.minOf { it.y }
        center = Point3((minX + maxX) / 2f, points.map { it.y }.average().toFloat(), (minZ + maxZ) / 2f)
        radius = max(maxX - minX, maxZ - minZ) / 2f
    }

    fun wrap(distance: Float): Float = ((distance % length) + length) % length

    private fun point(distance: Float): Point3 {
        val d = wrap(distance)
        val search = distances.binarySearch(d)
        val index = (if (search >= 0) search else -search - 2).coerceIn(0, points.lastIndex - 1)
        val fraction = (d - distances[index]) / (distances[index + 1] - distances[index])
        return points[index] + (points[index + 1] - points[index]) * fraction
    }

    fun frame(distance: Float): RoadFrame = RoadFrame(point(distance), (point(distance + 0.6f) - point(distance - 0.6f)).normal())

    fun curvature(distance: Float): Float {
        val before = frame(distance - 3f).forward
        val after = frame(distance + 3f).forward
        return (before.z * after.x - before.x * after.z) / 6f
    }

    fun padDistance(index: Int) = length * (0.15f + index * 0.25f)
    fun padLane(index: Int) = if (index % 2 == 0) -3.6f else 3.6f
    fun relativeDistance(a: Float, b: Float) = wrap(a - b + length / 2f) - length / 2f
}
