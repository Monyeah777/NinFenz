package dev.ninfenz.studio

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState
import dev.ninfenz.studio.ui.NfStudioApp

/** NF Studio 入口（Compose Multiplatform Desktop，JVM toolchain 21）。 */
fun main() = application {
    Window(
        onCloseRequest = ::exitApplication,
        title = "NF Studio",
        state = rememberWindowState(size = DpSize(1280.dp, 840.dp))
    ) {
        MaterialTheme {
            NfStudioApp()
        }
    }
}
