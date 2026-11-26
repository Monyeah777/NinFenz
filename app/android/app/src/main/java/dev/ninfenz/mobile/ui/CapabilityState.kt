package dev.ninfenz.mobile.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import dev.ninfenz.mobile.data.CapabilityRegistry

/** 订阅模块开关版本，供 Compose 页面实时刷新入口门控。 */
@Composable
fun rememberCapabilityRevision(): Int {
    var revision by remember { mutableIntStateOf(CapabilityRegistry.revision) }
    DisposableEffect(Unit) {
        val remove = CapabilityRegistry.observe { revision = CapabilityRegistry.revision }
        onDispose { remove() }
    }
    return revision
}
