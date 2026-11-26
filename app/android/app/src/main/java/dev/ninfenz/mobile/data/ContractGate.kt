package dev.ninfenz.mobile.data

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 合同导出 gate：只把已求解且 satisfiable=false 视为阻断；未求解不阻断。 */
object ContractGate {
    fun blocked(solve: JsonObject?): Boolean =
        solve?.get("satisfiable")?.jsonPrimitive?.content == "false"
}
