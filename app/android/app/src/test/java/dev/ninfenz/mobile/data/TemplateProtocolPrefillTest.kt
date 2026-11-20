package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TemplateProtocolPrefillTest {
    @Test
    fun parsesSlotNameAndExample() {
        val map = TemplateProtocolPrefill.parse(
            "# 模板\n\n- SLT-01 主题句（text · required）：灯灭之前\n- SLT-02 语气：冷静\n- SLT-03 空：   "
        )
        assertEquals("灯灭之前", map["主题句"])
        assertEquals("冷静", map["语气"])
        assertTrue(!map.containsKey("空"))
    }
}
