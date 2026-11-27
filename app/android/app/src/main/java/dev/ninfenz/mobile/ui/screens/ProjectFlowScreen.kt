package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.ui.design.NfType

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing

private data class FlowStep(val label: String, val status: ProjectStatus)

/** 左滑卡片进入的工作流引导：五阶段状态 + 唯一下一步。 */
@Composable
fun ProjectFlowScreen(
    project: Project,
    onBack: () -> Unit,
    onAuthor: () -> Unit,
    onDelivery: () -> Unit
) {
    val audit = dev.ninfenz.mobile.data.FeatureGate.auditEnabled()
    val steps = flowSteps(audit)
    val current = currentStep(project.status, audit)
    val nextAuthor = project.status == ProjectStatus.DRAFT || project.status == ProjectStatus.AUTHORING

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.flow_title), onBack = onBack)
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Text(project.title, style = NfType.screenTitle)
                        Text(project.id, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.flow_resume_hint),
                            style = NfType.secondary,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                        steps.forEachIndexed { index, step ->
                            FlowRow(
                                index = index,
                                label = step.label,
                                done = index < current,
                                current = index == current
                            )
                        }
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    if (nextAuthor) {
                        Button(onClick = onAuthor) { Text(stringResource(dev.ninfenz.mobile.R.string.flow_action_author)) }
                    } else {
                        Button(onClick = onDelivery) { Text(stringResource(dev.ninfenz.mobile.R.string.flow_action_delivery)) }
                    }
                    TextButton(onClick = onBack) { Text(stringResource(android.R.string.cancel)) }
                }
            }
        }
    }
}

@Composable
private fun flowSteps(audit: Boolean): List<FlowStep> = if (audit) listOf(
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_create), ProjectStatus.AUTHORING),
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_assemble), ProjectStatus.ASSEMBLED),
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_validate), ProjectStatus.VALIDATED),
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_export), ProjectStatus.EXPORTED),
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_review), ProjectStatus.REVIEWED)
) else listOf(
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_create), ProjectStatus.AUTHORING),
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_assemble), ProjectStatus.ASSEMBLED),
    FlowStep(stringResource(dev.ninfenz.mobile.R.string.flow_step_export), ProjectStatus.EXPORTED)
)

private fun currentStep(status: ProjectStatus, audit: Boolean): Int = when (status) {
    ProjectStatus.DRAFT, ProjectStatus.AUTHORING -> 0
    ProjectStatus.ASSEMBLED -> 1
    ProjectStatus.VALIDATED -> 2
    ProjectStatus.EXPORTED -> if (audit) 3 else 2
    ProjectStatus.REVIEWED -> if (audit) 4 else 2
}

@Composable
private fun FlowRow(index: Int, label: String, done: Boolean, current: Boolean) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        Box(
            modifier = Modifier
                .size(28.dp)
                .clip(CircleShape)
                .background(
                    when {
                        current -> MaterialTheme.colorScheme.primary
                        done -> MaterialTheme.colorScheme.secondary
                        else -> MaterialTheme.colorScheme.surfaceVariant
                    }
                ),
            contentAlignment = Alignment.Center
        ) {
            Text(
                (index + 1).toString(),
                style = NfType.meta,
                color = if (current || done) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = NfType.itemTitle)
            Text(
                stringResource(
                    when {
                        done -> dev.ninfenz.mobile.R.string.flow_stage_done
                        current -> dev.ninfenz.mobile.R.string.flow_stage_current
                        else -> dev.ninfenz.mobile.R.string.flow_stage_pending
                    }
                ),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
