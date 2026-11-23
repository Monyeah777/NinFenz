package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.isSystemInDarkTheme
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.design.Contrast
import dev.ninfenz.mobile.ui.design.ContrastPairs
import dev.ninfenz.mobile.ui.design.Layout
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.design.Palette
import dev.ninfenz.mobile.ui.design.Radius
import dev.ninfenz.mobile.ui.design.Sizes
import dev.ninfenz.mobile.ui.design.Space
import dev.ninfenz.mobile.ui.design.TypeScale
import dev.ninfenz.mobile.ui.design.components.NfBody
import dev.ninfenz.mobile.ui.design.components.NfEmptyState
import dev.ninfenz.mobile.ui.design.components.NfErrorBlock
import dev.ninfenz.mobile.ui.design.components.NfHashBlock
import dev.ninfenz.mobile.ui.design.components.NfItemTitle
import dev.ninfenz.mobile.ui.design.components.NfLabel
import dev.ninfenz.mobile.ui.design.components.NfMeta
import dev.ninfenz.mobile.ui.design.components.NfMono
import dev.ninfenz.mobile.ui.design.components.NfNumeric
import dev.ninfenz.mobile.ui.design.components.NfPrimaryAction
import dev.ninfenz.mobile.ui.design.components.NfScreenTitle
import dev.ninfenz.mobile.ui.design.components.NfSectionHeader
import dev.ninfenz.mobile.ui.design.components.NfSecondary
import dev.ninfenz.mobile.ui.design.components.NfSkeleton
import dev.ninfenz.mobile.ui.design.components.NfStatusChip
import dev.ninfenz.mobile.ui.design.components.NfStatusTone
import dev.ninfenz.mobile.ui.design.components.NfTrustMeter
import dev.ninfenz.mobile.ui.theme.NfDesignTheme

/**
 * 设计系统演示屏（debug 入口）：令牌、字阶、间距、色卡（实算对比度）、组件、缩放矩阵。
 * 深浅与缩放都在这屏内模拟，不改系统设置。
 */
