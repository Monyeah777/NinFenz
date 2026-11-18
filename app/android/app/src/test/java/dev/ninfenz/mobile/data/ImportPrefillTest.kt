package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Test

class ImportPrefillTest {
    @Test
    fun mapsHeadingToSlot() {
        val json = """{
  "schema": "nf-import/1",
  "source": {"kind": "file", "name": "clip.md", "mime": "text/markdown", "size": 10, "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  "detected": {"format": "markdown", "confidence": 90, "candidates": [{"format": "markdown", "confidence": 90}]},
  "text": "# 标题\n\n正文。",
  "text_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "structure": {"headings": [{"line": 1, "level": 1, "text": "标题"}], "paragraphs": 1, "code_blocks": [], "tables": []},
  "assets": [],
  "suggested": {"template_id": "demo", "mappings": [{"from_kind": "heading", "from_index": 0, "to_kind": "slot", "to_id": "SLT-01", "confidence": 80, "rationale": "标题"}], "unmapped": []},
  "warnings": []
}"""
        assertEquals("# 标题", ImportPrefill.fromJson(json)["SLT-01"])
    }

    @Test
    fun invalidJsonReturnsEmpty() {
        assertEquals(emptyMap<String, String>(), ImportPrefill.fromJson("{bad"))
    }
}
