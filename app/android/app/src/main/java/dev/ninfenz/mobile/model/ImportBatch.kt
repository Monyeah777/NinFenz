package dev.ninfenz.mobile.model

/** 多文件导入队列的纯状态：UI 只负责渲染与调用，不把成功判断藏在 Compose 状态里。 */
enum class ImportBatchStatus { PENDING, RUNNING, SUCCESS, FAILED, CANCELLED }

data class ImportBatchItem(
    val uri: String,
    val name: String,
    val status: ImportBatchStatus = ImportBatchStatus.PENDING,
    val error: String? = null
)

data class ImportBatchState(
    val items: List<ImportBatchItem>,
    val current: Int = -1,
    val cancelled: Boolean = false
) {
    val total: Int get() = items.size
    val success: Int get() = items.count { it.status == ImportBatchStatus.SUCCESS }
    val failed: Int get() = items.count { it.status == ImportBatchStatus.FAILED }
    val processed: Int get() = items.count {
        it.status == ImportBatchStatus.SUCCESS || it.status == ImportBatchStatus.FAILED || it.status == ImportBatchStatus.CANCELLED
    }
    val running: Boolean get() = items.any { it.status == ImportBatchStatus.RUNNING }

    fun markRunning(index: Int): ImportBatchState {
        if (index !in items.indices) return this
        return copy(
            current = index,
            items = items.mapIndexed { i, item ->
                if (i == index) item.copy(status = ImportBatchStatus.RUNNING, error = null) else item
            }
        )
    }

    fun markSuccess(index: Int): ImportBatchState {
        if (index !in items.indices) return this
        return copy(items = items.mapIndexed { i, item ->
            if (i == index) item.copy(status = ImportBatchStatus.SUCCESS, error = null) else item
        })
    }

    fun markFailure(index: Int, error: String): ImportBatchState {
        if (index !in items.indices) return this
        return copy(items = items.mapIndexed { i, item ->
            if (i == index) item.copy(status = ImportBatchStatus.FAILED, error = error) else item
        })
    }

    fun cancel(): ImportBatchState = copy(
        cancelled = true,
        items = items.map { item ->
            if (item.status == ImportBatchStatus.PENDING) item.copy(status = ImportBatchStatus.CANCELLED) else item
        }
    )

    fun failedIndices(): List<Int> = items.indices.filter { items[it].status == ImportBatchStatus.FAILED }

    companion object {
        fun start(uris: List<Pair<String, String>>): ImportBatchState =
            ImportBatchState(uris.map { (uri, name) -> ImportBatchItem(uri = uri, name = name) })
    }
}
