package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonObject

data class ProtocolClause(
    val id: String,
    val title: String,
    val level: String,
    val text: String,
    val enabled: Boolean,
    val fields: List<String>
)

data class ProtocolField(
    val id: String,
    val clause: String,
    val label: String,
    val type: String,
    val required: Boolean,
    val defaultText: String?,
    val options: List<String>,
    val maxLen: Int?,
    val pattern: String?
)

data class ProtocolRule(
    val id: String,
    val severity: String,
    val message: String,
    val fix: String,
    val op: String?
)

data class ProtocolPack(
    val id: String,
    val version: String,
    val title: String,
    val protoVersion: Int,
    val clauses: List<ProtocolClause>,
    val fields: List<ProtocolField>,
    val rules: List<ProtocolRule>,
    val appMin: String,
    val protocolMin: Int,
    val protocolMax: Int
)

/** 单条条款的占位符检查结果（本地检查，权威渲染仍走核心 protocol-render）。 */
data class ClausePlaceholderCheck(
    val clauseId: String,
    val missing: List<String>,
    val unknown: List<String>
) {
    val ok: Boolean get() = missing.isEmpty() && unknown.isEmpty()
}

object ProtocolModel {
    const val SCHEMA = "nf-protocol-pack/1"
    private val PLACEHOLDER = Regex("\\{\\{([A-Za-z0-9_-]+)\\}\\}")

    fun parse(text: String): ProtocolPack = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): ProtocolPack {
        J.schema(o, SCHEMA)
        val clauses = parseClauses(o)
        val fields = parseFields(o)
        val rules = parseRules(o)
        val compat = J.child(o, "compat", "")
        return ProtocolPack(
            id = J.string(o, "id", ""),
            version = J.string(o, "version", ""),
            title = J.string(o, "title", ""),
            protoVersion = J.int(o, "proto_version", ""),
            clauses = clauses,
            fields = fields,
            rules = rules,
            appMin = J.string(compat, "app_min", "/compat"),
            protocolMin = J.int(compat, "protocol_min", "/compat"),
            protocolMax = J.int(compat, "protocol_max", "/compat")
        )
    }

    private fun parseClauses(o: JsonObject): List<ProtocolClause> =
        J.array(o, "clauses", "").mapIndexed { i, el ->
            val c = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/clauses/" + i, "条款应为对象", "按 schema 修正")
            val p = "/clauses/" + i
            ProtocolClause(
                id = J.string(c, "id", p),
                title = J.string(c, "title", p),
                level = J.string(c, "level", p),
                text = J.string(c, "text", p),
                enabled = J.bool(c, "enabled", p),
                fields = J.optStringList(c, "fields")
            )
        }

    private fun parseFields(o: JsonObject): List<ProtocolField> =
        J.array(o, "fields", "").mapIndexed { i, el ->
            val f = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/fields/" + i, "字段应为对象", "按 schema 修正")
            val p = "/fields/" + i
            val constraint = J.optChild(f, "constraint")
            ProtocolField(
                id = J.string(f, "id", p),
                clause = J.string(f, "clause", p),
                label = J.string(f, "label", p),
                type = J.string(f, "type", p),
                required = J.bool(f, "required", p),
                defaultText = J.optString(f, "default"),
                options = J.optStringList(f, "options"),
                maxLen = constraint?.let { J.optInt(it, "max_len") },
                pattern = constraint?.let { J.optString(it, "pattern") }
            )
        }

    private fun parseRules(o: JsonObject): List<ProtocolRule> =
        J.array(o, "rules", "").mapIndexed { i, el ->
            val r = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/rules/" + i, "规则应为对象", "按 schema 修正")
            val p = "/rules/" + i
            val expr = J.optChild(r, "expr")
            ProtocolRule(
                id = J.string(r, "id", p),
                severity = J.string(r, "severity", p),
                message = J.string(r, "message", p),
                fix = J.string(r, "fix", p),
                op = expr?.let { J.optString(it, "op") }
            )
        }

    fun placeholders(text: String): List<String> =
        PLACEHOLDER.findAll(text).map { it.groupValues[1] }.toList()

    /**
     * 本地占位符检查（CONTRACT §5.3）：缺必填字段、未知占位符。
     * 这与核心 fail-closed 语义一致；权威渲染/规则求值仍由核心完成。
     */
    fun checkClause(pack: ProtocolPack, clause: ProtocolClause, values: Map<String, String>): ClausePlaceholderCheck {
        val declared = pack.fields.map { it.id }.toSet()
        val requiredByClause = pack.fields.filter { it.clause == clause.id && it.required }.map { it.id }.toSet()
        val refs = placeholders(clause.text)
        val missing = mutableListOf<String>()
        val unknown = mutableListOf<String>()
        for (ref in refs.distinct()) {
            if (ref !in declared) {
                unknown.add(ref)
                continue
            }
            if (ref in requiredByClause && values[ref].isNullOrBlank()) {
                missing.add(ref)
            }
        }
        for (f in requiredByClause) {
            if (f !in refs && values[f].isNullOrBlank()) {
                missing.add(f)
            }
        }
        return ClausePlaceholderCheck(clause.id, missing.distinct(), unknown.distinct())
    }

    /** 渲染前的保守替换：只替换已声明占位符，未知占位符原样保留并另行报错。 */
    fun renderPreview(clause: ProtocolClause, pack: ProtocolPack, values: Map<String, String>): String {
        val declared = pack.fields.map { it.id }.toSet()
        return PLACEHOLDER.replace(clause.text) { m ->
            val id = m.groupValues[1]
            if (id in declared) values[id] ?: "" else m.value
        }
    }

    fun enabledClauses(pack: ProtocolPack): List<ProtocolClause> = pack.clauses.filter { it.enabled }
}
