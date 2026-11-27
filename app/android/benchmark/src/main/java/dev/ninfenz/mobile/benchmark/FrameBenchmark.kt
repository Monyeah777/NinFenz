package dev.ninfenz.mobile.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class FrameBenchmark {
    @get:Rule
    val rule = MacrobenchmarkRule()

    @Test
    fun scrollHomeAndLibrary() = rule.measureRepeated(
        packageName = "dev.ninfenz.mobile",
        metrics = listOf(FrameTimingMetric()),
        iterations = 5,
        startupMode = StartupMode.COLD,
        compilationMode = CompilationMode.None()
    ) {
        startActivityAndWait()
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        device.swipe(540, 1800, 540, 500, 20)
        device.swipe(540, 500, 540, 1800, 20)
    }
}
