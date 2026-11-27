package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.ui.design.NfType

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.SeedResult
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** 首启 3 步引导（§7.1）：可跳过；示例载入失败可重试，不阻断进入。 */
@Composable
fun OnboardingScreen(
    seedState: SeedResult?,
    seeding: Boolean,
    onSeed: () -> Unit,
    onDone: () -> Unit,
    onSkip: () -> Unit
) {
    var step by remember { mutableIntStateOf(0) }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.surface)
            .statusBarsPadding()
            .padding(NfSpacing.xl),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End
        ) {
            TextButton(onClick = onSkip, modifier = Modifier.heightIn(min = 48.dp)) { Text(stringResource(dev.ninfenz.mobile.R.string.onboarding_skip)) }
        }
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            StepDots(step)
            OnboardingStepContent(step)
            SeedStatus(seedState, seeding, onSeed)
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (step > 0) {
                TextButton(onClick = { step -= 1 }) { Text(stringResource(dev.ninfenz.mobile.R.string.onboarding_prev)) }
            } else {
                Spacer(modifier = Modifier.size(1.dp))
            }
            if (step < 2) {
                Button(onClick = { step += 1 }, modifier = Modifier.heightIn(min = 48.dp)) { Text(stringResource(dev.ninfenz.mobile.R.string.onboarding_next)) }
            } else {
                Button(onClick = onDone) { Text(stringResource(dev.ninfenz.mobile.R.string.onboarding_start)) }
            }
        }
    }
}

@Composable
private fun OnboardingStepContent(step: Int) {
    when (step) {
        0 -> Step(
            icon = { Icon(Icons.Filled.Home, contentDescription = null, modifier = Modifier.size(58.dp), tint = MaterialTheme.colorScheme.primary) },
            title = stringResource(dev.ninfenz.mobile.R.string.onboarding_step0_title),
            body = stringResource(dev.ninfenz.mobile.R.string.onboarding_step0_body)
        )
        1 -> Step(
            icon = { Icon(Icons.AutoMirrored.Filled.List, contentDescription = null, modifier = Modifier.size(58.dp), tint = MaterialTheme.colorScheme.primary) },
            title = stringResource(dev.ninfenz.mobile.R.string.onboarding_step1_title),
            body = stringResource(dev.ninfenz.mobile.R.string.onboarding_step1_body)
        )
        else -> Step(
            icon = { Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(58.dp), tint = MaterialTheme.colorScheme.primary) },
            title = stringResource(dev.ninfenz.mobile.R.string.onboarding_step2_title),
            body = stringResource(dev.ninfenz.mobile.R.string.onboarding_step2_body)
        )
    }
}

@Composable
private fun StepDots(step: Int) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        repeat(3) { index ->
            val color = if (index == step) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = 0.35f)
            Spacer(
                modifier = Modifier
                    .size(if (index == step) 20.dp else 8.dp, 8.dp)
                    .background(color, CircleShape)
            )
        }
    }
}

@Composable
private fun Step(icon: @Composable () -> Unit, title: String, body: String) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
    ) {
        icon()
        Text(title, style = NfType.screenTitle, textAlign = TextAlign.Center)
        Text(
            body,
            style = NfType.body,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun SeedStatus(seedState: SeedResult?, seeding: Boolean, onSeed: () -> Unit) {
    when {
        seeding -> Text(stringResource(dev.ninfenz.mobile.R.string.onboarding_seed_loading), style = NfType.secondary, color = MaterialTheme.colorScheme.onSurfaceVariant)
        seedState is SeedResult.Installed -> Text(
            pluralStringResource(dev.ninfenz.mobile.R.plurals.onboarding_seed_ready, seedState.files, seedState.id, seedState.version, seedState.files),
            style = NfType.secondary,
            color = MaterialTheme.colorScheme.primary
        )
        seedState is SeedResult.AlreadyPresent -> Text(
            stringResource(dev.ninfenz.mobile.R.string.onboarding_seed_exists, seedState.id, seedState.version),
            style = NfType.secondary,
            color = MaterialTheme.colorScheme.primary
        )
        seedState is SeedResult.Failed -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(seedState.message, style = NfType.meta, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
            Text(seedState.fix, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            TextButton(onClick = onSeed, modifier = Modifier.heightIn(min = 48.dp)) { Text(stringResource(dev.ninfenz.mobile.R.string.onboarding_retry)) }
        }
        else -> Button(onClick = onSeed, modifier = Modifier.heightIn(min = 48.dp)) { Text(stringResource(dev.ninfenz.mobile.R.string.onboarding_load_sample)) }
    }
}
