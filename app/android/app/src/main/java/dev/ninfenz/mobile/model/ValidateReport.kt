package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonObject

data class ReportIssue(
    val code: String,
    val severity: String,
    val path: String?,
    val message: String,
    val fix: String,
    val rule: String?
)

data class ReportTarget(val kind: String, val ref: String, val digest: String)

data class ValidateReport(
    val level: String,
    val target: ReportTarget,
    val issues: List<ReportIssue>,
    val errorCount: Int,
    val warnCount: Int,
    val infoCount: Int,
    val verdict: String
) {
    val isPass: Boolean get() = verdict == "pass"
    val isFail: Boolean get() = verdict == "fail"
    val isWarn: Boolean get() = verdict == "warn"
}

object ReportModel {
    const val SCHEMA = "nf-validate-report/1"

    fun parse(text: String): ValidateReport = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): ValidateReport {
        J.schema(o, SCHEMA)
        val target = J.child(o, "target", "")
        val summary = J.child(o, "summary", "")
        val issues = J.array(o, "issues", "").mapIndexed { i, el ->
            val it = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/issues/" + i, "issue 应为对象", "按 schema 修正")
            val p = "/issues/" + i
            ReportIssue(
                code = J.string(it, "code", p),
                severity = J.string(it, "severity", p),
                path = J.optString(it, "path"),
                message = J.string(it, "message", p),
                fix = J.string(it, "fix", p),
                rule = J.optString(it, "rule")
            )
        }
        return ValidateReport(
            level = J.string(o, "level", ""),
            target = ReportTarget(
                kind = J.string(target, "kind", "/target"),
                ref = J.string(target, "ref", "/target"),
                digest = J.string(target, "digest", "/target")
            ),
            issues = issues,
            errorCount = J.int(summary, "error", "/summary"),
            warnCount = J.int(summary, "warn", "/summary"),
            infoCount = J.int(summary, "info", "/summary"),
            verdict = J.string(o, "verdict", "")
        )
    }

    fun line(report: ValidateReport): String =
        report.level + " " + report.verdict + "（error=" + report.errorCount + " warn=" + report.warnCount + " info=" + report.infoCount + "）"
}
