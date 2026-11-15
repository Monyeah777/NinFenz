package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.SeedResult
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfGradientHero
import dev.ninfenz.mobile.ui.components.NfListRow
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing

@Composable
fun LibraryHomeScreen(
    packs: List<PackEntry>,
    projects: List<ProjectEntry>,
    errors: List<String>,
    seedState: SeedResult?,
    seeding: Boolean,
    onSeed: () -> Unit,
    onImport: () -> Unit,
    onOpenPack: (PackEntry) -> Unit,
    onOpenProject: (ProjectEntry) -> Unit,
    onSettings: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(
            title = "库",
            actions = {
                IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, contentDescription = "设置") }
            }
        )
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            item {
                NfGradientHero(
                    title = "把内容写进协议",
                    subtitle = "本地处理 · 无网络 · 示例已就绪",
                    modifier = Modifier.padding(horizontal = NfSpacing.page)
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Button(onClick = onImport) { Text("导入内容") }
                        TextButton(onClick = onSeed, enabled = !seeding) {
                            Text(if (seeding) "载入中…" else "载入示例")
                        }
                    }
                    SeedLine(seedState)
                }
            }
            if (packs.isEmpty() && projects.isEmpty()) {
                item {
                    NfEmptyState(
                        icon = Icons.Filled.Home,
                        title = "还没有内容",
                        message = "载入内置示例 Pack，或从文件管理器/分享导入第一份内容。",
                        actionLabel = "载入示例 Pack",
                        onAction = onSeed,
                        secondaryLabel = "导入文件",
                        onSecondary = onImport
                    )
                }
            }
            if (projects.isNotEmpty()) {
                item { NfSectionHeader("最近项目") }
                items(projects.size) { index ->
                    val entry = projects[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenProject(entry) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(entry.project.title, style = MaterialTheme.typography.titleMedium)
                                Text(entry.project.id, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            NfStatusChip(projectStatusLabel(entry.project))
                        }
                    }
                }
            }
            if (packs.isNotEmpty()) {
                item { NfSectionHeader("已安装 Pack") }
                items(packs.size) { index ->
                    val pack = packs[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenPack(pack) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(pack.title, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    pack.id + " · " + pack.version + " · " + pack.itemCount + " 项",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            NfStatusChip("已安装")
                        }
                    }
                }
            }
            if (errors.isNotEmpty()) {
                item {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        shape = MaterialTheme.shapes.medium,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    ) {
                        Column(modifier = Modifier.padding(NfSpacing.m)) {
                            Text("有 " + errors.size + " 个条目无法读取", style = MaterialTheme.typography.titleMedium)
                            errors.take(3).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SeedLine(seed: SeedResult?) {
    when (seed) {
        is SeedResult.Installed -> Text(
            "示例已载入：" + seed.id + " · " + seed.version,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary
        )
        is SeedResult.AlreadyPresent -> Text(
            "示例已存在：" + seed.id + " · " + seed.version,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary
        )
        is SeedResult.Failed -> Text(
            seed.message,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.error
        )
        null -> Unit
    }
}

@Composable
fun CreateScreen(
    projects: List<ProjectEntry>,
    onImport: () -> Unit,
    onOpenProject: (ProjectEntry) -> Unit,
    onGoLibrary: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = "创作")
        if (projects.isEmpty()) {
            NfEmptyState(
                icon = Icons.Filled.Edit,
                title = "还没有项目",
                message = "先从示例 Pack 或导入内容开始；项目创建向导会在下一波接入。",
                actionLabel = "导入内容",
                onAction = onImport,
                secondaryLabel = "查看库",
                onSecondary = onGoLibrary
            )
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                items(projects.size) { index ->
                    val entry = projects[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenProject(entry) }
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(entry.project.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                                NfStatusChip(projectStatusLabel(entry.project))
                            }
                            Text(
                                "Pack " + entry.project.refs.basePackId + " · " + entry.project.refs.basePackVersion,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun DeliverScreen(
    projects: List<ProjectEntry>,
    onOpenProject: (ProjectEntry) -> Unit,
    onOpenAssembly: () -> Unit,
    onPackUpdate: () -> Unit,
    onCcos: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = "交付")
        if (projects.isEmpty()) {
            NfEmptyState(
                icon = Icons.AutoMirrored.Filled.List,
                title = "还没有可交付的项目",
                message = "先创建或打开一个项目，再装配、校验、导出与分享。",
                actionLabel = "去装配",
                onAction = onOpenAssembly,
                secondaryLabel = "Pack 更新",
                onSecondary = onPackUpdate
            )
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                item { NfSectionHeader("项目") }
                items(projects.size) { index ->
                    val entry = projects[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenProject(entry) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(entry.project.title, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "装配 / 校验 / 导出",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Button(onClick = onOpenAssembly) { Text("去装配") }
                        }
                    }
                }
                item { NfSectionHeader("更多") }
                item {
                    NfListRow(
                        title = "Pack 更新",
                        subtitle = "diff / 冲突 / 回滚",
                        leading = Icons.Filled.Refresh,
                        onClick = onPackUpdate
                    )
                }
                item {
                    NfListRow(
                        title = "CCOS 交接",
                        subtitle = "task / result / 人审",
                        leading = Icons.Filled.Info,
                        onClick = onCcos
                    )
                }
            }
        }
    }
}

@Composable
fun MeScreen(
    themeMode: ThemeMode,
    onThemeMode: (ThemeMode) -> Unit,
    storageText: String,
    nativeReady: Boolean,
    abi: String?,
    onSettings: () -> Unit,
    onAbout: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = "我的")
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item { NfSectionHeader("外观") }
            item {
                Row(
                    modifier = Modifier.padding(horizontal = NfSpacing.page),
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    ThemeMode.entries.forEach { mode ->
                        FilterChip(
                            selected = mode == themeMode,
                            onClick = { onThemeMode(mode) },
                            label = { Text(themeModeLabel(mode)) }
                        )
                    }
                }
            }
            item { NfSectionHeader("语言") }
            item {
                NfListRow(
                    title = "中文（默认）",
                    subtitle = "English 在 v0.1 接入",
                    leading = Icons.Filled.Person,
                    trailing = "›",
                    onClick = onSettings
                )
            }
            item { NfSectionHeader("存储与诊断") }
            item {
                NfListRow(
                    title = "存储与数据",
                    subtitle = storageText,
                    leading = Icons.Filled.Home,
                    trailing = "›",
                    onClick = onSettings
                )
            }
            item {
                NfListRow(
                    title = "诊断",
                    subtitle = if (nativeReady) "核心正常 · " + (abi ?: "") else "核心不可用（NF-E-005）",
                    leading = Icons.Filled.Refresh,
                    trailing = "›",
                    onClick = onSettings
                )
            }
            item { NfSectionHeader("关于") }
            item {
                NfListRow(
                    title = "关于 NF / 许可 / 隐私",
                    subtitle = "本地处理 · 无网络权限 · 无遥测",
                    leading = Icons.Filled.Info,
                    trailing = "›",
                    onClick = onAbout
                )
            }
        }
    }
}

