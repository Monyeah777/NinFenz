package dev.ninfenz.mobile.model

import org.junit.Assert.assertTrue
import org.junit.Test

class CorrectionPromptTest {
    @Test
    fun includesIssuesAndRequirements() {
        val report = ValidateReport(
            level = "L1",
            target = ReportTarget("markdown", "demo", "sha256"),
            issues = listOf(
                ReportIssue(code = "NF-VAL-001", severity = "error", path = "/sections/0", message = "缺少正文", fix = "补正文", rule = null)
            ),
            errorCount = 1,
            warnCount = 0,
            infoCount = 0,
            verdict = "fail"
        )
        val prompt = CorrectionPrompt.build("# 标题\n\n正文", report)
        assertTrue(prompt.contains("NF-VAL-001"))
        assertTrue(prompt.contains("补正文"))
        assertTrue(prompt.contains("不新增原文没有的事实"))
    }
}
