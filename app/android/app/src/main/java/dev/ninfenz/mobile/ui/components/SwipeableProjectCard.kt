package dev.ninfenz.mobile.ui.components

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
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.animation.core.Animatable
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.ui.screens.projectStatusLabel
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

/**
 * 库项目卡片：右滑露出删除，>50% 触发；左滑露出工作流，>50% 打开；点击展开详情；入场上浮淡入。
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
    var width by remember { mutableStateOf(0) }

    LaunchedEffect(entry.project.id) {
        delay((index.coerceAtMost(8) * 45L))
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
                    if (offset.value >= 0f) MaterialTheme.colorScheme.error
                    else MaterialTheme.colorScheme.primary
                )
                .padding(horizontal = NfSpacing.l)
        ) {
            if (offset.value > 0f) {
                Row(
                    modifier = Modifier.align(Alignment.CenterStart),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Icon(Icons.Filled.Delete, contentDescription = null, tint = MaterialTheme.colorScheme.onError)
                    Text(stringResource(dev.ninfenz.mobile.R.string.library_swipe_delete), color = MaterialTheme.colorScheme.onError)
                }
            } else if (offset.value < 0f) {
                Row(
                    modifier = Modifier.align(Alignment.CenterEnd),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.library_swipe_flow), color = MaterialTheme.colorScheme.onPrimary)
                    Text("→", color = MaterialTheme.colorScheme.onPrimary)
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
                    .pointerInput(entry.project.id) {
                        detectHorizontalDragGestures(
                            onDragEnd = {
                                scope.launch {
                                    val threshold = width * 0.5f
                                    when {
                                        offset.value > threshold -> {
                                            offset.animateTo(0f)
                                            onDelete()
                                        }
                                        offset.value < -threshold -> {
                                            offset.animateTo(0f)
                                            onFlow()
                                        }
                                        else -> offset.animateTo(0f)
                                    }
                                }
                            },
                            onHorizontalDrag = { change, dragAmount ->
                                change.consume()
                                scope.launch {
                                    val next = (offset.value + dragAmount).coerceIn(-width * 0.75f, width * 0.75f)
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
                                    Text(entry.project.title, style = MaterialTheme.typography.titleMedium)
                                    Text(
                                        entry.project.id,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                NfStatusChip(projectStatusLabel(entry.project))
                                IconButton(onClick = { expanded = !expanded }) {
                                    Icon(
                                        if (expanded) Icons.Filled.KeyboardArrowUp else Icons.Filled.KeyboardArrowDown,
                                        contentDescription = stringResource(
                                            if (expanded) dev.ninfenz.mobile.R.string.action_collapse
                                            else dev.ninfenz.mobile.R.string.action_expand
                                        )
                                    )
                                }
                            }
                            AnimatedVisibility(
                                visible = expanded,
                                enter = fadeIn() + expandVertically(),
                                exit = fadeOut() + shrinkVertically()
                            ) {
                                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                    Text(
                                        entry.project.refs.basePackId + " · " + entry.project.refs.basePackVersion,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(
                                        stringResource(dev.ninfenz.mobile.R.string.project_detail_history, entry.project.historyCount),
                                        style = MaterialTheme.typography.bodySmall,
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
