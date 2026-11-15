package dev.ninfenz.mobile.share

import android.app.Application
import android.content.Intent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ShareExporterTest {
    @Test
    fun launchChooser_fromApplicationContext_addsNewTask() {
        val app: Application = RuntimeEnvironment.getApplication()
        val target = Intent(Intent.ACTION_SEND).setType("text/plain")
        ShareExporter.launchChooser(app, target, "分享")

        val started = shadowOf(app).nextStartedActivity
        assertEquals(Intent.ACTION_CHOOSER, started.action)
        assertNotEquals(0, started.flags and Intent.FLAG_ACTIVITY_NEW_TASK)
    }
}
