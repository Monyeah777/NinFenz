package dev.ninfenz.mobile.model

/** 项目库按状态过滤：null=全部。 */
object ProjectFilter {
    fun apply(entries: List<ProjectEntry>, status: ProjectStatus?): List<ProjectEntry> {
        if (status == null) return entries
        return entries.filter { it.project.status == status }
    }
}
