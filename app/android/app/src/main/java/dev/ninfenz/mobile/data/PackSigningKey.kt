package dev.ninfenz.mobile.data

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.File
import java.security.KeyStore
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** 本地 Pack 发布签名 key（仅本机；Android 私有目录；优先 Keystore AES-GCM，JVM 测试回退明文）。 */
object PackSigningKey {
    private const val ALIAS = "nf-pack-signing"
    private const val FILE = "pack-signing-seed.enc"

    private fun legacyFile(filesDir: File): File =
        File(File(filesDir, "keys").apply { mkdirs() }, "pack-signing-seed.hex")

    private fun encFile(filesDir: File): File =
        File(File(filesDir, "keys").apply { mkdirs() }, FILE)

    fun seed(filesDir: File): String {
        keystoreSeed(filesDir)?.let { return it }
        val f = legacyFile(filesDir)
        if (f.isFile) {
            val existing = f.readText(Charsets.UTF_8).trim()
            if (existing.matches(Regex("^[0-9a-f]{64}$"))) return existing
        }
        val hex = randomHex()
        AtomicFiles.writeText(f, hex)
        return hex
    }

    private fun keystoreSeed(filesDir: File): String? = runCatching {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val key = (ks.getKey(ALIAS, null) as? SecretKey) ?: generate(ks)
        val f = encFile(filesDir)
        if (f.isFile) {
            val parts = f.readText(Charsets.UTF_8).trim().split(':')
            if (parts.size == 2) {
                val iv = hexToBytes(parts[0])
                val data = hexToBytes(parts[1])
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv))
                return String(cipher.doFinal(data), Charsets.UTF_8)
            }
        }
        val hex = randomHex()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        val data = cipher.doFinal(hex.toByteArray(Charsets.UTF_8))
        AtomicFiles.writeText(f, bytesToHex(cipher.iv) + ":" + bytesToHex(data))
        hex
    }.getOrNull()

    private fun generate(ks: KeyStore): SecretKey {
        val kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        kg.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        val key = kg.generateKey()
        ks.setKeyEntry(ALIAS, key, null, null)
        return key
    }

    private fun randomHex(): String {
        val bytes = ByteArray(32)
        SecureRandom().nextBytes(bytes)
        return bytesToHex(bytes)
    }

    private fun bytesToHex(bytes: ByteArray): String = bytes.joinToString("") { "%02x".format(it) }

    private fun hexToBytes(hex: String): ByteArray =
        hex.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
}
