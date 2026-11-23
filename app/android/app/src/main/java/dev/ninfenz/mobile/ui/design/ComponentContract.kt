package dev.ninfenz.mobile.ui.design

/** 7 态模板：状态必须有标题/说明/动作/语义，不能只换颜色。 */
enum class UiState { EMPTY, LOADING, ERROR, OFFLINE, PARTIAL, SIGNED, EXPIRED }

data class StateContract(
    val state: UiState,
    val title: String,
    val action: String?,
    val tone: String,
    val needsEvidence: Boolean
)

object StateContracts {
    val all = listOf(
        StateContract(UiState.EMPTY, "尚无内容", "创建/导入", "neutral", false),
        StateContract(UiState.LOADING, "正在处理", null, "info", false),
        StateContract(UiState.ERROR, "失败原因", "重试/修复", "error", true),
        StateContract(UiState.OFFLINE, "离线", "重试", "warning", false),
        StateContract(UiState.PARTIAL, "部分完成", "查看失败项", "warning", true),
        StateContract(UiState.SIGNED, "已签收", "查看证据", "success", true),
        StateContract(UiState.EXPIRED, "已过期", "重新校验", "neutral", true)
    )

    fun forState(state: UiState): StateContract = all.first { it.state == state }
}

/** 组件结构令牌：高度/触控/内边距/圆角/字号，全部落在栅格。 */
data class ComponentSpec(
    val name: String,
    val height: Int,
    val minTouch: Int,
    val padding: Int,
    val radius: Int,
    val type: String
)

object ComponentContracts {
    val all = listOf(
        ComponentSpec("topAppBar", Sizes.topAppBar, Sizes.topAppBar, Space.gutter, 0, "title.screen"),
        ComponentSpec("primaryButton", Sizes.button, Sizes.touchTarget, Space.gutter, Radius.full, "label"),
        ComponentSpec("secondaryButton", Sizes.button, Sizes.touchTarget, Space.gutter, Radius.full, "label"),
        ComponentSpec("textField", Sizes.textField, Sizes.textField, Space.gutter, Radius.sm, "body"),
        ComponentSpec("listOneLine", Sizes.listOneLine, Sizes.listOneLine, Space.gutter, 0, "itemTitle"),
        ComponentSpec("listTwoLine", Sizes.listTwoLine, Sizes.listTwoLine, Space.gutter, 0, "itemTitle"),
        ComponentSpec("chip", 32, Sizes.touchTarget, Space.itemGap, Radius.full, "label"),
        ComponentSpec("navigationBar", Sizes.navigationBar, Sizes.touchTarget, Space.gutter, 0, "meta")
    )

    fun onGrid(): Boolean = all.all {
        it.height % 4 == 0 && it.minTouch % 4 == 0 && it.padding % 4 == 0 && (it.radius == Radius.full || it.radius % 4 == 0)
    }

    fun touchSafe(): Boolean = all.all { it.minTouch >= Sizes.touchTarget }
}
