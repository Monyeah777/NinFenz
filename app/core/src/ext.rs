//! 计划 §17 扩展口：最小可用接口 + 默认实现 + fail-closed 默认行为。
//! 这些接口不改变 CLI 契约；第三方/平台实现可在此挂载。

use crate::canonical::digest_value;
use crate::error::CoreError;
use crate::markdown::MarkdownStructure;
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

/// ① 格式适配器。内置适配器实现它（text/markdown/json/yaml/zip/nftpl/nfpack）。
pub trait Adapter {
    fn format(&self) -> &'static str;
    /// 返回置信度（0–100）；None = 不适配。
    fn sniff(&self, name: &str, mime: Option<&str>, bytes: Option<&[u8]>) -> Option<u32>;
    /// 抽取为草稿（原文 + 结构 + 资产）。
    fn extract(&self, bytes: &[u8]) -> Result<AdapterDraft, CoreError>;
}

#[derive(Clone, Debug, Default)]
pub struct AdapterDraft {
    pub text: Option<String>,
    pub structure: MarkdownStructure,
    pub assets: Vec<Value>,
}

pub struct BuiltinAdapter {
    format: &'static str,
}

impl BuiltinAdapter {
    pub fn new(format: &'static str) -> Self {
        BuiltinAdapter { format }
    }
}

impl Adapter for BuiltinAdapter {
    fn format(&self) -> &'static str {
        self.format
    }

    fn sniff(&self, name: &str, mime: Option<&str>, bytes: Option<&[u8]>) -> Option<u32> {
        let sniffed = crate::ops::import_ops::sniff(name, mime, bytes).ok()??;
        sniffed
            .candidates
            .iter()
            .find(|(f, _)| f == self.format)
            .map(|(_, c)| *c)
    }

    fn extract(&self, bytes: &[u8]) -> Result<AdapterDraft, CoreError> {
        let out = crate::ops::import_ops::extract_format(self.format, bytes)?;
        Ok(AdapterDraft {
            text: out.text,
            structure: out.structure,
            assets: out.assets,
        })
    }
}

/// 内置适配器表（§5.2 首版）。
pub fn builtin_adapters() -> Vec<Box<dyn Adapter>> {
    ["text", "markdown", "json", "yaml", "zip", "nftpl", "nfpack"]
        .into_iter()
        .map(|f| Box::new(BuiltinAdapter::new(f)) as Box<dyn Adapter>)
        .collect()
}

/// ③ PackPublisher：导出包发布。默认实现 = 本地目录。
pub trait PackPublisher {
    fn publish(&self, tree: &Path) -> Result<Value, CoreError>;
}

pub struct LocalDirPublisher {
    pub target: PathBuf,
}

impl LocalDirPublisher {
    pub fn new(target: impl Into<PathBuf>) -> Self {
        LocalDirPublisher {
            target: target.into(),
        }
    }
}

impl PackPublisher for LocalDirPublisher {
    fn publish(&self, tree: &Path) -> Result<Value, CoreError> {
        crate::fsutil::ensure_dir(&self.target)?;
        let rels = crate::fsutil::copy_tree(tree, &self.target)?;
        let computed = crate::fsutil::pack_items(&self.target, None)?;
        Ok(json!({
            "target": "local-dir",
            "items": computed.items.len(),
            "tree": computed.tree,
            "files": rels,
        }))
    }
}

/// ② CCOS 执行面抽象：只声明，不做网络。
pub trait Provider {
    fn name(&self) -> &'static str;
    fn supports(&self, task: &Value) -> bool;
    fn execute(&self, task: &Value) -> Result<Value, CoreError>;
}

/// 默认 Provider：未配置 → 环境缺失 exit 4（不得降级为本地执行）。
pub struct UnconfiguredProvider;

impl Provider for UnconfiguredProvider {
    fn name(&self) -> &'static str {
        "unconfigured"
    }

    fn supports(&self, task: &Value) -> bool {
        task.get("schema").and_then(|v| v.as_str()) == Some("ccos-task/1")
    }

    fn execute(&self, _task: &Value) -> Result<Value, CoreError> {
        Err(CoreError::new("NF-E-005")
            .with_message("CCOS Provider 未配置（核心不做网络/执行）")
            .with_fix("在 APP 侧注入 Provider 实现")
            .with_exit(4))
    }
}

/// ④ FeatureGate：计划 §2.3 要求空实现、默认全开。
pub trait FeatureGate {
    fn enabled(&self, feature: &str) -> bool;
}

#[derive(Default)]
pub struct AllEnabled;

impl FeatureGate for AllEnabled {
    fn enabled(&self, _feature: &str) -> bool {
        true
    }
}

/// ⑤ TraceRecorder：默认 no-op；记录步骤/耗时字段但不落盘。
#[derive(Clone, Debug, Default)]
pub struct TraceEvent {
    pub step: String,
    pub elapsed_ms: u64,
    pub detail: Option<String>,
}

pub trait TraceRecorder {
    fn record(&mut self, event: TraceEvent);
    fn events(&self) -> &[TraceEvent];
}

