package dev.ninfenz.mobile.ui

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import dev.ninfenz.mobile.ui.screens.DesignSystemScreen
import org.junit.Rule
import org.junit.Test

/** 6 张矩阵快照：浅/深 × 100/130/200%。用于人工核对截断，不做像素比对。 */
class DesignSystemSnapshotTest {
    @get:Rule
    val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_5)

    @Test
    fun sixScaleThemeSnapshots() {
        for (dark in listOf(false, true)) {
            for (scale in listOf(1f, 1.3f, 2f)) {
                val name = (if (dark) "dark" else "light") + "-" + (scale * 100).toInt()
                paparazzi.snapshot(name = name) {
                    DesignSystemScreen(onBack = {}, initialDark = dark, initialScale = scale)
                }
            }
        }
    }
}
