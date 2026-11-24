package dev.ninfenz.mobile.ui.components

import dev.ninfenz.mobile.ui.design.NfType

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.ui.screens.projectStatusLabel
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * 库项目卡片：左滑露出归档（DELETE），右滑露出工作流；>50% 触发；点击展开详情；入场上浮淡入。
 */
@Composable
fun SwipeableProjectCard(
    entry: ProjectEntry,
    index: Int,
    onOpen: () -> Unit,
    onFlow: () -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier
) {
    var expanded by remember(entry.project.id) { mutableStateOf(false) }
    var visible by remember(entry.project.id) { mutableStateOf(false) }
    val offset = remember(entry.project.id) { Animatable(0f) }
    val scope = rememberCoroutineScope()
    var width by remember { mutableIntStateOf(0) }
    var armed by remember { mutableStateOf(false) }
    val haptic = LocalHapticFeedback.current

    LaunchedEffect(entry.project.id) {
        delay((index.coerceAtMost(6) * 35L))
        visible = true
    }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
    ) {
        // 底层操作面
        Box(
            modifier = Modifier
                .matchParentSize()
                .clip(RoundedCornerShape(24.dp))
                .background(
                    when {
                        offset.value > 1f -> MaterialTheme.colorScheme.primary
                        offset.value < -1f -> MaterialTheme.colorScheme.error
                        else -> androidx.compose.ui.graphics.Color.Transparent
                    }
                )
                .padding(horizontal = NfSpacing.l)
        ) {
            val reveal = (abs(offset.value) / (width * 0.35f).coerceAtLeast(1f)).coerceIn(0f, 1f)
            if (offset.value > 0f) {
                Row(
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .alpha(reveal),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.library_swipe_flow), color = MaterialTheme.colorScheme.onPrimary)
                    Text("→", color = MaterialTheme.colorScheme.onPrimary)
                }
            } else if (offset.value < 0f) {
                Row(
                    modifier = Modifier
                        .align(Alignment.CenterEnd)
                        .alpha(reveal),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Icon(Icons.Filled.Delete, contentDescription = null, tint = MaterialTheme.colorScheme.onError)
                    Text(stringResource(dev.ninfenz.mobile.R.string.library_swipe_delete), color = MaterialTheme.colorScheme.onError)
                }
            }
        }

        AnimatedVisibility(
            visible = visible,
            enter = fadeIn() + expandVertically(expandFrom = Alignment.Top),
            exit = fadeOut() + shrinkVertically()
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .offset { IntOffset(offset.value.roundToInt(), 0) }
                    .graphicsLayer {
                        val dragFraction = (abs(offset.value) / (width * 0.5f).coerceAtLeast(1f)).coerceIn(0f, 1f)
                        scaleX = 1f - dragFraction * 0.012f
                        scaleY = 1f - dragFraction * 0.012f
                    }
                    .pointerInput(entry.project.id) {
                        detectHorizontalDragGestures(
                            onDragEnd = {
                                scope.launch {
                                    val threshold = width * 0.5f
                                    armed = false
                                    val settle = spring<Float>(dampingRatio = 0.78f, stiffness = 420f)
                                    when {
                                        offset.value > threshold -> {
                                            offset.animateTo(0f, animationSpec = settle)
                                            onFlow()
                                        }
                                        offset.value < -threshold -> {
                                            offset.animateTo(0f, animationSpec = settle)
                                            onDelete()
                                        }
                                        else -> offset.animateTo(0f, animationSpec = settle)
                                    }
                                }
                            },
                            onHorizontalDrag = { change, dragAmount ->
                                change.consume()
                                scope.launch {
                                    val edge = width * 0.75f
                                    val resistance = 1f - (abs(offset.value) / edge.coerceAtLeast(1f) * 0.45f).coerceIn(0f, 0.45f)
                                    val next = (offset.value + dragAmount * resistance).coerceIn(-edge, edge)
                                    val crossed = width > 0 && kotlin.math.abs(next) >= width * 0.5f
                                    if (crossed && !armed) {
                                        armed = true
                                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    } else if (!crossed) {
                                        armed = false
                                    }
                                    offset.snapTo(next)
                                }
                            }
                        )
                    }
            ) {
                androidx.compose.foundation.layout.BoxWithConstraints {
                    width = constraints.maxWidth
                    NfCard(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onOpen() },
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        entry.project.title,
                                        style = NfType.itemTitle,
                                        maxLines = 2,
                                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                    )
                                    Text(
                                        entry.project.id,
                                        style = NfType.meta,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                NfStatusChip(projectStatusLabel(entry.project))
                                val chevron by animateFloatAsState(
                                    targetValue = if (expanded) 180f else 0f,
                                    animationSpec = tween(durationMillis = 220),
                                    label = "project-chevron"
                                )
                                IconButton(onClick = { expanded = !expanded }) {
                                    Icon(
                                        Icons.Filled.KeyboardArrowDown,
                                        contentDescription = stringResource(
                                            if (expanded) dev.ninfenz.mobile.R.string.action_collapse
                                            else dev.ninfenz.mobile.R.string.action_expand
                                        ),
                                        modifier = Modifier.rotate(chevron)
                                    )
                                }
                            }
                            AnimatedVisibility(
                                visible = expanded,
                                enter = fadeIn(tween(180)) + expandVertically(
                                    animationSpec = spring(dampingRatio = 0.82f, stiffness = 380f),
                                    expandFrom = Alignment.Top
                                ),
                                exit = fadeOut(tween(120)) + shrinkVertically(
                                    animationSpec = spring(dampingRatio = 0.9f, stiffness = 480f),
                                    shrinkTowards = Alignment.Top
                                )
                            ) {
                                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                    Text(
                                        entry.project.refs.basePackId + " · " + entry.project.refs.basePackVersion,
                                        style = NfType.meta,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(
                                        stringResource(dev.ninfenz.mobile.R.string.project_detail_history, entry.project.historyCount),
                                        style = NfType.meta,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                        androidx.compose.material3.TextButton(onClick = onOpen) {
                                            Text(stringResource(dev.ninfenz.mobile.R.string.flow_open_project))
                                        }
                                        androidx.compose.material3.TextButton(onClick = onFlow) {
                                            Text(stringResource(dev.ninfenz.mobile.R.string.flow_title))
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
