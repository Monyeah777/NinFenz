package dev.ninfenz.mobile.ui

import dev.ninfenz.mobile.data.BackupService
import dev.ninfenz.mobile.data.CreateProjectResult
import dev.ninfenz.mobile.data.DraftProjectBinder
import dev.ninfenz.mobile.data.PackDraftStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackInstaller
import dev.ninfenz.mobile.data.ProjectArchiver
import dev.ninfenz.mobile.data.ProjectDuplicator
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.ProjectPackage
import dev.ninfenz.mobile.data.ProjectPaths
import dev.ninfenz.mobile.data.ProjectRenamer
import dev.ninfenz.mobile.data.ProjectReviewStore
import dev.ninfenz.mobile.data.ReviewResult
import dev.ninfenz.mobile.data.TemplateCandidateStore
import dev.ninfenz.mobile.data.TemplatePackageBuilder
import dev.ninfenz.mobile.data.TemplateProjectCreator
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.TopDestination
import dev.ninfenz.mobile.util.orNullLogged
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 项目级动作：从 NfMobileApp 详情路由的 lambda 中抽出，保持原有行为与错误提示。 */
internal fun NfShellHost.shareProject(entry: ProjectEntry) {
    val text = runCatching { entry.file.readText(Charsets.UTF_8) }.orNullLogged("NfMobileApp")
    if (text != null) {
        val shared = ShareExporter.writeSharedFile(context, "nf-project-" + entry.project.id, "json", text)
        val intent = ShareExporter.shareFileIntent(context, shared, "application/json", entry.project.title)
        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.project_detail_share))
    }
}

internal fun NfShellHost.deleteProject(entry: ProjectEntry) {
    scope.launch {
        val snapshot = withContext(Dispatchers.IO) {
            runCatching { BackupService.create(context.filesDir) }.orNullLogged("NfMobileApp")
        }
        if (snapshot == null) {
            toast(context.getString(dev.ninfenz.mobile.R.string.backup_snapshot_blocked))
            return@launch
        }
        withContext(Dispatchers.IO) { ProjectArchiver.deleteProject(entry.file, context.filesDir) }
        refresh()
        select(TopDestination.LIBRARY)
    }
}

internal fun NfShellHost.shareProjectFull(entry: ProjectEntry) {
    toast(context.getString(dev.ninfenz.mobile.R.string.project_detail_share_full), android.widget.Toast.LENGTH_SHORT)
    scope.launch {
        val zip = withContext(Dispatchers.IO) {
            ProjectPackage.create(
                entry.file,
                File(File(context.filesDir, "projects"), entry.project.id),
                File(context.cacheDir, "shared")
            )
        }
        val intent = ShareExporter.shareFileIntent(context, zip, "application/zip", entry.project.title)
        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.project_detail_share_full))
    }
}

internal fun NfShellHost.saveAsTemplate(entry: ProjectEntry) {
    toast(context.getString(dev.ninfenz.mobile.R.string.project_save_template), android.widget.Toast.LENGTH_SHORT)
    scope.launch {
        val pack = packs.packs.firstOrNull {
            it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
        }
        val specFile = pack?.let { ProjectPaths.packSpec(it.dir) }
        val override = ProjectPaths.specOverride(context.filesDir, entry.project.id)
        val source = if (override.isFile) override else specFile
        val raw = source?.takeIf { it.isFile }?.readText(Charsets.UTF_8)
        if (raw == null) {
            toast(context.getString(dev.ninfenz.mobile.R.string.project_save_template))
            return@launch
        }
        val spec = runCatching { Json.parseToJsonElement(raw).jsonObject }.orNullLogged("NfMobileApp")
        if (spec == null) {
            toast(context.getString(dev.ninfenz.mobile.R.string.project_save_template))
            return@launch
        }
        val check = safeCall("spec-validate", buildJsonObject { put("spec", spec) })
        if (check.ok) {
            val saved = TemplateCandidateStore(context.filesDir).save(spec)
            toast(context.getString(dev.ninfenz.mobile.R.string.project_save_template) + ": " + saved.name, android.widget.Toast.LENGTH_SHORT)
        } else {
            toast(check.error?.message ?: context.getString(dev.ninfenz.mobile.R.string.project_save_template))
        }
    }
}