@Composable
fun ProjectDetailScreen(
    project: Project,
    onBack: () -> Unit,
    onProtocol: () -> Unit,
    onGraph: () -> Unit,
    onAssembly: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = project.title, onBack = onBack)
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("状态", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                            NfStatusChip(projectStatusLabel(project))
                        }
                        Text("项目 ID：" + project.id, style = MaterialTheme.typography.bodySmall)
                        Text(
                            "Pack：" + project.refs.basePackId + " · " + project.refs.basePackVersion,
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            "协议：" + project.refs.protocolId.ifBlank { "未绑定" },
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            "历史：" + project.historyCount + " 条",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
            item {
                NfSectionHeader("继续")
            }
            item { NfListRow("协议表单", "参数 / 条款 / 校验", Icons.Filled.Edit, "›", onProtocol) }
            item { NfListRow("管线编辑", "阶段 / 权重 / 边", Icons.AutoMirrored.Filled.List, "›", onGraph) }
            item { NfListRow("装配与交付", "预览 / 校验 / 导出", Icons.Filled.Info, "›", onAssembly) }
        }
    }
}

@Composable
fun PackDetailScreen(pack: PackEntry, onBack: () -> Unit, onUpdate: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = pack.title, onBack = onBack)
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Text(pack.id + " · " + pack.version, style = MaterialTheme.typography.titleMedium)
                        Text(pack.description, style = MaterialTheme.typography.bodyMedium)
                        Text("条目：" + pack.itemCount, style = MaterialTheme.typography.bodySmall)
                        Text("tree：" + pack.tree.take(16) + "…", style = MaterialTheme.typography.bodySmall)
                        Text("目录：" + pack.dir.absolutePath, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            item { Button(onClick = onUpdate, modifier = Modifier.fillMaxWidth()) { Text("Pack 更新 / 校验") } }
        }
    }
}

fun projectStatusLabel(project: Project): String = when (project.status) {
    dev.ninfenz.mobile.model.ProjectStatus.DRAFT -> "草稿"
    dev.ninfenz.mobile.model.ProjectStatus.AUTHORING -> "创作中"
    dev.ninfenz.mobile.model.ProjectStatus.ASSEMBLED -> "已装配"
    dev.ninfenz.mobile.model.ProjectStatus.VALIDATED -> "已校验"
    dev.ninfenz.mobile.model.ProjectStatus.EXPORTED -> "已导出"
    dev.ninfenz.mobile.model.ProjectStatus.REVIEWED -> "已人审"
}

fun themeModeLabel(mode: ThemeMode): String = when (mode) {
    ThemeMode.SYSTEM -> "跟随系统"
    ThemeMode.LIGHT -> "浅色"
    ThemeMode.DARK -> "深色"
}
