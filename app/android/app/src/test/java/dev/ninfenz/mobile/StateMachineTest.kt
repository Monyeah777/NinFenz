package dev.ninfenz.mobile

import dev.ninfenz.mobile.model.ConflictBoard
import dev.ninfenz.mobile.model.PackConflict
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectReview
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.state.NavState
import dev.ninfenz.mobile.state.Screen
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class StateMachineTest {

    @Test
    fun navStartsAtHomeAndPoplocksAtRoot() {
        val nav = NavState()
        assertEquals(Screen.HOME, nav.current)
        assertFalse(nav.canPop)
        assertEquals(nav, nav.pop())
        val pushed = nav.push(Screen.IMPORT)
        assertTrue(pushed.canPop)
        assertEquals(Screen.IMPORT, pushed.current)
        assertEquals(Screen.HOME, pushed.pop().current)
    }

    @Test
    fun navPushSameScreenIsNoopAndResetClears() {
        val nav = NavState().push(Screen.GRAPH)
        assertEquals(nav, nav.push(Screen.GRAPH))
        val deep = nav.push(Screen.CCOS).push(Screen.SETTINGS)
        assertEquals(4, deep.stack.size)
        val reset = deep.reset(Screen.HOME)
        assertEquals(listOf(Screen.HOME), reset.stack)
    }

    @Test
    fun conflictBoardDefaultsToDeferAndRequiresDecisions() {
        val board = ConflictBoard(listOf(
            PackConflict("CFL-01", "delete", "docs/legacy.md", null, null, listOf("keep_mine", "take_new", "defer"), "defer")
        ))
        assertEquals("defer", board.decisionOf("CFL-01"))
        assertFalse(board.isResolved())
        assertEquals(1, board.unresolved().size)
        assertFalse(board.decide("CFL-01", "bogus"))
        assertFalse(board.decide("CFL-99", "take_new"))
        assertTrue(board.decide("CFL-01", "take_new"))
        assertEquals("take_new", board.decisionOf("CFL-01"))
        assertTrue(board.isResolved())
        assertEquals(mapOf("CFL-01" to "take_new"), board.decisionsMap())
        assertTrue(board.summary().contains("冲突 1 个"))
    }

    @Test
    fun conflictBoardWithNoConflictsIsResolved() {
        val board = ConflictBoard(emptyList())
        assertTrue(board.isResolved())
        assertEquals("无冲突", board.summary())
    }

    @Test
    fun projectTransitionsFollowOrder() {
        val forward = listOf(
            ProjectStatus.DRAFT to ProjectStatus.AUTHORING,
            ProjectStatus.AUTHORING to ProjectStatus.ASSEMBLED,
            ProjectStatus.ASSEMBLED to ProjectStatus.VALIDATED,
            ProjectStatus.VALIDATED to ProjectStatus.EXPORTED,
            ProjectStatus.EXPORTED to ProjectStatus.REVIEWED
        )
        for ((from, to) in forward) {
            assertTrue(ProjectModel.transition(from, to, false).ok)
        }
        assertFalse(ProjectModel.transition(ProjectStatus.DRAFT, ProjectStatus.ASSEMBLED, false).ok)
        assertTrue(ProjectModel.transition(ProjectStatus.DRAFT, ProjectStatus.ASSEMBLED, true).ok)
        assertFalse(ProjectModel.transition(ProjectStatus.REVIEWED, ProjectStatus.REVIEWED, false).ok)
    }

    @Test
    fun reviewRequiresTraceForApproved() {
        assertTrue(ProjectModel.reviewOk(ProjectReview("none", null, null, null)))
        assertTrue(ProjectModel.reviewOk(ProjectReview("pending", null, null, null)))
        assertFalse(ProjectModel.reviewOk(ProjectReview("approved", null, "note", "digest")))
        assertFalse(ProjectModel.reviewOk(ProjectReview("approved", "reviewer", null, "digest")))
        assertFalse(ProjectModel.reviewOk(ProjectReview("approved", "reviewer", "note", null)))
        assertTrue(ProjectModel.reviewOk(ProjectReview("approved", "reviewer", "note", "digest")))
        assertFalse(ProjectModel.reviewOk(ProjectReview("rejected", null, null, null)))
        assertFalse(ProjectModel.reviewOk(ProjectReview("bogus", null, null, null)))
    }
}