#[derive(Default)]
pub struct NoopTraceRecorder;

impl TraceRecorder for NoopTraceRecorder {
    fn record(&mut self, _event: TraceEvent) {}
    fn events(&self) -> &[TraceEvent] {
        &[]
    }
}

/// 仅内存记录（用于测试/诊断；调用方决定是否落盘）。
#[derive(Default)]
pub struct InMemoryTraceRecorder {
    events: Vec<TraceEvent>,
}

impl TraceRecorder for InMemoryTraceRecorder {
    fn record(&mut self, event: TraceEvent) {
        self.events.push(event);
    }
    fn events(&self) -> &[TraceEvent] {
        &self.events
    }
}

/// ⑥ DslParser：规则表达式最小子集；未知 op fail-closed。
pub struct DslParser;

impl DslParser {
    pub const OPS: &'static [&'static str] = crate::ops::protocol::OPS;

    /// 解析并校验表达式结构；未知 op/非法操作数 → NF-PRT-005。
    pub fn parse_rule(expr: &Value) -> Result<Value, CoreError> {
        if !expr.is_object() {
            return Err(CoreError::new("NF-PRT-005")
                .with_message("DSL 表达式必须是 object")
                .with_exit(3));
        }
        let op = expr
            .get("op")
            .and_then(|v| v.as_str())
            .ok_or_else(|| CoreError::new("NF-PRT-005").with_message("DSL 缺 op").with_exit(3))?;
        if !Self::OPS.contains(&op) {
            return Err(CoreError::new("NF-PRT-005")
                .with_message(format!("DSL op {op} 不在白名单（fail-closed）"))
                .with_exit(3));
        }
        if let Some(args) = expr.get("args") {
            let args = args.as_array().ok_or_else(|| {
                CoreError::new("NF-PRT-005").with_message("DSL args 必须是数组").with_exit(3)
            })?;
            for (i, arg) in args.iter().enumerate() {
                if arg.is_object() && arg.get("op").is_some() {
                    Self::parse_rule(arg).map_err(|e| e.with_exit(3))?;
                } else if arg.is_object() && arg.get("field").is_none() {
                    return Err(CoreError::new("NF-PRT-005")
                        .with_message(format!("DSL args[{i}] 既不是表达式也不是字段操作数"))
                        .with_exit(3));
                }
            }
        }
        Ok(expr.clone())
    }
}

/// ⑦ BatchRunner：批量输入 → 逐项结果（错误聚合，不中断）。
pub struct BatchRunner;

pub struct BatchOutcome<T> {
    pub results: Vec<(usize, Result<T, CoreError>)>,
}

impl<T> BatchOutcome<T> {
    pub fn succeeded(&self) -> usize {
        self.results.iter().filter(|(_, r)| r.is_ok()).count()
    }
    pub fn failed(&self) -> usize {
        self.results.iter().filter(|(_, r)| r.is_err()).count()
    }
    pub fn errors(&self) -> Vec<(usize, String)> {
        self.results
            .iter()
            .filter_map(|(i, r)| r.as_ref().err().map(|e| (*i, e.code.clone())))
            .collect()
    }
}

impl BatchRunner {
    pub fn run<T, F>(items: &[Value], mut f: F) -> BatchOutcome<T>
    where
        F: FnMut(usize, &Value) -> Result<T, CoreError>,
    {
        let mut out = Vec::with_capacity(items.len());
        for (i, item) in items.iter().enumerate() {
            out.push((i, f(i, item)));
        }
        BatchOutcome { results: out }
    }
}

/// ⑧ PluginAdapter：第三方适配器挂载点；默认拒绝未注册。
pub trait Plugin {
    fn name(&self) -> &'static str;
    fn call(&self, request: &Value) -> Result<Value, CoreError>;
}

#[derive(Default)]
pub struct PluginRegistry {
    plugins: Vec<Box<dyn Plugin>>,
}

impl PluginRegistry {
    pub fn register(&mut self, plugin: Box<dyn Plugin>) {
        self.plugins.push(plugin);
    }

    pub fn names(&self) -> Vec<&'static str> {
        self.plugins.iter().map(|p| p.name()).collect()
    }

    /// 未注册 → NF-E-002 exit 3（fail-closed）。
    pub fn call(&self, name: &str, request: &Value) -> Result<Value, CoreError> {
        match self.plugins.iter().find(|p| p.name() == name) {
            Some(p) => p.call(request),
            None => Err(CoreError::new("NF-E-002")
                .with_message(format!("插件 {name} 未注册（拒绝挂载）"))
                .with_exit(3)),
        }
    }
}

/// Pack 发布的确定性摘要辅助（测试/发布器共用）。
pub fn publisher_manifest(publisher: &dyn PackPublisher, tree: &Path) -> Result<(Value, String), CoreError> {
    let result = publisher.publish(tree)?;
    let tree_digest = result
        .get("tree")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    Ok((result, tree_digest))
}

#[allow(dead_code)]
fn digest_of(v: &Value) -> Result<String, CoreError> {
    digest_value(v)
}
