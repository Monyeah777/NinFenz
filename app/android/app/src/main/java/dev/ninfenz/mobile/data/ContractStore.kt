package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.Base64
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 本地验收签收：用设备密钥对验收载荷做 ECDSA 签名，不是 CA/时间戳。 */
class ContractStore(
    private val filesDir: File,
    private val signer: ContractSigner = AndroidKeystoreSigner()
) {
    data class Signoff(
        val projectId: String,
        val accepted: List<String>,
        val signedAt: String,
        val artifactSha256: String?,
        val keyFingerprint: String? = null
    )

    private fun file(projectId: String): File {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        return File(File(filesDir, "contracts").apply { mkdirs() }, safe + ".json")
    }

    private fun payload(projectId: String, accepted: List<String>, at: String, artifactSha256: String?): String =
        buildJsonObject {
            put("schema", "nf-contract-signoff/1")
            put("project_id", projectId)
            putJsonArray("accepted") { accepted.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
            put("signed_at", at)
            artifactSha256?.let { put("artifact_sha256", it) }
        }.toString()

    private fun fingerprint(publicKey: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(publicKey).joinToString("") { "%02x".format(it.toInt() and 0xff) }

    fun raw(projectId: String): String? = file(projectId).takeIf { it.isFile }?.readText(Charsets.UTF_8)

    fun load(projectId: String): Signoff? {
        val f = file(projectId)
        if (!f.isFile) return null
        return runCatching {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            val storedProjectId = root["project_id"]?.jsonPrimitive?.content ?: projectId
            val accepted = root["accepted"]?.jsonArray?.map { it.jsonPrimitive.content }.orEmpty()
            val at = root["signed_at"]?.jsonPrimitive?.content.orEmpty()
            val artifact = root["artifact_sha256"]?.jsonPrimitive?.content
            val sigObj = root["signature"]?.jsonObject ?: return null
            val signature = Base64.getDecoder().decode(sigObj["value"]?.jsonPrimitive?.content ?: return null)
            val text = payload(storedProjectId, accepted, at, artifact)
            if (!signer.verify(text.toByteArray(Charsets.UTF_8), signature)) return null
            Signoff(storedProjectId, accepted, at, artifact, fingerprint(signer.publicKey()))
        }.getOrNull()
    }

    fun sign(projectId: String, accepted: List<String>, at: String, artifactSha256: String? = null) {
        val text = payload(projectId, accepted, at, artifactSha256)
        val signature = signer.sign(text.toByteArray(Charsets.UTF_8))
        val publicKey = signer.publicKey()
        val payload = buildJsonObject {
            put("schema", "nf-contract-signoff/1")
            put("project_id", projectId)
            putJsonArray("accepted") { accepted.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
            put("signed_at", at)
            artifactSha256?.let { put("artifact_sha256", it) }
            put("signature", buildJsonObject {
                put("alg", "SHA256withECDSA")
                put("value", Base64.getEncoder().encodeToString(signature))
                put("public_key", Base64.getEncoder().encodeToString(publicKey))
                put("key_sha256", fingerprint(publicKey))
            })
        }
        AtomicFiles.writeText(file(projectId), payload.toString())
    }
}
