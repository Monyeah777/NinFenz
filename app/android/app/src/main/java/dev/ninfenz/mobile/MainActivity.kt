package dev.ninfenz.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dev.ninfenz.mobile.ui.NfMobileApp
import dev.ninfenz.mobile.ui.theme.NfTheme

/** 主界面：edge-to-edge + 预测返回（manifest enableOnBackInvokedCallback=true）。 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            NfTheme {
                NfMobileApp()
            }
        }
    }
}
