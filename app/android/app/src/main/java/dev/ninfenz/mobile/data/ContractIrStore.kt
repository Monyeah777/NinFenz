package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreResponse
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 合同 IR 本地存档 + 通过核心 contract-compile 编译。与验收签收 ContractStore 分开。 */
class ContractIrStore(private val filesDir: File, private val projectId: String) {
    data class Compiled(val contract: JsonObject, val warnings: List<String> = emptyList())

    fun file(): File = File(File(File(filesDir, "projects"), projectId), "contract/contract.json")

    fun load(): JsonObject? = runCatching {
        val f = file()
        if (!f.isFile) null else Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
    }.getOrNull()

    fun save(contract: JsonObject) {
        AtomicFiles.writeText(file(), contract.toString())
    }

    fun solveFile(): File = File(File(File(filesDir, "projects"), projectId), "contract/solve.json")

    fun saveSolve(result: JsonObject) {
        AtomicFiles.writeText(solveFile(), result.toString())
    }

    fun loadSolve(): JsonObject? = runCatching {
        val f = solveFile()
        if (!f.isFile) null else Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
    }.getOrNull()

    fun valuesFile(): File = File(File(File(filesDir, "projects"), projectId), "contract/values.json")

    fun saveValues(values: Map<String, String>) {
        AtomicFiles.writeText(
            valuesFile(),
            JsonObject(values.mapValues { (_, value) -> JsonPrimitive(value) }).toString()
        )
    }

    fun loadValues(): Map<String, String> = runCatching {
        val f = valuesFile()
        if (!f.isFile) emptyMap()
        else Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            .mapValues { (_, value) -> value.jsonPrimitive.content }
    }.getOrDefault(emptyMap())

    suspend fun compile(spec: JsonObject, protocol: JsonObject?): Result<Compiled> = withContext(Dispatchers.IO) {
        runCatching {
            val bridge = Core.bridge
            val request = buildJsonObject {
                put("spec", spec)
                protocol?.let { put("protocol", it) }
            }
            val response: CoreResponse = bridge.call("contract-compile", request)
            if (!response.ok) {
                throw IllegalStateException(response.error?.message ?: "contract-compile failed")
            }
            val contract = response.resultObject() ?: throw IllegalStateException("合同结果为空")
            save(contract)
            Compiled(contract)
        }
    }
}
