package dev.ninfenz.mobile.model

import java.io.File

/** 项目库条目：项目模型 + 磁盘文件。model 层自有类型，避免 model -> data 反向依赖。 */
data class ProjectEntry(val project: Project, val file: File)
