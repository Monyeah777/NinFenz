package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.ProtocolModel
import dev.ninfenz.mobile.model.ProtocolPack
import dev.ninfenz.mobile.model.SpecModel
import java.io.File
import kotlinx.serialization.json.JsonObject

data class AuthorArtifacts(
    val protocol: ProtocolPack,
    val protocolJson: JsonObject,
    val graph: PipelineGraph,
    val graphJson: JsonObject,
    val spec: MdSpec,
    val specJson: JsonObject
)

/** 从已安装 Pack 读取项目引用的 protocol/pipeline/spec（只读；编辑保存留 W4 后续）。 */
object AuthorArtifactsLoader {
    fun load(pack: PackEntry, specOverride: File? = null): AuthorArtifacts {
        val protocolFile = File(pack.dir, "protocol/nf-protocol-pack.json")
        val graphFile = File(pack.dir, "pipeline/main.nfg.json")
        val specFile = File(pack.dir, "spec/main.nfspec.json")
        require(protocolFile.isFile) { "Pack 缺少 protocol/nf-protocol-pack.json" }
        require(graphFile.isFile) { "Pack 缺少 pipeline/main.nfg.json" }
        require(specFile.isFile) { "Pack 缺少 spec/main.nfspec.json" }

        val protocolJson = J.parseObject(protocolFile.readText(Charsets.UTF_8), ProtocolModel.SCHEMA)
        val graphJson = J.parseObject(graphFile.readText(Charsets.UTF_8), GraphModel.SCHEMA)
        val specSource = specOverride?.takeIf { it.isFile } ?: specFile
        val specJson = J.parseObject(specSource.readText(Charsets.UTF_8), SpecModel.SCHEMA)
        return AuthorArtifacts(
            protocol = ProtocolModel.parse(protocolJson),
            protocolJson = protocolJson,
            graph = GraphModel.parse(graphJson),
            graphJson = graphJson,
            spec = SpecModel.parse(specJson),
            specJson = specJson
        )
    }
}
