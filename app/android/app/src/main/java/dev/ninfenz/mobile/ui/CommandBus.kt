package dev.ninfenz.mobile.ui

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/** Activity 键盘事件 → Compose 命令面板；无网络、进程内。 */
object CommandBus {
    private val _requests = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val requests = _requests.asSharedFlow()

    fun request() {
        _requests.tryEmit(Unit)
    }
}
