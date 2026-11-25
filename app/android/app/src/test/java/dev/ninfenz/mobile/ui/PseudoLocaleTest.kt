package dev.ninfenz.mobile.ui

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "en-rXA-w360dp-h640dp-xhdpi")
class PseudoLocaleTest {
    @Test
    fun pseudoLocaleResourcesAreMarked() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val name = context.getString(dev.ninfenz.mobile.R.string.app_name)
        assertTrue(name, name.contains("⟦"))
    }
}
