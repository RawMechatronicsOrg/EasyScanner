package com.rawmechatronics.easyscanner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WizardTest {
    private val none = Readiness(boardConfirmed = false, focusLocked = false, calibrated = false, planeReady = false)
    private val ready = Readiness(boardConfirmed = true, focusLocked = true, calibrated = true, planeReady = true)

    @Test
    fun followsTheFirstOpenStep() {
        val w = Wizard()
        assertEquals(Step.BOARD, w.update(none))
        assertEquals(Step.FOCUS, w.update(none.copy(boardConfirmed = true)))
        assertEquals(Step.LASER, w.update(ready.copy(planeReady = false)))
        assertEquals(Step.SCAN, w.update(ready))
    }

    @Test
    fun aBrokenPrerequisiteMovesBack() {
        val w = Wizard()
        w.update(ready)
        // a new focus lock invalidates the calibration (and the plane with it)
        assertEquals(Step.CAMERA, w.update(ready.copy(calibrated = false, planeReady = false)))
    }

    @Test
    fun redoStaysUntilCompleted() {
        val w = Wizard()
        w.update(ready)
        assertTrue(w.open(Step.LASER, ready))
        assertEquals(Step.LASER, w.update(ready))
        w.completed(ready)
        assertEquals(Step.SCAN, w.step)
    }

    @Test
    fun laterStepsWaitForTheirPrerequisites() {
        val w = Wizard()
        val board = none.copy(boardConfirmed = true)
        w.update(board)
        assertFalse(w.open(Step.LASER, board))
        assertFalse(w.open(Step.DONE, ready))
        assertTrue(w.open(Step.BOARD, board))
        assertEquals(Step.BOARD, w.update(board))
    }

    @Test
    fun theResultStaysUntilANewScan() {
        val w = Wizard()
        w.update(ready)
        w.finished()
        assertEquals(Step.DONE, w.update(ready))
        w.newScan(ready)
        assertEquals(Step.SCAN, w.step)
        w.finished()
        w.newScan(ready.copy(planeReady = false))
        assertEquals(Step.LASER, w.step)
    }
}