@Composable
fun DesignSystemScreen(onBack: () -> Unit) {
    val systemDark = isSystemInDarkTheme()
    var dark by remember { mutableStateOf(systemDark) }
    var fontScale by remember { mutableStateOf(1f) }
    val base = LocalDensity.current

    NfDesignTheme(darkTheme = dark) {
        CompositionLocalProvider(
            LocalDensity provides Density(density = base.density, fontScale = base.fontScale * fontScale)
        ) {
            NfScaffold(title = "设计系统", onBack = onBack) {
                Row(horizontalArrangement = Arrangement.spacedBy(Space.gap.dp)) {
                    OutlinedButton(onClick = { dark = false }) { Text("浅色") }
                    OutlinedButton(onClick = { dark = true }) { Text("深色") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(Space.gap.dp)) {
                    OutlinedButton(onClick = { fontScale = 1f }) { Text("100%") }
                    OutlinedButton(onClick = { fontScale = 1.3f }) { Text("130%") }
                    OutlinedButton(onClick = { fontScale = 2f }) { Text("200%") }
                }
                NfMeta("当前：${if (dark) "深色" else "浅色"} · 缩放 ${(fontScale * 100).toInt()}%")

                NfSectionHeader("字阶（4 级）")
                TypeScale.all.forEach { token ->
                    Column(verticalArrangement = Arrangement.spacedBy(Space.inline.dp)) {
                        Text(
                            text = "${token.name}  ${token.size.toInt()}/${token.line.toInt()}  w${token.weight}",
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "内容库 Content 123",
                            style = when (token.name) {
                                "title.screen" -> NfType.screenTitle
                                "title.section" -> NfType.sectionTitle
                                "title.item" -> NfType.itemTitle
                                "body.long" -> NfType.bodyLong
                                "body.secondary" -> NfType.secondary
                                "label" -> NfType.label
                                "meta" -> NfType.meta
                                "mono" -> NfType.mono
                                else -> NfType.body
                            }
                        )
                    }
                }

                NfSectionHeader("间距（4 的倍数）")
                Space.all.forEach { value ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .width(value.dp)
                                .height(8.dp)
                                .background(MaterialTheme.colorScheme.primary)
                        )
                        Spacer(Modifier.width(Space.gap.dp))
                        NfMeta("${value}dp")
                    }
                }

                NfSectionHeader("颜色与对比度")
                ContrastPairs.all.forEach { pair ->
                    val ratio = Contrast.ratio(pair, dark)
                    val pass = ratio >= pair.min
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .background(Color(if (dark) pair.bg.dark else pair.bg.light))
                                .border(
                                    width = 1.dp,
                                    color = MaterialTheme.colorScheme.outline,
                                    shape = RoundedCornerShape(Radius.xs.dp)
                                )
                        )
                        Spacer(Modifier.width(Space.gap.dp))
                        NfMeta(pair.name)
                        Spacer(Modifier.width(Space.gap.dp))
                        NfMono("${"%.2f".format(ratio)} ${if (pass) "OK" else "FAIL"}")
                    }
                }

                NfSectionHeader("组件")
                Row(horizontalArrangement = Arrangement.spacedBy(Space.gap.dp)) {
                    NfStatusChip("草稿", tone = NfStatusTone.NEUTRAL)
                    NfStatusChip("已签收", tone = NfStatusTone.SUCCESS)
                    NfStatusChip("待复核", tone = NfStatusTone.WARNING)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(Space.gap.dp)) {
                    NfStatusChip("错误", tone = NfStatusTone.ERROR)
                    NfStatusChip("信息", tone = NfStatusTone.INFO)
                    NfStatusChip("交付中", tone = NfStatusTone.BRAND)
                }
                NfTrustMeter(level = 2, caption = "可复核，未签收")
                NfScreenTitle("屏幕标题 22")
                Text(text = "区块标题 16/600", style = NfType.sectionTitle)
                NfItemTitle("条目标题 16/500")
                NfBody("正文 16/24。中文行距 1.5，字距 0，断行交给系统。")
                NfSecondary("次要正文 14/20，用于辅助说明。")
                NfMeta("元信息 12/20 · 3 分钟前")
                NfHashBlock("88d26e9a4f1c2b3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5")
                NfNumeric("1,284")
                NfErrorBlock(
                    code = "[NF-E-003]",
                    what = "剪贴板为空。",
                    fix = "先复制一段内容，再点粘贴。"
                )
                NfSkeleton(width = 200, height = 20)
                NfEmptyState(text = "尚无项目。新建或导入一段内容开始。", actionLabel = "新建项目", onAction = {})
                NfPrimaryAction(label = "开始成稿", onClick = {})

                NfSectionHeader("7 态")
                NfMeta("空 / 加载 / 错误 / 离线 / 部分成功 / 已签 / 已过期")
                Row(horizontalArrangement = Arrangement.spacedBy(Space.gap.dp)) {
                    NfStatusChip("空", tone = NfStatusTone.NEUTRAL)
                    NfStatusChip("加载中", tone = NfStatusTone.INFO)
                    NfStatusChip("错误", tone = NfStatusTone.ERROR)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(Space.gap.dp)) {
                    NfStatusChip("离线", tone = NfStatusTone.WARNING)
                    NfStatusChip("部分成功", tone = NfStatusTone.WARNING)
                    NfStatusChip("已签", tone = NfStatusTone.SUCCESS)
                    NfStatusChip("已过期", tone = NfStatusTone.NEUTRAL)
                }

                NfSectionHeader("尺寸")
                NfMono("touch ${Sizes.touchTarget}dp · appbar ${Sizes.topAppBar}dp · button ${Sizes.button}dp")
                NfMono("field ${Sizes.textField}dp · row ${Sizes.listOneLine}/${Sizes.listTwoLine}dp")
                NfMono("nav ${Sizes.navigationBar}dp · content max ${Layout.maxContentWidth}dp")
            }
        }
    }
}
