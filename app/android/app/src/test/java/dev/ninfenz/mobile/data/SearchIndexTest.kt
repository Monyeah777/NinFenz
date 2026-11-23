package dev.ninfenz.mobile.data

import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchIndexTest {

    private fun write(file: Path, text: String) {
        Files.createDirectories(file.parent)
        file.toFile().writeText(text, Charsets.UTF_8)
    }

    private fun setup(root: Path) {
        val pack = root.resolve("library/packs/demo-pack/1.0.0")
        write(pack.resolve("nf-pack.json"), "{\"id\":\"demo-pack\",\"version\":\"1.0.0\",\"title\":\"示例 Pack\",\"description\":\"d\",\"items\":[{}],\"hashes\":{\"tree\":\"" + "a".repeat(64) + "\"}}")
        write(pack.resolve("protocol/nf-protocol-pack.json"), "{\"clauses\":[{\"id\":\"C-001\",\"title\":\"开篇约束\",\"level\":\"MUST\"},{\"id\":\"C-002\",\"title\":\"节奏要求\",\"level\":\"SHOULD\"}],\"fields\":[{\"id\":\"F-001\",\"label\":\"主角名\"}]}")
        write(pack.resolve("pipeline/main.nfg.json"), "{\"nodes\":[{\"id\":\"N01\",\"kind\":\"stage\",\"title\":\"开篇\"},{\"id\":\"N02\",\"kind\":\"module\",\"title\":\"润色\"}]}")
        write(pack.resolve("spec/main.nfspec.json"), "{\"sections\":[{\"id\":\"SEC-01\",\"title\":\"开篇\"}],\"slots\":[{\"id\":\"SLT-01\",\"name\":\"开篇钩子\",\"kind\":\"text\"}]}")
        write(root.resolve("projects/demo.nfproject.json"), "{\"schema\":\"nf-project/1\",\"id\":\"demo-project\",\"title\":\"演示项目\",\"status\":\"draft\"}")
    }

    @Test
    fun indexesPackContentAndProjects() {
        val root = Files.createTempDirectory("nf-search-test")
        setup(root)
        val index = SearchIndex(root.toFile())
        val all = index.build()
        assertTrue(all.any { it.kind == SearchKind.CLAUSE && it.title == "开篇约束" })
        assertTrue(all.any { it.kind == SearchKind.FIELD && it.title == "主角名" })
        assertTrue(all.any { it.kind == SearchKind.NODE && it.title == "润色" })
        assertTrue(all.any { it.kind == SearchKind.SLOT && it.title == "开篇钩子" })
        assertTrue(all.any { it.kind == SearchKind.PROJECT && it.title == "演示项目" })

        val hits = index.search(all, "开篇")
        assertTrue(hits.isNotEmpty())
        assertTrue(hits.any { it.kind == SearchKind.CLAUSE }) // 标题命中优先于 detail
    }

    @Test
    fun searchesProjectBody() {
        val root = Files.createTempDirectory("nf-search-body")
        setup(root)
        write(root.resolve("projects/demo-project/authoring/import-1.md"), "# 正文\n\n暴雨后的城市亮起灯。")
        val index = SearchIndex(root.toFile())
        val hits = index.search(index.build(), "暴雨")
        assertEquals(1, hits.size)
        assertTrue(hits[0].detail.contains("暴雨后的城市"))
        assertTrue(hits[0].body.contains("暴雨后的城市"))
    }

    @Test
    fun blankQueryReturnsEmpty() {
        val root = Files.createTempDirectory("nf-search-blank")
        setup(root)
        val index = SearchIndex(root.toFile())
        assertTrue(index.search(index.build(), "   ").isEmpty())
    }

    @Test
    fun missingDirectoriesAreTolerated() {
        val root = Files.createTempDirectory("nf-search-missing")
        val all = SearchIndex(root.toFile()).build()
        assertTrue(all.isEmpty())
    }
}
