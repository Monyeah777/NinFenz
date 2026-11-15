package dev.ninfenz.mobile.share

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** 透明接收 Activity 与主界面之间的一次性交接（进程内；consumed 后清空）。 */
object ShareHandoff {
    var pending: SharePayload? by mutableStateOf(null)
        private set

    fun offer(payload: SharePayload) {
        pending = payload
    }

    fun consume(): SharePayload? {
        val current = pending
        pending = null
        return current
    }
}
