package dev.ninfenz.mobile.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.ui.draw.clip
import dev.ninfenz.mobile.ui.theme.NfLayout
import dev.ninfenz.mobile.ui.theme.NfMotion
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.MoreVert
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
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
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
fun NfStepStrip(steps: List<String>, current: Int, modifier: Modifier = Modifier) {
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

/** 顶部栏溢出菜单按钮（可选；当前用于详情页占位）。 */
@Composable
fun NfOverflowButton(onClick: () -> Unit) {
    IconButton(onClick = onClick, modifier = Modifier.size(48.dp)) {
        Icon(Icons.Filled.MoreVert, contentDescription = stringResource(dev.ninfenz.mobile.R.string.common_more))
    }
}

/** 标题 + 说明的可访问性占位（空态/加载态共用）。 */
@Composable
fun NfHint(text: String) {
    Spacer(modifier = Modifier.height(NfSpacing.s))
    Text(
        text = text,
        style = NfType.meta,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = NfSpacing.page)
    )
}

@Composable
fun NfErrorCard(code: String, message: String, fix: String, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite },
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.errorContainer
    ) {
        Column(modifier = Modifier.padding(NfSpacing.m), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
            val hint = when (code) {
                "NF-IMP-001" -> stringResource(dev.ninfenz.mobile.R.string.error_hint_import_source)
                "NF-IMP-003" -> stringResource(dev.ninfenz.mobile.R.string.error_hint_file_too_large)
                "NF-E-003" -> stringResource(dev.ninfenz.mobile.R.string.error_hint_clipboard_empty)
                "NF-E-004" -> stringResource(dev.ninfenz.mobile.R.string.error_hint_file_read)
                "NF-PCK-001" -> stringResource(dev.ninfenz.mobile.R.string.error_hint_pack_update)
                "NF-REV-002" -> stringResource(dev.ninfenz.mobile.R.string.error_hint_review)
                else -> null
            }
            Text("[" + code + "] " + (hint ?: message), style = NfType.itemTitle, color = MaterialTheme.colorScheme.onErrorContainer)
            if (hint != null) {
                Text(message, style = NfType.meta, color = MaterialTheme.colorScheme.onErrorContainer)
            }
            Text(stringResource(dev.ninfenz.mobile.R.string.error_fix_prefix, fix), style = NfType.meta, color = MaterialTheme.colorScheme.onErrorContainer)
        }
    }
}

/** 统一加载态（§18.12 三态组件）：转圈 + 可选文案。 */
@Composable
fun NfLoadingState(message: String? = null) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(NfSpacing.page),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        CircularProgressIndicator()
        message?.let {
            Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** 统一骨架态：最多 5 行、1200ms shimmer；与真实布局同构的占位。 */
@Composable
fun NfSkeleton(lines: Int = 3) {
    val transition = rememberInfiniteTransition(label = "nf-skeleton")
    val alpha by transition.animateFloat(
        initialValue = 0.25f,
        targetValue = 0.6f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = NfMotion.SKELETON_MS),
            repeatMode = RepeatMode.Reverse
        ),
        label = "nf-skeleton-alpha"
    )
    Column(
        modifier = Modifier.fillMaxWidth().padding(NfSpacing.page),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        repeat(lines.coerceIn(1, 5)) { index ->
            Box(
                modifier = Modifier
                    .fillMaxWidth(if (index == lines - 1) 0.6f else 1f)
                    .height(12.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = alpha))
            )
        }
    }
}

