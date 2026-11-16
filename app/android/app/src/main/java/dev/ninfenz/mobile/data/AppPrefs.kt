package dev.ninfenz.mobile.data

import android.content.Context
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

enum class ThemeMode { SYSTEM, LIGHT, DARK }

enum class LanguageMode(val tag: String?) { SYSTEM(null), ZH("zh"), EN("en") }

/** 本地设置（v0.02 先用 SharedPreferences；DataStore 迁移列入后续波次）。 */
class AppPrefs(context: Context) {
    private val sp = context.getSharedPreferences("nf_prefs", Context.MODE_PRIVATE)

    var onboardingDone: Boolean
        get() = sp.getBoolean("onboarding_done", false)
        set(value) = sp.edit().putBoolean("onboarding_done", value).apply()

    var sampleSeeded: Boolean
        get() = sp.getBoolean("sample_seeded", false)
        set(value) = sp.edit().putBoolean("sample_seeded", value).apply()

    var themeMode: ThemeMode
        get() = runCatching { ThemeMode.valueOf(sp.getString("theme_mode", "SYSTEM") ?: "SYSTEM") }
            .getOrDefault(ThemeMode.SYSTEM)
        set(value) = sp.edit().putString("theme_mode", value.name).apply()

    var languageMode: LanguageMode
        get() = runCatching { LanguageMode.valueOf(sp.getString("language_mode", "SYSTEM") ?: "SYSTEM") }
            .getOrDefault(LanguageMode.SYSTEM)
        set(value) = sp.edit().putString("language_mode", value.name).apply()

    var dynamicColor: Boolean
        get() = sp.getBoolean("dynamic_color", false)
        set(value) = sp.edit().putBoolean("dynamic_color", value).apply()

    /** 备份用快照（仅本地偏好，不含内容）。 */
    fun snapshot(): String = buildJsonObject {
        put("onboarding_done", onboardingDone)
        put("sample_seeded", sampleSeeded)
        put("theme_mode", themeMode.name)
        put("language_mode", languageMode.name)
        put("dynamic_color", dynamicColor)
    }.toString()

    fun restore(json: String): Boolean = try {
        val o = Json.parseToJsonElement(json).jsonObject
        o["onboarding_done"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()?.let { onboardingDone = it }
        o["sample_seeded"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()?.let { sampleSeeded = it }
        o["theme_mode"]?.jsonPrimitive?.content?.let { ThemeMode.entries.firstOrNull { m -> m.name == it } }?.let { themeMode = it }
        o["language_mode"]?.jsonPrimitive?.content?.let { LanguageMode.entries.firstOrNull { m -> m.name == it } }?.let { languageMode = it }
        o["dynamic_color"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()?.let { dynamicColor = it }
        true
    } catch (t: Throwable) {
        false
    }
}