internal fun NfShellHost.exportTemplatePackage(entry: ProjectEntry) {
    toast(context.getString(dev.ninfenz.mobile.R.string.project_export_template), android.widget.Toast.LENGTH_SHORT)
    scope.launch {
        val pack = packs.packs.firstOrNull {
            it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
        }
        val override = ProjectPaths.specOverride(context.filesDir, entry.project.id)
        val specFile = pack?.let { ProjectPaths.packSpec(it.dir) }
        val source = if (override.isFile) override else specFile
        val spec = source?.takeIf { it.isFile }?.let { file ->
            runCatching { Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject }.orNullLogged("NfMobileApp")
        }
        if (pack == null || spec == null) {
            toast(context.getString(dev.ninfenz.mobile.R.string.project_export_template))
            return@launch
        }
        val templateMd = ProjectPaths.templateMd(context.filesDir, entry.project.id)
            .takeIf { it.isFile }?.readText(Charsets.UTF_8)
        val prepared = TemplatePackageBuilder.prepare(context.cacheDir, pack, spec, entry.project.title, templateMd)
        try {
            val hash = safeCall("pack-hash", buildJsonObject { put("root", prepared.dir.absolutePath) })
            val hashes = hash.resultObject()?.get("hashes") as? kotlinx.serialization.json.JsonObject
            val tree = hashes?.get("tree")?.jsonPrimitive?.content
            val count = hashes?.get("count")?.jsonPrimitive?.content?.toIntOrNull()
            if (!hash.ok || tree == null || count == null) {
                toast(hash.error?.message ?: context.getString(dev.ninfenz.mobile.R.string.project_export_template))
            } else {
                val zip = TemplatePackageBuilder.finalize(prepared, tree, count, ProjectPaths.templateExportCache(context.cacheDir))
                val intent = ShareExporter.shareFileIntent(context, zip, "application/zip", entry.project.title)
                ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.project_export_template))
            }
        } finally {
            prepared.dir.deleteRecursively()
        }
    }
}

internal fun NfShellHost.reviewProject(entry: ProjectEntry, approve: Boolean, reviewer: String, note: String) {
    scope.launch {
        when (val result = ProjectReviewStore(context.filesDir).review(entry.project, approve, reviewer, note)) {
            is ReviewResult.Reviewed -> {
                refresh()
                toast(context.getString(dev.ninfenz.mobile.R.string.project_review_saved), android.widget.Toast.LENGTH_SHORT)
            }
            is ReviewResult.Failure ->
                toast(result.message)
        }
    }
}

internal fun NfShellHost.renameProject(entry: ProjectEntry, title: String) {
    scope.launch {
        withContext(Dispatchers.IO) { ProjectRenamer.rename(entry.file, title) }
        refresh()
    }
}

internal fun NfShellHost.archiveProject(entry: ProjectEntry) {
    scope.launch {
        withContext(Dispatchers.IO) { ProjectArchiver.archive(entry.file, context.filesDir) }
        refresh()
        select(TopDestination.LIBRARY)
    }
}

internal fun NfShellHost.duplicateProject(entry: ProjectEntry) {
    scope.launch {
        val copy = withContext(Dispatchers.IO) {
            ProjectDuplicator.duplicate(entry.file, context.filesDir)
        }
        refresh()
        open(Detail.Project(copy.name.removeSuffix(".nfproject.json")))
    }
}

internal fun NfShellHost.changeProjectPack(entry: ProjectEntry, pack: PackEntry) {
    scope.launch {
        val result = withContext(Dispatchers.IO) {
            projectCreator.create(pack, entry.project.title + " · " + pack.id)
        }
        when (result) {
            is CreateProjectResult.Success -> {
                withContext(Dispatchers.IO) {
                    val oldDir = ProjectPaths.projectDir(context.filesDir, entry.project.id)
                    val newDir = ProjectPaths.projectDir(context.filesDir, result.project.id)
                    oldDir.listFiles()?.filter { it.name != ".nfproject.json" }?.forEach { child ->
                        child.copyRecursively(newDir.resolve(child.name), overwrite = false)
                    }
                    val oldDraft = ProjectPaths.deliveryDraft(context.filesDir, entry.project.id)
                    if (oldDraft.isFile) {
                        oldDraft.copyTo(
                            ProjectPaths.deliveryDraft(context.filesDir, result.project.id),
                            overwrite = true
                        )
                    }
                }
                refresh()
                open(Detail.Project(result.project.id))
            }
            is CreateProjectResult.Failure -> {
                toast(result.code + " · " + result.message)
            }
        }
    }
}

