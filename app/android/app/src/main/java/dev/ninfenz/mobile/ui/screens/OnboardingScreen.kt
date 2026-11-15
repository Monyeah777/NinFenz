package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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
            TextButton(onClick = onSkip) { Text("跳过") }
        }
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            StepDots(step)
            when (step) {
                0 -> Step(
                    icon = { Icon(Icons.Filled.Home, contentDescription = null, modifier = Modifier.size(56.dp), tint = MaterialTheme.colorScheme.primary) },
                    title = "把内容写进协议",
                    body = "NF 把导入的内容套进协议、管线与规格，再装配、校验、导出。全部在本机完成，不需要网络。"
                )
                1 -> Step(
                    icon = { Icon(Icons.AutoMirrored.Filled.List, contentDescription = null, modifier = Modifier.size(56.dp), tint = MaterialTheme.colorScheme.primary) },
                    title = "先给你一份示例",
                    body = "内置示例 Pack：8 个条目，含协议、管线、规格与素材。载入后即可在「库」里看到它。"
                )
                else -> Step(
                    icon = { Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(56.dp), tint = MaterialTheme.colorScheme.primary) },
                    title = "从一次导入开始",
                    body = "进入「库」后点右下角「导入」，从文件管理器、分享或剪贴板带内容进来。"
                )
            }
            SeedStatus(seedState, seeding, onSeed)
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (step > 0) {
                TextButton(onClick = { step -= 1 }) { Text("上一步") }
            } else {
                Spacer(modifier = Modifier.size(1.dp))
            }
            if (step < 2) {
                Button(onClick = { step += 1 }) { Text("下一步") }
            } else {
                Button(onClick = onDone) { Text("开始使用") }
            }
        }
    }
}

@Composable
private fun StepDots(step: Int) {
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
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
        Text(title, style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
        Text(
            body,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun SeedStatus(seedState: SeedResult?, seeding: Boolean, onSeed: () -> Unit) {
    when {
        seeding -> Text("正在载入示例…", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        seedState is SeedResult.Installed -> Text(
            "示例已就绪：" + seedState.id + " · " + seedState.version + "（" + seedState.files + " 个文件）",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.primary
        )
        seedState is SeedResult.AlreadyPresent -> Text(
            "示例已存在：" + seedState.id + " · " + seedState.version,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.primary
        )
        seedState is SeedResult.Failed -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(seedState.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
            Text(seedState.fix, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            TextButton(onClick = onSeed) { Text("重试") }
        }
        else -> Button(onClick = onSeed) { Text("载入示例 Pack") }
    }
}
