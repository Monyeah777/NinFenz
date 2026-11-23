package dev.ninfenz.mobile.ui.design.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.design.LocalNfSemantic
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.design.Radius
import dev.ninfenz.mobile.ui.design.Sizes
import dev.ninfenz.mobile.ui.design.Space
import dev.ninfenz.mobile.ui.design.shortHash

/** 状态色：只用于表达状态，不承担装饰。 */
enum class NfStatusTone { NEUTRAL, BRAND, SUCCESS, WARNING, ERROR, INFO }

@Composable
private fun toneColors(tone: NfStatusTone): Pair<Color, Color> {
    val cs = MaterialTheme.colorScheme
    val semantic = LocalNfSemantic.current
    return when (tone) {
        NfStatusTone.NEUTRAL -> cs.surfaceVariant to cs.onSurfaceVariant
        NfStatusTone.BRAND -> cs.primaryContainer to cs.onPrimaryContainer
        NfStatusTone.SUCCESS -> semantic.successContainer to semantic.onSuccessContainer
        NfStatusTone.WARNING -> semantic.warningContainer to semantic.onWarningContainer
        NfStatusTone.ERROR -> cs.errorContainer to cs.onErrorContainer
        NfStatusTone.INFO -> semantic.infoContainer to semantic.onInfoContainer
    }
}

/** 状态 = 颜色 + 文字 + 圆点（形状），不只靠颜色。 */
@Composable
fun NfStatusChip(
    label: String,
    modifier: Modifier = Modifier,
    tone: NfStatusTone = NfStatusTone.NEUTRAL
) {
    val (bg, fg) = toneColors(tone)
    Surface(
        modifier = modifier,
        color = bg,
        contentColor = fg,
        shape = RoundedCornerShape(percent = 50)
    ) {
        Row(
            modifier = Modifier
                .height(32.dp)
                .padding(horizontal = Space.itemGap.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .background(fg, CircleShape)
            )
            Spacer(Modifier.width(6.dp))
            Text(text = label, style = NfType.label, color = fg)
        }
    }
}

/** 信任刻度：5 段对应 T0–T4，当前级别配 mono 标注与一句人话。 */
@Composable
fun NfTrustMeter(
    level: Int,
    caption: String,
    modifier: Modifier = Modifier
) {
    val cs = MaterialTheme.colorScheme
    Row(modifier = modifier, verticalAlignment = Alignment.CenterVertically) {
        repeat(5) { index ->
            Box(
                modifier = Modifier
                    .width(24.dp)
                    .height(6.dp)
                    .background(
                        color = if (index < level) cs.primary else cs.outlineVariant,
                        shape = RoundedCornerShape(2.dp)
                    )
            )
            if (index < 4) Spacer(Modifier.width(4.dp))
        }
        Spacer(Modifier.width(Space.gap.dp))
        Text(text = "T$level", style = NfType.mono, color = cs.onSurface)
        Spacer(Modifier.width(Space.inline.dp))
        Text(text = caption, style = NfType.meta, color = cs.onSurfaceVariant)
    }
}

/** 错误三段式：码 / 发生了什么 / 怎么修。 */
@Composable
fun NfErrorBlock(
    code: String,
    what: String,
    fix: String,
    modifier: Modifier = Modifier
) {
    val cs = MaterialTheme.colorScheme
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = cs.errorContainer,
        contentColor = cs.onErrorContainer,
        shape = RoundedCornerShape(Radius.sm.dp)
    ) {
        Column(
            modifier = Modifier.padding(Space.gutter.dp),
            verticalArrangement = Arrangement.spacedBy(Space.gap.dp)
        ) {
            Text(text = code, style = NfType.mono)
            Text(text = what, style = NfType.body)
            Text(text = "修复：$fix", style = NfType.body)
        }
    }
}

/** 哈希：4 字符分组，中间省略，单行不拆断。 */
@Composable
fun NfHashBlock(raw: String, modifier: Modifier = Modifier, label: String = "sha256") {
    val cs = MaterialTheme.colorScheme
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = cs.surfaceVariant,
        contentColor = cs.onSurface,
        shape = RoundedCornerShape(Radius.sm.dp)
    ) {
        Column(
            modifier = Modifier.padding(Space.itemGap.dp),
            verticalArrangement = Arrangement.spacedBy(Space.inline.dp)
        ) {
            Text(text = label, style = NfType.meta, color = cs.onSurfaceVariant)
            Text(
                text = shortHash(raw),
                style = NfType.mono,
                maxLines = 1
            )
        }
    }
}

/** 空状态：一句说明 + 一个动作，不放插图。 */
@Composable
fun NfEmptyState(
    text: String,
    modifier: Modifier = Modifier,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = Space.section.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(Space.itemGap.dp)
    ) {
        Text(
            text = text,
            style = NfType.body,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
        if (actionLabel != null && onAction != null) {
            Button(onClick = onAction) { Text(actionLabel, style = NfType.label) }
        }
    }
}

/** 骨架：高度按真实行高占位，避免加载完成时跳版。 */
@Composable
fun NfSkeleton(modifier: Modifier = Modifier, width: Int = 160, height: Int = 20) {
    Box(
        modifier = modifier
            .width(width.dp)
            .height(height.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(Radius.xs.dp))
    )
}

/** 主操作：一屏只允许一个。 */
@Composable
fun NfPrimaryAction(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true
) {
    Button(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        enabled = enabled
    ) {
        Text(text = label, style = NfType.label)
    }
}

/** 区块头：上面留 24，下面留 8，不用分割线。 */
@Composable
fun NfSectionHeader(text: String, modifier: Modifier = Modifier) {
    NfSectionTitle(
        text = text,
        modifier = modifier.padding(top = Space.section.dp, bottom = Space.gap.dp)
    )
}