internal fun NfShellHost.restoreArchive(file: File) {
    scope.launch {
        val restored = withContext(Dispatchers.IO) { ProjectArchiver.restore(file, context.filesDir) }
        refresh()
        open(Detail.Project(restored.name.removeSuffix(".nfproject.json")))
    }
}

internal fun NfShellHost.createProjectFromDraft(pack: PackEntry, title: String, draft: File, openAuthor: Boolean) {
    scope.launch {
        when (val result = projectCreator.create(pack, title)) {
            is CreateProjectResult.Success -> {
                runCatching {
                    withContext(Dispatchers.IO) {
                        DraftProjectBinder.bind(context.filesDir, result.project.id, draft)
                    }
                }
                refresh()
                open(if (openAuthor) Detail.Author(result.project.id) else Detail.Project(result.project.id))
            }
            is CreateProjectResult.Failure ->
                toast(result.message)
        }
    }
}

internal fun NfShellHost.createProjectFromTemplate(pack: PackEntry, title: String, spec: String, templateText: String) {
    scope.launch {
        when (val result = projectCreator.create(pack, title)) {
            is CreateProjectResult.Success -> {
                runCatching {
                    withContext(Dispatchers.IO) {
                        DraftProjectBinder.bindSpec(context.filesDir, result.project.id, spec)
                        if (templateText.isNotBlank()) {
                            DraftProjectBinder.bindText(context.filesDir, result.project.id, templateText)
                        }
                    }
                }
                refresh()
                open(Detail.Author(result.project.id))
            }
            is CreateProjectResult.Failure ->
                toast(result.message)
        }
    }
}

internal fun NfShellHost.useTemplate(file: File, pack: PackEntry, title: String) {
    scope.launch {
        val result = withContext(Dispatchers.IO) {
            TemplateProjectCreator(context.filesDir).create(pack, title, file)
        }
        when (result) {
            is CreateProjectResult.Success -> {
                refresh()
                open(Detail.Project(result.project.id))
            }
            is CreateProjectResult.Failure -> {
                toast(context.getString(dev.ninfenz.mobile.R.string.template_gallery_create_failed, result.message))
            }
        }
    }
}

internal fun NfShellHost.uninstallPack(pack: PackEntry) {
    val inUse = projects.count {
        it.project.refs.basePackId == pack.id && it.project.refs.basePackVersion == pack.version
    }
    if (inUse > 0) {
        toast(context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.packcenter_uninstall_in_use, inUse, inUse))
        return
    }
    scope.launch {
        val snapshot = withContext(Dispatchers.IO) {
            runCatching { BackupService.create(context.filesDir) }.orNullLogged("NfMobileApp")
        }
        if (snapshot == null) {
            toast(context.getString(dev.ninfenz.mobile.R.string.backup_snapshot_blocked))
            return@launch
        }
        val result = runCatching {
            withContext(Dispatchers.IO) { PackInstaller.uninstall(pack.dir, context.filesDir) }
        }
        result.onSuccess {
            refresh()
            toast(context.getString(dev.ninfenz.mobile.R.string.packcenter_uninstall_done, pack.id, pack.version), android.widget.Toast.LENGTH_SHORT)
        }.onFailure {
            toast(context.getString(dev.ninfenz.mobile.R.string.packcenter_uninstall_failed, it.message ?: it.javaClass.simpleName))
        }
    }
}

internal fun NfShellHost.newPackDraft() {
    val source = packs.packs.firstOrNull()
    if (source == null) {
        toast(context.getString(dev.ninfenz.mobile.R.string.new_project_no_pack_title))
        return
    }
    scope.launch {
        val result = runCatching {
            withContext(Dispatchers.IO) {
                PackDraftStore(context.filesDir).createFrom(
                    source,
                    source.id + "-draft",
                    source.version,
                    source.title + " draft"
                )
            }
        }
        result.onSuccess { open(Detail.PackBuilder(it.id)) }
        result.onFailure {
            toast(it.message ?: "draft failed")
        }
    }
}
