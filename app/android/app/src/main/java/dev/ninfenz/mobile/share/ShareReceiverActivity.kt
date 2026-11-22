package dev.ninfenz.mobile.share

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.MainActivity
import dev.ninfenz.mobile.ui.theme.NfTheme

/**
 * 透明分享接收（SEND / SEND_MULTIPLE / VIEW / PROCESS_TEXT）：
 * 只做「确认后转交主界面导入」，不在本 Activity 解析内容、不落盘。
 */
class ShareReceiverActivity : ComponentActivity() {

    private var payloadState by mutableStateOf<SharePayload?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        payloadState = payloadOf(intent)
        setContent {
            NfTheme {
                Surface(color = MaterialTheme.colorScheme.surface) {
                    ReceiveCard(
                        payload = payloadState ?: SharePayload(SharePayloadParser.kindOf(null), null, emptyList(), null),
                        onConfirm = {
                            val current = payloadState
                            if (current != null && current.count > 0) {
                                ShareHandoff.offer(current)
                                startActivity(Intent(this, MainActivity::class.java).apply {
                                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                                })
                            }
                            finish()
                        },
                        onCancel = {
                            setResult(Activity.RESULT_CANCELED)
                            finish()
                        }
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        payloadState = payloadOf(intent)
    }

    private fun payloadOf(intent: Intent?): SharePayload {
        if (intent == null) {
            return SharePayload(SharePayloadParser.kindOf(null), null, emptyList(), null)
        }
        val action = intent.action
        val mime = intent.type
        val text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT)
        val process = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)
        val uris = mutableListOf<String>()
        @Suppress("DEPRECATION")
        val single = intent.getParcelableExtra(Intent.EXTRA_STREAM) as? android.net.Uri
        if (single != null) uris.add(single.toString())
        val clip = intent.clipData
        if (clip != null) {
            for (i in 0 until clip.itemCount) {
                val uri = clip.getItemAt(i).uri
                if (uri != null && uri.toString() !in uris) uris.add(uri.toString())
            }
        }
        if (Intent.ACTION_VIEW == action && intent.data != null && intent.data.toString() !in uris) {
            uris.add(intent.data.toString())
        }
        return SharePayloadParser.parse(action, mime, text, uris, process)
    }
}

@Composable
private fun ReceiveCard(
    payload: SharePayload,
    onConfirm: () -> Unit,
    onCancel: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(text = stringResource(dev.ninfenz.mobile.R.string.share_receive_title), style = MaterialTheme.typography.headlineSmall)
        Text(
            text = payload.summary(
                itemLabel = pluralStringResource(dev.ninfenz.mobile.R.plurals.share_payload_items, payload.count, payload.count),
                processLabel = payload.processText?.let {
                    pluralStringResource(dev.ninfenz.mobile.R.plurals.share_payload_process, it.length, it.length)
                }
            ),
            style = MaterialTheme.typography.bodyMedium
        )
        if (payload.count == 0) {
            Text(
                text = stringResource(dev.ninfenz.mobile.R.string.share_receive_empty, payload.kind),
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall
            )
        } else {
            Text(
                text = stringResource(dev.ninfenz.mobile.R.string.share_receive_confirm),
                style = MaterialTheme.typography.bodySmall
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedButton(onClick = onCancel, modifier = Modifier.width(120.dp)) {
                Text(stringResource(android.R.string.cancel))
            }
            Button(
                onClick = onConfirm,
                enabled = payload.count > 0,
                modifier = Modifier.width(140.dp).padding(start = 8.dp)
            ) {
                Text(stringResource(dev.ninfenz.mobile.R.string.share_receive_go))
            }
        }
    }
}
