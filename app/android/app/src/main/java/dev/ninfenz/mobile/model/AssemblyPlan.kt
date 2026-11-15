package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonObject

data class PlanStep(
    val id: String,
    val node: String,
    val stage: String,
    val module: String,
    val weight: Int,
    val inputs: List<String>,
    val outputs: List<String>
)

data class AssemblyPlan(
    val pipelineId: String,
    val pipelineVersion: String,
    val pipelineDigest: String,
    val steps: List<PlanStep>,
    val slots: List<String>,
    val outputForm: String,
    val outputPath: String,
    val digest: String?
)

object PlanModel {
    const val SCHEMA = "nf-assembly-plan/1"

    fun parse(text: String): AssemblyPlan = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): AssemblyPlan {
        J.schema(o, SCHEMA)
        val pipeline = J.child(o, "pipeline", "")
        val steps = J.array(o, "steps", "").mapIndexed { i, el ->
            val s = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/steps/" + i, "step 应为对象", "按 schema 修正")
            val p = "/steps/" + i
            PlanStep(
                id = J.string(s, "id", p),
                node = J.string(s, "node", p),
                stage = J.string(s, "stage", p),
                module = J.string(s, "module", p),
                weight = J.int(s, "weight", p),
                inputs = J.optStringList(s, "inputs"),
                outputs = J.optStringList(s, "outputs")
            )
        }
        val output = J.child(o, "output", "")
        return AssemblyPlan(
            pipelineId = J.string(pipeline, "id", "/pipeline"),
            pipelineVersion = J.string(pipeline, "version", "/pipeline"),
            pipelineDigest = J.string(pipeline, "digest", "/pipeline"),
            steps = steps,
            slots = J.optStringList(o, "slots"),
            outputForm = J.string(output, "form", "/output"),
            outputPath = J.optString(output, "path") ?: "result.md",
            digest = J.optString(o, "digest")
        )
    }

    /** 本地检查：step id S## 连续、引用非空、权重 0..100。 */
    fun formIssues(plan: AssemblyPlan): List<FormIssue> {
        val issues = mutableListOf<FormIssue>()
        val ids = plan.steps.map { it.id }
        for (i in ids.indices) {
            val expect = "S" + (i + 1).toString().padStart(2, '0')
            if (ids[i] != expect) {
                issues.add(FormIssue("NF-ASM-003", "/steps/" + i, "step id 应从 S01 连续编号，实际 " + ids[i] + "（期望 " + expect + "）", "重新编译 plan"))
                break
            }
        }
        for (step in plan.steps) {
            if (step.weight !in 0..100) {
                issues.add(FormIssue("NF-ASM-003", "/steps/" + step.id, "step 权重越界：" + step.weight, "权重限 0..100"))
            }
            if (step.stage.isBlank() || step.module.isBlank()) {
                issues.add(FormIssue("NF-ASM-003", "/steps/" + step.id, "step 缺 stage/module 引用", "重新编译 plan"))
            }
        }
        if (plan.pipelineDigest.isBlank()) {
            issues.add(FormIssue("NF-ASM-001", "/pipeline/digest", "plan 缺 pipeline digest（不可追溯）", "重新编译 plan"))
        }
        return issues
    }
}
