package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
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
    var filter by rememberSaveable { mutableStateOf("all") }
    val visible = records.filter {
        when (filter) {
            "undoable" -> it.undoable && !it.reversed
            "final" -> !it.undoable
            "reversed" -> it.reversed
            else -> true
        }
    }
    NfScaffold(title = stringResource(R.string.decision_log_title), onBack = onBack) {
        if (records.isEmpty()) {
            Text(stringResource(R.string.decision_log_empty), style = NfType.body)
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                        listOf(
                            "all" to R.string.decision_log_all,
                            "undoable" to R.string.decision_log_undoable_filter,
                            "final" to R.string.decision_log_final_filter,
                            "reversed" to R.string.decision_log_reversed_filter
                        ).forEach { (id, label) ->
                            FilterChip(
                                selected = filter == id,
                                onClick = { filter = id },
                                label = { Text(stringResource(label)) }
                            )
                        }
                    }
                }
                if (visible.isEmpty()) {
                    item { Text(stringResource(R.string.decision_log_no_match), style = NfType.meta) }
                }
                items(visible, key = { it.id }) { r ->
                    CardBox(title = r.action) {
                        Text(r.reason, style = NfType.body)
                        Text(
                            java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(r.at)) + " · " +
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
