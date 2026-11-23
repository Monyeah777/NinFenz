package dev.ninfenz.mobile.ui.design.components

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import dev.ninfenz.mobile.ui.design.NfType

/**
 * 语义文字组件：业务层只挑角色，不写字号。
 * 每个函数对应一个 TypeToken，避免出现"随手 13sp"。
 */
@Composable
fun NfScreenTitle(text: String, modifier: Modifier = Modifier, color: Color = Color.Unspecified) {
    Text(text = text, modifier = modifier, style = NfType.screenTitle, color = color)
}

@Composable
fun NfSectionTitle(text: String, modifier: Modifier = Modifier, color: Color = Color.Unspecified) {
    Text(text = text, modifier = modifier, style = NfType.sectionTitle, color = color)
}

@Composable
fun NfItemTitle(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    maxLines: Int = 2
) {
    Text(
        text = text,
        modifier = modifier,
        style = NfType.itemTitle,
        color = color,
        maxLines = maxLines,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
fun NfBody(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    maxLines: Int = Int.MAX_VALUE
) {
    Text(
        text = text,
        modifier = modifier,
        style = NfType.body,
        color = color,
        maxLines = maxLines,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
fun NfBodyLong(text: String, modifier: Modifier = Modifier, color: Color = Color.Unspecified) {
    Text(text = text, modifier = modifier, style = NfType.bodyLong, color = color)
}

@Composable
fun NfLabel(text: String, modifier: Modifier = Modifier, color: Color = Color.Unspecified) {
    Text(text = text, modifier = modifier, style = NfType.label, color = color)
}

@Composable
fun NfSecondary(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    maxLines: Int = Int.MAX_VALUE
) {
    Text(
        text = text,
        modifier = modifier,
        style = NfType.secondary,
        color = color,
        maxLines = maxLines,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
fun NfMeta(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    maxLines: Int = 1
) {
    Text(
        text = text,
        modifier = modifier,
        style = NfType.meta,
        color = color,
        maxLines = maxLines,
        overflow = TextOverflow.Ellipsis
    )
}

/** 哈希/路径：等宽、单行、不换行拆断。 */
@Composable
fun NfMono(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    maxLines: Int = 1
) {
    Text(
        text = text,
        modifier = modifier,
        style = NfType.mono,
        color = color,
        maxLines = maxLines,
        overflow = TextOverflow.Ellipsis
    )
}

/** 关键数字：等宽数字，避免计数跳动。 */
@Composable
fun NfNumeric(text: String, modifier: Modifier = Modifier, color: Color = Color.Unspecified) {
    Text(text = text, modifier = modifier, style = NfType.numeric, color = color)
}
