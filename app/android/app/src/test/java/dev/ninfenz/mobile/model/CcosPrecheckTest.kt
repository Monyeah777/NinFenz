package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CcosPrecheckTest {
    private val hex = "a".repeat(64)

    private fun task() = CcosTask(
        id = "T-1", createdAt = "2026-01-01T00:00:00Z", packId = "p", packVersion = "1.0.0",
        packTree = hex, protocolId = "proto", protocolDigest = hex, pipelineDigest = hex,
        specDigest = hex, inputsCount = 1, maxTokens = 1, maxChars = 1, maxSeconds = 1,
        networkAllowed = false, secretsPolicy = "none", projectId = "proj", projectDigest = hex
    )

    private fun result(
        taskId: String = "T-1",
        taskDigest: String = hex,
        artifactPath: String = "out/result.md",
        artifactSha: String = hex
    ) = CcosResult(
        taskId = taskId, taskDigest = taskDigest, status = "pass",
        artifacts = listOf(CcosArtifact("result.md", "text/markdown", artifactPath, artifactSha, 3)),
        evidence = listOf(CcosEvidence("report", "report.json", hex)),
        reportSummary = "ok", issues = emptyList(), reviewRequired = true,
        reviewState = "pending", reviewer = null, note = null,
        engine = "test", startedAt = "2026-01-01T00:00:00Z", finishedAt = "2026-01-01T00:00:01Z",
        model = null
    )

    @Test
    fun validResultHasNoFindings() {
        assertTrue(CcosPrecheck.check(result(), task()).isEmpty())
    }

    @Test
    fun taskIdMismatchIsReported() {
        val findings = CcosPrecheck.check(result(taskId = "T-2"), task())
        assertEquals(1, findings.size)
        assertEquals("task_id", findings[0].field)
    }

    @Test
    fun unsafeArtifactPathAndDigestAreReported() {
        val findings = CcosPrecheck.check(result(artifactPath = "../x", artifactSha = "bad"), task())
        assertEquals(2, findings.size)
    }
}
