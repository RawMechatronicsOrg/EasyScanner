package com.rawmechatronics.easyscanner

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files

class PlyCloudTest {
    /** The engine's layout: float x y z, uchar red green blue. */
    private fun enginePly(points: List<Pair<FloatArray, IntArray>>): ByteArray {
        val header = "ply\nformat binary_little_endian 1.0\nelement vertex ${points.size}\n" +
            "property float x\nproperty float y\nproperty float z\n" +
            "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
        val body = ByteBuffer.allocate(points.size * 15).order(ByteOrder.LITTLE_ENDIAN)
        for ((p, c) in points) {
            p.forEach(body::putFloat)
            c.forEach { body.put(it.toByte()) }
        }
        return header.toByteArray(Charsets.US_ASCII) + body.array()
    }

    @Test
    fun readsTheEnginesLayout() {
        val bytes = enginePly(listOf(floatArrayOf(1f, 98f, 3f) to intArrayOf(10, 20, 250), floatArrayOf(-1.5f, 100f, -9.25f) to intArrayOf(255, 0, 1)))
        val c = PlyCloud.read(ByteBuffer.wrap(bytes), 10)
        assertEquals(2, c.count)
        assertEquals(2, c.total)
        assertArrayEquals(floatArrayOf(1f, 98f, 3f, -1.5f, 100f, -9.25f), c.xyz, 0f)
        assertArrayEquals(byteArrayOf(10, 20, 250.toByte(), 255.toByte(), 0, 1), c.rgb)
    }

    @Test
    fun thinsByAStride() {
        val pts = (0 until 10).map { floatArrayOf(it.toFloat(), 0f, 0f) to intArrayOf(0, 0, 0) }
        val c = PlyCloud.read(ByteBuffer.wrap(enginePly(pts)), 4)
        assertEquals(10, c.total)
        assertEquals(4, c.count)                 // every 3rd: 0, 3, 6, 9
        assertArrayEquals(floatArrayOf(0f, 3f, 6f, 9f), FloatArray(4) { c.xyz[3 * it] }, 0f)
    }

    @Test
    fun otherOrderTypesAndNoColour() {
        val header = "ply\r\nformat binary_little_endian 1.0\r\ncomment made elsewhere\r\nelement vertex 1\r\n" +
            "property double z\r\nproperty float nx\r\nproperty double x\r\nproperty double y\r\nelement face 0\r\n" +
            "property list uchar int vertex_indices\r\nend_header\r\n"
        val body = ByteBuffer.allocate(28).order(ByteOrder.LITTLE_ENDIAN).putDouble(3.0).putFloat(9f).putDouble(1.0).putDouble(2.0)
        val c = PlyCloud.read(ByteBuffer.wrap(header.toByteArray() + body.array()), 10)
        assertArrayEquals(floatArrayOf(1f, 2f, 3f), c.xyz, 0f)
        assertArrayEquals(byteArrayOf(0xB0.toByte(), 0xB0.toByte(), 0xB0.toByte()), c.rgb)
    }

    @Test(expected = IOException::class)
    fun refusesAscii() {
        PlyCloud.read(ByteBuffer.wrap("ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nend_header\n0\n".toByteArray()), 10)
    }

    @Test(expected = IOException::class)
    fun refusesATruncatedBody() {
        val bytes = enginePly(listOf(floatArrayOf(0f, 0f, 0f) to intArrayOf(0, 0, 0)))
        PlyCloud.read(ByteBuffer.wrap(bytes.copyOf(bytes.size - 4)), 10)
    }

    @Test
    fun boundsIgnoreStrayPoints() {
        val pts = (0 until 1000).map { floatArrayOf((it % 10).toFloat(), (it / 100).toFloat(), 5f) to intArrayOf(0, 0, 0) } +
            listOf(floatArrayOf(5000f, 5000f, 5000f) to intArrayOf(0, 0, 0))
        val (centre, radius) = PlyCloud.read(ByteBuffer.wrap(enginePly(pts)), 10_000).bounds()
        assertEquals(5f, centre[2], 0f)
        assertTrue("radius $radius", radius < 20f)
    }

    @Test
    fun libraryListsSessionsAndScansNewestFirst() {
        val files = Files.createTempDirectory("lib").toFile()
        try {
            val session = File(files, "sessions/2026-10-29T10-00-00_ab").apply { mkdirs() }
            File(session, "photos").mkdirs()
            File(session, "photos/left_0001.jpg").writeBytes(byteArrayOf(1))
            File(session, "photos/.pending_x.jpg").writeBytes(byteArrayOf(1))
            File(session, "scan.ply").writeBytes(enginePly(listOf(floatArrayOf(0f, 0f, 0f) to intArrayOf(0, 0, 0))))
            File(files, "sessions/empty").mkdirs()
            val scan = File(files, "scans/scan_20261019_080936.ply").apply { parentFile!!.mkdirs() }
            scan.writeBytes(enginePly(List(3) { floatArrayOf(0f, 0f, 0f) to intArrayOf(0, 0, 0) }))
            scan.setLastModified(System.currentTimeMillis() - 86_400_000)

            val items = ScanLibrary.list(files)
            assertEquals(listOf("2026-10-29T10-00-00_ab", "scan_20261019_080936"), items.map { it.name })
            assertEquals(listOf(1, 3), items.map { it.points })
            assertEquals(1, items[0].photos.size)
            assertNull(items[1].dir)
        } finally {
            files.deleteRecursively()
        }
    }
}
