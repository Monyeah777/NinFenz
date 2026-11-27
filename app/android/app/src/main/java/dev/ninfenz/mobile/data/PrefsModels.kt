package dev.ninfenz.mobile.data

/** 12 个可关模块；默认值来自 0.3.6 方案。 */
enum class Capability(val id: String, val defaultEnabled: Boolean) {
    CONTRACT("contract", true),
    BUILD_DIAG("builddiag", false),
    FRAGMENTS("fragments", true),
    MATRIX("matrix", true),
    STYLE("style", false),
    AI("ai", false),
    MERGE("merge", true),
    NETWORK("network", false),
    SOURCES("sources", true),
    MACROS("macros", false),
    BATCH("batch", true),
    SEARCH("search", true)
}

data class ModuleToggles(
    val values: Map<String, Boolean> = Capability.entries.associate { it.id to it.defaultEnabled }
) {
    init {
        require(Capability.entries.all { values.containsKey(it.id) }) { "模块开关缺项" }
        require(values.keys.all { key -> Capability.entries.any { it.id == key } }) { "未知模块开关" }
    }

    fun enabled(capability: Capability): Boolean = values[capability.id] ?: capability.defaultEnabled

    fun with(capability: Capability, enabled: Boolean): ModuleToggles =
        copy(values = values + (capability.id to enabled))

    companion object {
        fun standard(): ModuleToggles = ModuleToggles()
        fun allOff(): ModuleToggles = ModuleToggles(Capability.entries.associate { it.id to false })
        fun allOn(): ModuleToggles = ModuleToggles(Capability.entries.associate { it.id to true })
        fun expert(): ModuleToggles = ModuleToggles(
            Capability.entries.associate { it.id to (it != Capability.NETWORK) }
        )
    }
}

enum class Density { COMFORTABLE, COMPACT }

enum class PrefsTheme { SYSTEM, LIGHT, DARK, HIGH_CONTRAST }

data class UiPrefs(
    val density: Density = Density.COMFORTABLE,
    val fontScalePercent: Int = 100,
    val theme: PrefsTheme = PrefsTheme.SYSTEM,
    val motion: Boolean = true
) {
    init {
        require(fontScalePercent in 80..200) { "字号必须在 80..200" }
    }
}

data class ActionPolicy(
    val aiResult: String = "draft",
    val mergeConflict: String = "manual",
    val packUpdate: String = "manual",
    val macroReplay: String = "dry_run"
)

data class ValidationPolicy(
    val mode: String = "on_demand",
    val blockExport: Boolean = false,
    val recordSkips: Boolean = true
) {
    init {
        require(mode in setOf("off", "on_demand", "delivery", "strict")) { "未知校验模式" }
    }

    fun blocksExport(): Boolean = blockExport || mode == "delivery" || mode == "strict"
}

data class WorkflowPreset(
    val id: String,
    val name: String,
    val source: String,
    val modules: ModuleToggles,
    val ui: UiPrefs,
    val actionPolicy: ActionPolicy,
    val validationPolicy: ValidationPolicy
)

object WorkflowPresets {
    fun minimal(): WorkflowPreset {
        return WorkflowPreset(
            id = "minimal",
            name = "minimal",
            source = "builtin",
            modules = ModuleToggles.allOff(),
            ui = UiPrefs(density = Density.COMPACT, motion = false),
            actionPolicy = ActionPolicy(),
            validationPolicy = ValidationPolicy(mode = "on_demand")
        )
    }

    fun standard(): WorkflowPreset {
        return WorkflowPreset(
            id = "standard",
            name = "standard",
            source = "builtin",
            modules = ModuleToggles.standard(),
            ui = UiPrefs(),
            actionPolicy = ActionPolicy(),
            validationPolicy = ValidationPolicy()
        )
    }

    fun expert(): WorkflowPreset {
        return WorkflowPreset(
            id = "expert",
            name = "expert",
            source = "builtin",
            modules = ModuleToggles.expert(),
            ui = UiPrefs(density = Density.COMPACT, motion = false),
            actionPolicy = ActionPolicy(aiResult = "ask", macroReplay = "dry_run"),
            validationPolicy = ValidationPolicy(mode = "on_demand")
        )
    }

    fun builtins(): List<WorkflowPreset> {
        return listOf(minimal(), standard(), expert())
    }
}

data class NfPrefs(
    val revision: Int = 0,
    val modules: ModuleToggles = ModuleToggles.standard(),
    val ui: UiPrefs = UiPrefs(),
    val language: LanguageMode = LanguageMode.SYSTEM,
    val actionPolicy: ActionPolicy = ActionPolicy(),
    val validationPolicy: ValidationPolicy = ValidationPolicy(),
    val workflows: List<WorkflowPreset> = WorkflowPresets.builtins()
)

class PrefsFormatException(message: String) : Exception(message)
