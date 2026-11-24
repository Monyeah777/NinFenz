package dev.ninfenz.mobile.ui.components

import dev.ninfenz.mobile.ui.design.NfType

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** v0.02 视觉壳：旧功能屏复用同一 TopAppBar/卡片/错误视觉，避免开发面板感。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NfScaffold(
    title: String,
    onBack: (() -> Unit)?,
    actions: @Composable RowScope.() -> Unit = {},
    bottomBar: @Composable () -> Unit = {},
    content: @Composable (PaddingValues) -> Unit
) {
    Scaffold(
        modifier = Modifier.semantics { paneTitle = title },
        bottomBar = bottomBar,
        topBar = {
            TopAppBar(
                title = { Text(title, style = NfType.screenTitle, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.semantics { heading() }) },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_back))
                        }
                    }
                },
                actions = actions,
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxWidth()
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = NfSpacing.page, vertical = NfSpacing.m),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            content(padding)
        }
    }
}

@Composable
fun CardBox(title: String?, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)
    ) {
        Column(
            modifier = Modifier.padding(NfSpacing.l),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.s),
            content = {
                if (title != null) {
                    Text(title, style = NfType.screenTitle)
                }
                content()
            }
        )
    }
}

@Composable
fun ErrorNotice(error: dev.ninfenz.mobile.core.CoreError, modifier: Modifier = Modifier) {
    val entry = dev.ninfenz.mobile.core.ErrorCatalog.find(error.code)
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.errorContainer
    ) {
        Column(modifier = Modifier.padding(NfSpacing.m), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
            Text(
                "[" + error.code + "] " + error.message,
                style = NfType.itemTitle,
                color = MaterialTheme.colorScheme.onErrorContainer
            )
            if (error.path != null) {
                Text("path: " + error.path, style = NfType.meta, fontFamily = FontFamily.Monospace)
            }
            Text(
                stringResource(dev.ninfenz.mobile.R.string.error_fix_prefix, entry?.fix?.takeIf { it.isNotBlank() } ?: error.fix),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onErrorContainer
            )
            Text(
                "exit=" + error.exit + " · severity=" + (entry?.severity ?: "unknown") + " · backend=" +
                    dev.ninfenz.mobile.core.Core.bridge.backendName,
                style = NfType.meta
            )
        }
    }
}

@Composable
fun Notice(text: String, tone: Tone = Tone.INFO) {
    val colors = when (tone) {
        Tone.INFO -> MaterialTheme.colorScheme.secondaryContainer to MaterialTheme.colorScheme.onSecondaryContainer
        Tone.WARN -> MaterialTheme.colorScheme.tertiaryContainer to MaterialTheme.colorScheme.onTertiaryContainer
        Tone.ERROR -> MaterialTheme.colorScheme.errorContainer to MaterialTheme.colorScheme.onErrorContainer
    }
    Surface(shape = MaterialTheme.shapes.medium, color = colors.first, contentColor = colors.second, modifier = Modifier.fillMaxWidth()) {
        Text(text = text, style = NfType.meta, modifier = Modifier.padding(NfSpacing.m))
    }
}

enum class Tone { INFO, WARN, ERROR }

@Composable
fun KeyValue(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(text = label, style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(text = value, style = NfType.meta, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun MonoText(text: String) {
    Surface(shape = MaterialTheme.shapes.small, color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f), modifier = Modifier.fillMaxWidth()) {
        Text(text = text, style = NfType.meta, fontFamily = FontFamily.Monospace, modifier = Modifier.padding(NfSpacing.m))
    }
}

@Composable
fun EmptyState(text: String) {
    Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f), modifier = Modifier.fillMaxWidth()) {
        Text(text = text, style = NfType.secondary, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(NfSpacing.l))
    }
}

@Composable
fun FormTextField(label: String, value: String, onValueChange: (String) -> Unit, singleLine: Boolean = true) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        singleLine = singleLine,
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
fun Divider16() {
    Text(text = "", modifier = Modifier.height(2.dp))
}
