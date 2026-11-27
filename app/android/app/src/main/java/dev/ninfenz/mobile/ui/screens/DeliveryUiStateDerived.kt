package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import dev.ninfenz.mobile.model.SpecModel
import kotlinx.serialization.json.JsonObject

internal val DeliveryUiState.step: Int
    get() = when {
        exportedFile != null -> 3
        markdown != null || report != null -> if (audit) 2 else 3
        plan != null -> 1
        else -> 0
    }

internal val DeliveryUiState.exportBlocked: Boolean
    get() = busy || contractUnsatisfiable

internal val DeliveryUiState.hasWork: Boolean
    get() = exportedFile == null && (plan != null || markdown != null || inputs.values.any { it.isNotBlank() })

internal val DeliveryUiState.exportMarkdown: String?
    get() = if (audit && (needsRevalidate || report?.verdict == "fail")) null else markdown

internal val DeliveryUiState.slotPrefill: Map<String, String>
    get() = zeroPrefill + protocolPrefill

private var specMetaKey: kotlinx.serialization.json.JsonObject? = null
private var specMetaReady = false
private var specMetaCache: dev.ninfenz.mobile.model.MdSpec? = null

internal val DeliveryUiState.specMeta: dev.ninfenz.mobile.model.MdSpec?
    get() {
        val key = artifacts?.specJson
        if (!specMetaReady || key != specMetaKey) {
            specMetaReady = true
            specMetaKey = key
            specMetaCache = artifacts?.let { runCatching { dev.ninfenz.mobile.model.SpecModel.parse(it.specJson) }.orNullLogged("DeliveryScreen") }
        }
        return specMetaCache
    }

internal val DeliveryUiState.constraintConflicts: List<List<dev.ninfenz.mobile.model.ConstraintMUS.Rule>>
    get() = dev.ninfenz.mobile.model.SpecConstraintAudit.conflicts(specMeta?.slots.orEmpty())

private var protocolPrefillReady = false
private var protocolPrefillKey: Triple<String, Any?, Any?>? = null
private var protocolPrefillCache: Map<String, String> = emptyMap()

internal val DeliveryUiState.protocolPrefill: Map<String, String>
    get() {
        val art = artifacts
        val key = Triple(project.id, art?.protocol, art?.spec)
        if (!protocolPrefillReady || key != protocolPrefillKey) {
            protocolPrefillReady = true
            protocolPrefillKey = key
            protocolPrefillCache = if (art == null) emptyMap() else {
                val params = dev.ninfenz.mobile.data.ProtocolSlotPrefill.loadParams(context.filesDir, project.id)
                dev.ninfenz.mobile.data.ProtocolSlotPrefill.bind(art.protocol.fields, art.spec.slots, params)
            }
        }
        return protocolPrefillCache
    }
