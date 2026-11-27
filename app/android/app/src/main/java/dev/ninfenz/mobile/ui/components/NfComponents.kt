package dev.ninfenz.mobile.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.ColumnScope
import dev.ninfenz.mobile.ui.theme.NfLayout
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.style.TextOverflow as NfTextOverflow
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NfTopAppBar(
    title: String,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {}
) {
    TopAppBar(
        title = { Text(title, style = NfType.screenTitle, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.semantics { heading() }) },
        navigationIcon = {
            if (onBack != null) {
                IconButton(onClick = onBack, modifier = Modifier.size(48.dp)) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_back))
                }
            }
        },
        actions = actions,
        colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent)
    )
}

/** 结构型步骤条：用短标签表达当前处于流程第几步，横向可滚动。 */
@Composable
fun NfStepStrip(steps: List<String>, current: Int, modifier: Modifier = Modifier, onStepClick: ((Int) -> Unit)? = null) {
    val progressText = stringResource(dev.ninfenz.mobile.R.string.step_progress, current + 1, steps.size)
    Row(
        modifier = modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .semantics { stateDescription = progressText }
            .padding(horizontal = NfLayout.pageCompact, vertical = NfSpacing.s),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        steps.forEachIndexed { index, label ->
            val active = index == current
            Surface(
                modifier = if (onStepClick != null) Modifier.clickable { onStepClick(index) } else Modifier,
                shape = MaterialTheme.shapes.large,
                color = if (active) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
                contentColor = if (active) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant
            ) {
                Text(
                    label,
                    style = NfType.label,
                    modifier = Modifier.padding(horizontal = NfSpacing.s, vertical = 8.dp)
                )
            }
            if (index < steps.lastIndex) {
                Text("›", color = if (index < current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline)
            }
        }
        Text(
            stringResource(dev.ninfenz.mobile.R.string.step_progress, current + 1, steps.size),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = NfSpacing.s)
        )
    }
}

@Composable
fun NfSectionHeader(text: String, modifier: Modifier = Modifier, action: (@Composable () -> Unit)? = null) {
    Row(
        modifier = modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).padding(horizontal = NfLayout.pageCompact),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(text, style = NfType.sectionTitle, modifier = Modifier.semantics { heading() })
        action?.invoke()
    }
}

/** 可折叠分组：标题行常驻，内容可收起/展开，适合长表单与长预览。 */
@Composable
fun NfCollapsibleSection(
    title: String,
    subtitle: String? = null,
    initiallyExpanded: Boolean = true,
    content: @Composable ColumnScope.() -> Unit
) {
    var expanded by remember { mutableStateOf(initiallyExpanded) }
    Column(modifier = Modifier.fillMaxWidth().animateContentSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = !expanded }
                .padding(horizontal = NfLayout.pageCompact, vertical = NfSpacing.s),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(title, style = NfType.itemTitle, modifier = Modifier.semantics { heading() })
                subtitle?.let {
                    Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Icon(
                imageVector = if (expanded) Icons.Filled.KeyboardArrowUp else Icons.Filled.KeyboardArrowDown,
                contentDescription = stringResource(if (expanded) dev.ninfenz.mobile.R.string.action_collapse else dev.ninfenz.mobile.R.string.action_expand)
            )
        }
        if (expanded) {
            Column(content = content)
        }
    }
}

/** 长文本预览：默认截断，展开后限高滚动，避免把整页撑爆。 */
@Composable
fun NfExpandableText(
    text: String,
    modifier: Modifier = Modifier,
    collapsedLines: Int = 12,
    collapsedChars: Int = 600
) {
    var expanded by remember { mutableStateOf(false) }
    val estimatedLines = text.split('\n').sumOf { line -> (line.length / 24) + 1 }
    val needsToggle = text.length > collapsedChars || estimatedLines > collapsedLines
    Column(modifier = modifier.fillMaxWidth()) {
        Box(
            modifier = if (expanded) {
                Modifier.fillMaxWidth().heightIn(max = 420.dp).verticalScroll(rememberScrollState())
            } else {
                Modifier.fillMaxWidth()
            }
        ) {
            Text(
                text = text,
                style = NfType.secondary,
                maxLines = if (expanded) Int.MAX_VALUE else collapsedLines,
                overflow = NfTextOverflow.Ellipsis
            )
        }
        if (needsToggle) {
            TextButton(onClick = { expanded = !expanded }) {
                Text(stringResource(if (expanded) dev.ninfenz.mobile.R.string.action_collapse else dev.ninfenz.mobile.R.string.action_expand))
            }
        }
    }
}

@Composable
fun NfEmptyState(
    icon: ImageVector,
    title: String,
    message: String,
    actionLabel: String,
    onAction: () -> Unit,
    modifier: Modifier = Modifier,
    secondaryLabel: String? = null,
    onSecondary: (() -> Unit)? = null
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(NfSpacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(48.dp)
        )
        Text(title, style = NfType.screenTitle, textAlign = androidx.compose.ui.text.style.TextAlign.Center, modifier = Modifier.semantics { heading() })
        Text(
            message,
            style = NfType.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
        Button(onClick = onAction, modifier = Modifier.heightIn(min = 48.dp)) { Text(actionLabel) }
        if (secondaryLabel != null && onSecondary != null) {
            TextButton(onClick = onSecondary) { Text(secondaryLabel) }
        }
    }
}

@Composable
fun NfCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable () -> Unit
) {
    val haptic = LocalHapticFeedback.current
    Surface(
        modifier = if (onClick != null) modifier.fillMaxWidth().clickable(role = Role.Button) { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); onClick() } else modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
        tonalElevation = 0.dp
    ) {
        Box(modifier = Modifier.padding(NfSpacing.l)) { content() }
    }
}

@Composable
fun NfStatusChip(label: String, color: Color = MaterialTheme.colorScheme.primary) {
    Surface(shape = RoundedCornerShape(percent = 50), color = color.copy(alpha = 0.12f), contentColor = color) {
        Text(
            text = label,
            style = NfType.label,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
        )
    }
}

@Composable
fun NfListRow(
    title: String,
    subtitle: String? = null,
    leading: ImageVector? = null,
    trailing: String? = null,
    onClick: () -> Unit
) {
    val haptic = LocalHapticFeedback.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(role = Role.Button) { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); onClick() }
            .padding(horizontal = NfSpacing.page, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.m)
    ) {
        if (leading != null) {
            Icon(leading, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(title, style = NfType.itemTitle, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (subtitle != null) {
                Text(
                    subtitle,
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
        if (trailing != null) Text(trailing, style = NfType.body)
    }
}

