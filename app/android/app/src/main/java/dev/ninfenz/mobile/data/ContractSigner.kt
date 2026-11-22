package dev.ninfenz.mobile.data

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import java.security.spec.ECGenParameterSpec

/** 合同签收的密码学签名：生产用 Android Keystore，测试用软件 EC 密钥。 */
interface ContractSigner {
    fun sign(payload: ByteArray): ByteArray
    fun verify(payload: ByteArray, signature: ByteArray): Boolean
    fun publicKey(): ByteArray
}

private const val ALGORITHM = "SHA256withECDSA"
private const val CURVE = "secp256r1"

private fun generateEc(): KeyPair =
    KeyPairGenerator.getInstance("EC").apply {
        initialize(ECGenParameterSpec(CURVE))
    }.generateKeyPair()

/** 进程内软件密钥；只用于 JVM 测试，不持久化。 */
class SoftwareContractSigner(private val keyPair: KeyPair = generateEc()) : ContractSigner {
    override fun sign(payload: ByteArray): ByteArray =
        Signature.getInstance(ALGORITHM).run {
            initSign(keyPair.private)
            update(payload)
            sign()
        }

    override fun verify(payload: ByteArray, signature: ByteArray): Boolean =
        runCatching {
            Signature.getInstance(ALGORITHM).run {
                initVerify(keyPair.public)
                update(payload)
                verify(signature)
            }
        }.getOrDefault(false)

    override fun publicKey(): ByteArray = keyPair.public.encoded
}

/** 设备密钥：私钥不出 Android Keystore；卸载/清除应用后旧签收失效。 */
class AndroidKeystoreSigner(
    private val alias: String = "nf-contract-signing"
) : ContractSigner {
    private val keyStore: KeyStore by lazy {
        KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    }

    private fun ensureKey() {
        if (keyStore.containsAlias(alias)) return
        KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore").apply {
            initialize(
                KeyGenParameterSpec.Builder(
                    alias,
                    KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
                )
                    .setAlgorithmParameterSpec(ECGenParameterSpec(CURVE))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .build()
            )
            generateKeyPair()
        }
    }

    override fun sign(payload: ByteArray): ByteArray {
        ensureKey()
        val key = keyStore.getKey(alias, null) as java.security.PrivateKey
        return Signature.getInstance(ALGORITHM).run {
            initSign(key)
            update(payload)
            sign()
        }
    }

    override fun verify(payload: ByteArray, signature: ByteArray): Boolean =
        runCatching {
            ensureKey()
            val key = keyStore.getCertificate(alias).publicKey
            Signature.getInstance(ALGORITHM).run {
                initVerify(key)
                update(payload)
                verify(signature)
            }
        }.getOrDefault(false)

    override fun publicKey(): ByteArray {
        ensureKey()
        return keyStore.getCertificate(alias).publicKey.encoded
    }
}
