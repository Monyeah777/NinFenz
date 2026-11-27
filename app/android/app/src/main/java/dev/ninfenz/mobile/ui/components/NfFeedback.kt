package dev.ninfenz.mobile.ui.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfMotion
import dev.ninfenz.mobile.ui.theme.NfSpacing

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
