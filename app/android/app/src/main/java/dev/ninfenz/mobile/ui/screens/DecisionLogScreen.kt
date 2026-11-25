package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.data.DecisionStore
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

/** 自动动作的“为什么/撤销”：只展示本地记录，不联网。 */
@Composable
fun DecisionLogScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val store = remember { DecisionStore(context.filesDir) }
    var records by remember { mutableStateOf(store.load()) }
    NfScaffold(title = stringResource(R.string.decision_log_title), onBack = onBack) {
        if (records.isEmpty()) {
            Text(stringResource(R.string.decision_log_empty), style = NfType.body)
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                items(records, key = { it.id }) { r ->
                    CardBox(title = r.action) {
                        Text(r.reason, style = NfType.body)
                        Text(
                            if (r.reversed) stringResource(R.string.decision_log_reversed)
                            else if (r.undoable) stringResource(R.string.decision_log_undoable)
                            else stringResource(R.string.decision_log_final),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        if (r.undoable && !r.reversed) {
                            OutlinedButton(onClick = {
                                if (store.reverse(r.id)) records = store.load()
                            }) { Text(stringResource(R.string.decision_log_undo)) }
                        }
                    }
                }
            }
        }
    }
}
