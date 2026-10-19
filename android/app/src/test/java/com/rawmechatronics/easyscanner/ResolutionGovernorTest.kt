package com.rawmechatronics.easyscanner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ResolutionGovernorTest {
    private val sizes = listOf(
        FrameSize(3840, 2880), FrameSize(2560, 1920), FrameSize(1920, 1440),
        FrameSize(1280, 960), FrameSize(960, 720), FrameSize(640, 480),
    )

    /** Processing cost = fixed + per-megapixel part; returns the switches made. */
    private fun run(
        gov: ResolutionGovernor, fixedMs: Double, msPerMp: Double, seconds: Double, startNs: Long = 0L,
    ): Int {
        var t = startNs
        val dt = 1_000_000_000L / 30
        var switches = 0
        repeat((seconds * 30).toInt()) {
            val s = gov.size
            if (gov.onFrame(fixedMs + msPerMp * s.width * s.height / 1e6, t) != null) switches++
            t += dt
        }
        return switches
    }

    private fun governor(start: Int = 0) = ResolutionGovernor(sizes, 30, start).also { it.reset(start, 0) }

    @Test
    fun stepsDownToTheLargestSizeThatFits() {
        // 10 ms/MP: 2560x1920 = 49 ms is over budget, 1920x1440 = 27.6 ms fits (≤ 0.92·33.3)
        val gov = governor()
        run(gov, 0.0, 10.0, 20.0)
        assertEquals(sizes[2], gov.size)
    }

    @Test
    fun climbsBackWhenThereIsHeadroom() {
        val gov = governor(start = 5)
        run(gov, 0.0, 2.0, 40.0)
        // 2 ms/MP: even 3840x2880 (11 MP → 22 ms) fits
        assertEquals(0, gov.index)
    }

    @Test
    fun climbsDespiteAFixedPerFrameCost() {
        // 10 ms fixed + 1 ms/MP: 640x480 costs 10.3 ms, which a pixel-count
        // model would extrapolate to 41 ms at 1280x960 — real cost is 11.2 ms
        val gov = governor(start = 5)
        run(gov, 10.0, 1.0, 40.0)
        assertEquals(0, gov.index)
    }

    @Test
    fun aFailedProbeIsNotRetriedSoon() {
        // 5 + 10 ms/MP: 1280x960 = 17.3 ms fits, 1920x1440 = 32.6 ms does not
        val gov = governor(start = 5)
        run(gov, 5.0, 10.0, 30.0)
        assertEquals(sizes[3], gov.size)
        // within the memory window it stays put instead of re-probing every 4 s
        val switches = run(gov, 5.0, 10.0, 25.0, startNs = 30_000_000_000L)
        assertEquals(0, switches)
        assertEquals(sizes[3], gov.size)
    }

    @Test
    fun startUpWarmUpDoesNotDowngrade() {
        // the first 1.5 s are slow (initialisation), then 12 ms at the top size
        val gov = governor()
        var t = 0L
        repeat(30 * 20) {
            gov.onFrame(if (t < 1_500_000_000L) 60.0 else 12.0, t)
            t += 33_333_333L
        }
        assertEquals(sizes[0], gov.size)
    }

    @Test
    fun aRefusedSizeIsNeverRetried() {
        val gov = governor()
        gov.limitTo(2, 0)
        assertEquals(2, gov.index)
        run(gov, 0.0, 0.1, 40.0) // plenty of headroom
        assertEquals(2, gov.index)
    }

    @Test
    fun frozenHoldsTheSize() {
        val gov = governor()
        gov.frozen = true
        var t = 0L
        repeat(300) {
            assertNull(gov.onFrame(100.0, t))
            t += 33_333_333L
        }
        assertEquals(0, gov.index)
    }
}
