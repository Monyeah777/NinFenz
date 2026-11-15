package dev.ninfenz.mobile.core

/** 核心诊断快照（Settings 诊断页用；不伪造就绪状态）。 */
data class CoreDiagnostics(
    val backend: String,
    val abiVersion: String?,
    val nativeReady: Boolean,
    val errorCodeCount: Int,
    val errorCatalogLoaded: Boolean
)

/**
 * 进程内单例：生产只接原生桥。原生库不在时桥自身返回 NF-E-005——
 * 不做「假核心/演示数据」回退（任务纪律：GL 不准假数据）。
 */
object Core {
    val bridge: CoreBridge by lazy { CoreBridgeNative() }

    fun diagnostics(): CoreDiagnostics = CoreDiagnostics(
        backend = bridge.backendName,
        abiVersion = bridge.abiVersion(),
        nativeReady = bridge.abiVersion() != null,
        errorCodeCount = ErrorCatalog.all().size,
        errorCatalogLoaded = ErrorCatalog.isLoaded()
    )
}
