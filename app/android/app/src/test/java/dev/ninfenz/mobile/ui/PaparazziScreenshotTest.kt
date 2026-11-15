package dev.ninfenz.mobile.ui

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test

/** W6 截图基线：Paparazzi 在 JVM 渲染 Home（紧凑尺寸）。 */
class PaparazziScreenshotTest {
    @get:Rule
    val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_5)

    @Test
    fun libraryHome() {
        paparazzi.snapshot {
            NfTheme {
                LibraryHomeScreen(
                    packs = emptyList(), projects = emptyList(), errors = emptyList(),
                    seedState = null, seeding = false,
                    onSeed = {}, onImport = {}, onOpenPack = {}, onOpenProject = {},
                    onSearch = {}, onPackCenter = {}, onSettings = {}
                )
            }
        }
    }
}
