package dev.ninfenz.mobile.data

import android.content.Context
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import dev.ninfenz.mobile.R

/** 最近项目动态快捷方式（最多 3 个）；失败静默，不影响主流程。 */
object RecentProjectShortcuts {
    const val ACTION_OPEN_PROJECT = "dev.ninfenz.mobile.OPEN_PROJECT"
    const val EXTRA_PROJECT_ID = "dev.ninfenz.mobile.EXTRA_PROJECT_ID"

    fun reportUsed(context: Context, projectId: String) {
        runCatching {
            context.getSystemService(ShortcutManager::class.java)?.reportShortcutUsed("project:" + projectId)
        }
    }

    fun publish(context: Context, projects: List<ProjectEntry>, targetClass: Class<*>) {
        runCatching {
        val manager = context.getSystemService(ShortcutManager::class.java) ?: return
        val shortcuts = projects.take(3).map { entry ->
            val title = entry.project.title.ifBlank { entry.project.id }
            ShortcutInfo.Builder(context, "project:" + entry.project.id)
                .setShortLabel(title.take(12))
                .setLongLabel(title.take(40))
                .setIcon(Icon.createWithResource(context, R.drawable.ic_launcher_foreground))
                .setIntent(
                    Intent(context, targetClass)
                        .setAction(ACTION_OPEN_PROJECT)
                        .putExtra(EXTRA_PROJECT_ID, entry.project.id)
                )
                .build()
        }
        manager.dynamicShortcuts = shortcuts
        }
    }
}
