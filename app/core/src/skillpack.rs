//! Skill/MCP 包脚手架导出（EXP-02）。
//!
//! 产物是一个可交付的 zip scaffold：SKILL.md（AI 技能入口）+ mcp.json（MCP server 描述模板）
//! + README.md（来源与填充指引）+ 可选 result.md / result.meta.json。
//! 确定性：zip 时间戳/权限固定；mcp.json 走 canonical JSON；不含运行时间/绝对路径。

use crate::error::CoreError;
use crate::zipsec;
use serde_json::{json, Value};

fn esc_md(s: &str) -> String {
    s.replace('\r', "")
}

/// 生成 skill/MCP 脚手架 zip 字节。
pub fn build_skill_pack(
    project_id: &str,
    title: &str,
    markdown: Option<&str>,
    meta: Option<&Value>,
    plan_digest: &str,
    spec_digest: &str,
    markdown_digest: &str,
) -> Result<Vec<u8>, CoreError> {
    let id = if project_id.is_empty() { "nf-skill" } else { project_id };
    let title = if title.is_empty() { id } else { title };
    let skill_md = format!(
        "---\nname: {id}\ndescription: {title} —— NF APP 导出的技能脚手架（AI 可读；MCP 描述见 mcp.json）\nlicense: MIT\n---\n\n# {title}\n\n> 本文件由 NF APP 导出（skill/MCP 脚手架）。它把「项目引用 + 产物摘要」钉在一起；按你的 Agent 平台要求补全 frontmatter 后即可使用。\n\n## 来源（digest 回钉）\n\n| 项 | digest |\n|---|---|\n| plan | {plan_digest} |\n| spec | {spec_digest} |\n| markdown | {markdown_digest} |\n\n## 使用\n\n1. 把本包内容（含 result.md，若存在）作为技能资料装载。\n2. 需要工具调用时，按 mcp.json 的 server 段配置 MCP 客户端（命令与参数按你的运行环境替换）。\n3. 产物校验：用 NF APP 的 validate 流程对 result.md 重跑 L0/L1。\n\n## 边界\n\n- 不含密钥/凭据；不含绝对路径；不含遥测。\n- 本脚手架不承诺任何具体 Agent 平台的私有格式；mcp.json 是**模板**，字段需按目标平台补全。\n",
        id = esc_md(id),
        title = esc_md(title),
        plan_digest = plan_digest,
        spec_digest = spec_digest,
        markdown_digest = markdown_digest
    );
    let mcp = json!({
        "schema": "nf-mcp-scaffold/1",
        "name": id,
        "version": "0.1.0",
        "description": format!("{title} —— NF APP 导出的 MCP server 描述模板"),
        "server": {
            "transport": "stdio",
            "command": "nf-app",
            "args": ["mcp-serve"]
        },
        "tools": [],
        "resources": [],
        "provenance": {
            "plan_digest": plan_digest,
            "spec_digest": spec_digest,
            "markdown_digest": markdown_digest
        }
    });
    let mcp_bytes = crate::canonical::canonical_bytes(&mcp)?;
    let readme = format!(
        "# {title} —— skill/MCP 脚手架\n\n本包含：\n\n- SKILL.md：技能入口（AI 可读）\n- mcp.json：MCP server 描述模板（nf-mcp-scaffold/1）\n- result.md / result.meta.json：装配产物（若导出时提供）\n\n## 复现\n\n来源摘要：plan={plan_digest}；spec={spec_digest}；markdown={markdown_digest}。\n\n## 填充指引\n\n1. mcp.json 的 server.command/args 换成你环境的入口；tools/resources 按实际能力补全（不要留空声明）。\n2. SKILL.md 的 description 按目标平台限制改写；正文保留来源回钉。\n3. 交付前用 NF APP 的 validate/export 流程重跑一次，确认摘要未漂。\n",
        title = esc_md(title),
        plan_digest = plan_digest,
        spec_digest = spec_digest,
        markdown_digest = markdown_digest
    );
    let mut entries: Vec<(String, Vec<u8>)> = vec![
        ("README.md".to_string(), readme.into_bytes()),
        ("SKILL.md".to_string(), skill_md.into_bytes()),
        ("mcp.json".to_string(), mcp_bytes),
    ];
    if let Some(md) = markdown {
        entries.push(("result.md".to_string(), md.as_bytes().to_vec()));
    }
    if let Some(m) = meta {
        entries.push((
            "result.meta.json".to_string(),
            crate::canonical::canonical_bytes(m)?,
        ));
    }
    entries.sort_by(|a, b| a.0.cmp(&b.0));
    zipsec::zip_bytes(&entries)
}
