package dev.ninfenz.mobile.ui

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test

@Composable
private fun LibraryHomeForShot() {
    NfTheme {
        LibraryHomeScreen(
            packs = emptyList(), projects = emptyList(), errors = emptyList(),
            seedState = null, seeding = false,
            onSeed = {}, onImport = {}, onOpenPack = {}, onOpenProject = {},
            onSearch = {}, onPackCenter = {}, onSettings = {}
        )
    }
}

private fun shotConfig(width: Int, height: Int): DeviceConfig =
    DeviceConfig.PIXEL_5.copy(screenWidth = width, screenHeight = height)

class Paparazzi360x640Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(360, 640))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi360x800Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(360, 800))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi360x1000Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(360, 1000))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi700x640Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(700, 640))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi700x900Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(700, 900))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi700x1000Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(700, 1000))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi900x640Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(900, 640))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi900x900Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(900, 900))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class Paparazzi900x1000Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = shotConfig(900, 1000))
    @Test fun home() { paparazzi.snapshot { LibraryHomeForShot() } }
}

class PaparazziFontScale200Test {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_5)
    @Test fun home200() {
        paparazzi.snapshot {
            CompositionLocalProvider(LocalDensity provides Density(1f, 2f)) {
                LibraryHomeForShot()
            }
        }
    }
}
