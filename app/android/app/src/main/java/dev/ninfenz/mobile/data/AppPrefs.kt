package dev.ninfenz.mobile.data

import android.content.Context

enum class ThemeMode { SYSTEM, LIGHT, DARK }

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
}
