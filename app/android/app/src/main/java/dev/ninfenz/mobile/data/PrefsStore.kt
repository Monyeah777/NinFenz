package dev.ninfenz.mobile.data

import android.content.Context
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/**
 * nf-prefs/1 本地存储：单文件、原子写、保留上一份 .bak。
 * 首次加载从旧 AppPrefs 迁移主题/语言/动态色；旧键不删除。
 */
class PrefsStore(
    private val filesDir: File,
    private val legacy: AppPrefs? = null
) {
    constructor(context: Context) : this(context.filesDir, AppPrefs(context))

    private fun file(): File = File(filesDir, "nf-prefs.json")

    @Volatile
    private var cached: NfPrefs? = null

    @Volatile
    var lastError: String? = null
        private set

    fun load(): NfPrefs {
        cached?.let { return it }
        val f = file()
        if (!f.isFile) {
            val migrated = migrateLegacy()
            write(migrated)
            cached = migrated
            return migrated
        }
        return try {
            val parsed = parse(f.readText(Charsets.UTF_8))
            cached = parsed
            parsed
        } catch (t: Throwable) {
            lastError = t.message ?: t.javaClass.simpleName
            val fallback = migrateLegacy()
            cached = fallback
            fallback
        }
    }

    fun save(next: NfPrefs): NfPrefs {
        val revisioned = next.copy(revision = next.revision + 1)
        write(revisioned)
        cached = revisioned
        lastError = null
        return revisioned
    }

    fun resetAll(): NfPrefs = save(NfPrefs())

    fun resetModule(capability: Capability): NfPrefs {
        val current = load()
        return save(current.copy(modules = current.modules.with(capability, capability.defaultEnabled)))
    }

    fun applyWorkflow(id: String): NfPrefs {
        val current = load()
        val preset = current.workflows.firstOrNull { it.id == id } ?: WorkflowPresets.builtins().first { it.id == id }
        return save(
            current.copy(
                modules = preset.modules,
                ui = preset.ui,
                actionPolicy = preset.actionPolicy,
                validationPolicy = preset.validationPolicy
            )
        )
    }

    fun saveWorkflow(name: String): NfPrefs {
        val current = load()
        val id = slug(name)
        val preset = WorkflowPreset(
            id = id,
            name = name.ifBlank { id },
            source = "user",
            modules = current.modules,
            ui = current.ui,
            actionPolicy = current.actionPolicy,
            validationPolicy = current.validationPolicy
        )
        val next = (current.workflows.filterNot { it.id == id } + preset).takeLast(20)
        return save(current.copy(workflows = next))
    }

    fun exportJson(): String = toJson(load()).toString()

    fun importJson(text: String): NfPrefs {
        val parsed = parse(text)
        return save(parsed.copy(revision = load().revision))
    }

    fun snapshot(): String = exportJson()

    fun restore(text: String): Boolean = runCatching { importJson(text) }.isSuccess

    private fun migrateLegacy(): NfPrefs {
        val theme = when (legacy?.themeMode) {
            ThemeMode.LIGHT -> PrefsTheme.LIGHT
            ThemeMode.DARK -> PrefsTheme.DARK
            else -> PrefsTheme.SYSTEM
        }
        return NfPrefs(
            ui = UiPrefs(theme = theme),
            language = legacy?.languageMode ?: LanguageMode.SYSTEM
        )
    }

    private fun write(prefs: NfPrefs) {
        AtomicFiles.writeText(file(), toJson(prefs).toString())
    }

    private fun parse(text: String): NfPrefs {
        val root = runCatching { Json.parseToJsonElement(text).jsonObject }
            .getOrElse { throw PrefsFormatException("nf-prefs 不是 JSON 对象") }
        if (root.string("schema") != "nf-prefs/1") throw PrefsFormatException("schema 必须是 nf-prefs/1")
        if (root.int("version") != 1) throw PrefsFormatException("version 必须是 1")
        val revision = root.int("revision")
        val modules = parseModules(root.obj("modules"))
        val ui = parseUi(root.obj("ui"))
        val language = parseLanguage(root.string("language"))
        val action = parseAction(root.obj("action_policy"))
        val validation = parseValidation(root.obj("validation_policy"))
        val workflows = root["workflows"]?.let { element ->
            val array = element as? JsonArray ?: throw PrefsFormatException("workflows 必须是数组")
            array.map { parseWorkflow(it as? JsonObject ?: throw PrefsFormatException("workflow 必须是对象")) }
        } ?: WorkflowPresets.builtins()
        if (workflows.size > 20) throw PrefsFormatException("workflows 最多 20 个")
        return NfPrefs(revision, modules, ui, language, action, validation, workflows)
    }

    private fun parseModules(obj: JsonObject): ModuleToggles {
        val allowed = Capability.entries.map { it.id }.toSet()
        if (!allowed.containsAll(obj.keys)) throw PrefsFormatException("modules 含未知键")
        val values = Capability.entries.associate { cap ->
            val value = obj[cap.id] as? JsonPrimitive
                ?: throw PrefsFormatException("modules " + cap.id + " 必须是 boolean")
            cap.id to (value.content.toBooleanStrictOrNull()
                ?: throw PrefsFormatException("modules " + cap.id + " 必须是 boolean"))
        }
        return ModuleToggles(values)
    }

    private fun parseUi(obj: JsonObject): UiPrefs {
        val density = when (obj.string("density")) {
            "comfortable" -> Density.COMFORTABLE
            "compact" -> Density.COMPACT
            else -> throw PrefsFormatException("ui.density 非法")
        }
        val theme = when (obj.string("theme")) {
            "system" -> PrefsTheme.SYSTEM
            "light" -> PrefsTheme.LIGHT
            "dark" -> PrefsTheme.DARK
            "high_contrast" -> PrefsTheme.HIGH_CONTRAST
            else -> throw PrefsFormatException("ui.theme 非法")
        }
        val scale = obj.int("font_scale_percent")
        if (scale !in 80..200) throw PrefsFormatException("ui.font_scale_percent 必须在 80..200")
        val motion = obj.boolean("motion")
        return UiPrefs(density, scale, theme, motion)
    }

    private fun parseLanguage(raw: String): LanguageMode = when (raw) {
        "system" -> LanguageMode.SYSTEM
        "zh" -> LanguageMode.ZH
        "en" -> LanguageMode.EN
        "pseudo" -> LanguageMode.PSEUDO
        else -> throw PrefsFormatException("language 非法")
    }

    private fun parseAction(obj: JsonObject): ActionPolicy = ActionPolicy(
        aiResult = obj.string("ai_result").also { if (it !in setOf("draft", "ask", "auto")) throw PrefsFormatException("ai_result 非法") },
        mergeConflict = obj.string("merge_conflict").also { if (it !in setOf("manual", "auto")) throw PrefsFormatException("merge_conflict 非法") },
        packUpdate = obj.string("pack_update").also { if (it !in setOf("manual", "ask", "auto")) throw PrefsFormatException("pack_update 非法") },
        macroReplay = obj.string("macro_replay").also { if (it !in setOf("dry_run", "run")) throw PrefsFormatException("macro_replay 非法") }
    )

    private fun parseValidation(obj: JsonObject): ValidationPolicy {
        val mode = obj.string("mode")
        if (mode !in setOf("off", "on_demand", "delivery", "strict")) throw PrefsFormatException("validation.mode 非法")
        return ValidationPolicy(mode, obj.boolean("block_export"), obj.boolean("record_skips"))
    }

    private fun parseWorkflow(obj: JsonObject): WorkflowPreset {
        if (obj.string("schema") != "nf-workflow/1") throw PrefsFormatException("workflow.schema 非法")
        val id = obj.string("id")
        if (!Regex("^[a-z][a-z0-9-]{1,63}$").matches(id)) throw PrefsFormatException("workflow.id 非法")
        val source = obj.string("source")
        if (source !in setOf("builtin", "user")) throw PrefsFormatException("workflow.source 非法")
        return WorkflowPreset(
            id = id,
            name = obj.string("name"),
            source = source,
            modules = parseModules(obj.obj("modules")),
            ui = parseUi(obj.obj("ui")),
            actionPolicy = parseAction(obj.obj("action_policy")),
            validationPolicy = parseValidation(obj.obj("validation_policy"))
        )
    }

    private fun toJson(prefs: NfPrefs): JsonObject = buildJsonObject {
        put("schema", "nf-prefs/1")
        put("version", 1)
        put("revision", prefs.revision)
        put("modules", modulesJson(prefs.modules))
        put("ui", uiJson(prefs.ui))
        put("language", languageJson(prefs.language))
        put("action_policy", actionJson(prefs.actionPolicy))
        put("validation_policy", validationJson(prefs.validationPolicy))
        put("workflows", buildJsonArray { prefs.workflows.forEach { add(workflowJson(it)) } })
    }

    private fun modulesJson(modules: ModuleToggles): JsonObject = buildJsonObject {
        Capability.entries.forEach { cap -> put(cap.id, modules.enabled(cap)) }
    }

    private fun uiJson(ui: UiPrefs): JsonObject = buildJsonObject {
        put("density", ui.density.name.lowercase())
        put("font_scale_percent", ui.fontScalePercent)
        put("theme", ui.theme.name.lowercase())
        put("motion", ui.motion)
    }

    private fun languageJson(language: LanguageMode): String = language.name.lowercase()

    private fun actionJson(policy: ActionPolicy): JsonObject = buildJsonObject {
        put("ai_result", policy.aiResult)
        put("merge_conflict", policy.mergeConflict)
        put("pack_update", policy.packUpdate)
        put("macro_replay", policy.macroReplay)
    }

    private fun validationJson(policy: ValidationPolicy): JsonObject = buildJsonObject {
        put("mode", policy.mode)
        put("block_export", policy.blockExport)
        put("record_skips", policy.recordSkips)
    }

    private fun workflowJson(preset: WorkflowPreset): JsonObject = buildJsonObject {
        put("schema", "nf-workflow/1")
        put("id", preset.id)
        put("name", preset.name)
        put("source", preset.source)
        put("modules", modulesJson(preset.modules))
        put("ui", uiJson(preset.ui))
        put("action_policy", actionJson(preset.actionPolicy))
        put("validation_policy", validationJson(preset.validationPolicy))
    }

    private fun slug(name: String): String {
        val base = name.trim().lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').ifBlank { "preset" }
        if (base == "preset") {
            val hash = name.hashCode() and 0x7fffffff
            return "p-" + hash.toString(16)
        }
        return if (base.first().isLetter()) base.take(63) else "p-$base".take(63)
    }

    private fun JsonObject.string(key: String): String =
        (this[key] as? JsonPrimitive)?.content ?: throw PrefsFormatException("缺 " + key)

    private fun JsonObject.int(key: String): Int =
        string(key).toIntOrNull() ?: throw PrefsFormatException(key + " 必须是整数")

    private fun JsonObject.boolean(key: String): Boolean =
        (this[key] as? JsonPrimitive)?.content?.toBooleanStrictOrNull()
            ?: throw PrefsFormatException(key + " 必须是 boolean")

    private fun JsonObject.obj(key: String): JsonObject =
        this[key] as? JsonObject ?: throw PrefsFormatException(key + " 必须是对象")
}
