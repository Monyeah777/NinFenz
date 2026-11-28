package dev.ninfenz.mobile.data

import android.content.Context
import dev.ninfenz.mobile.BuildConfig
import dev.ninfenz.mobile.core.Core
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 授权码校验结果（离线；不联网、不留账号）。 */
data class LicenseState(
    val valid: Boolean,
    val edition: String = "",
    val order: String = "",
    val reasonCode: String? = null,
    val reason: String = ""
)

/**
 * 纯策略：edition → Tier、版本号 → 主版本。
 * 独立成 object 以便 JVM 单测（不依赖 Android Context / JNI）。
 */
object EntitlementPolicy {
    fun tierFor(edition: String?): FeatureGate.Tier = when (edition?.trim()?.lowercase()) {
        "pro" -> FeatureGate.Tier.PRO
        "studio", "ccos" -> FeatureGate.Tier.CCOS
        else -> FeatureGate.Tier.FREE
    }

    fun editionLabel(edition: String?): String = when (edition?.trim()?.lowercase()) {
        "pro" -> "Pro"
        "studio" -> "Studio"
        "ccos" -> "Studio"
        else -> "Free"
    }

    /** "0.3.8-preview.1" → 0；解析失败默认 0（与核心 CURRENT_MAJOR 对齐）。 */
    fun appMajor(versionName: String?): Long =
        versionName?.substringBefore('.')?.trim()?.toLongOrNull() ?: 0L
}

/**
 * Pro 离线授权存储：码只存本机 SharedPreferences，启动时离线验签恢复层级。
 * 设备绑定/重绑是后续迭代（当前授权码为「任意设备」，接受个人分流）。
 */
object EntitlementStore {
    private const val PREFS = "nf_license"
    private const val KEY_CODE = "license_code"
    private const val KEY_EDITION = "license_edition"
    private const val KEY_ORDER = "license_order"
    private const val KEY_ACTIVATED_AT = "license_activated_at"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun storedCode(context: Context): String =
        prefs(context).getString(KEY_CODE, "").orEmpty()

    fun storedEdition(context: Context): String =
        prefs(context).getString(KEY_EDITION, "").orEmpty()

    fun storedOrder(context: Context): String =
        prefs(context).getString(KEY_ORDER, "").orEmpty()

    fun activatedAt(context: Context): String =
        prefs(context).getString(KEY_ACTIVATED_AT, "").orEmpty()

    fun isActivated(context: Context): Boolean = storedCode(context).isNotEmpty()

    /** 启动恢复：读已存码 → 核心离线验签 → 应用层级。任何异常都回 Free（fail-closed）。 */
    suspend fun restore(context: Context) {
        val code = storedCode(context)
        if (code.isEmpty()) {
            FeatureGate.applyEntitlement(null)
            return
        }
        val state = runCatching { verify(code) }.getOrElse {
            LicenseState(false, reasonCode = "NF-E-005", reason = it.message ?: "verify failed")
        }
        FeatureGate.applyEntitlement(if (state.valid) state.edition else null)
    }

    /** 激活：验签成功才落盘并切换层级；失败不落盘。 */
    suspend fun activate(context: Context, rawCode: String): LicenseState {
        val code = rawCode.trim()
        if (code.isEmpty()) {
            return LicenseState(false, reasonCode = "EMPTY", reason = "empty code")
        }
        val state = runCatching { verify(code) }.getOrElse {
            LicenseState(false, reasonCode = "NF-E-005", reason = it.message ?: "verify failed")
        }
        if (!state.valid) return state
        prefs(context).edit()
            .putString(KEY_CODE, code)
            .putString(KEY_EDITION, state.edition)
            .putString(KEY_ORDER, state.order)
            .putString(KEY_ACTIVATED_AT, java.time.OffsetDateTime.now().toString())
            .apply()
        FeatureGate.applyEntitlement(state.edition)
        return state
    }

    fun deactivate(context: Context) {
        prefs(context).edit().clear().apply()
        FeatureGate.applyEntitlement(null)
    }

    private suspend fun verify(code: String): LicenseState = withContext(Dispatchers.Default) {
        val response = Core.bridge.call(
            "license-verify",
            buildJsonObject {
                put("code", code)
                put("app_major", EntitlementPolicy.appMajor(BuildConfig.VERSION_NAME))
            }
        )
        val obj: JsonObject? = response.resultObject()
        if (!response.ok || obj == null) {
            return@withContext LicenseState(
                false,
                reasonCode = response.error?.code ?: "NF-E-002",
                reason = response.error?.message ?: "license-verify 无结果"
            )
        }
        LicenseState(
            valid = obj["valid"]?.jsonPrimitive?.booleanOrNull == true,
            edition = obj["edition"]?.jsonPrimitive?.contentOrNull ?: "",
            order = obj["order"]?.jsonPrimitive?.contentOrNull ?: "",
            reasonCode = obj["code"]?.jsonPrimitive?.contentOrNull,
            reason = obj["reason"]?.jsonPrimitive?.contentOrNull ?: ""
        )
    }
}
