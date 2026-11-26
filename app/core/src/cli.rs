//! CLI 入口（CLI.md §1/§2）：单行 JSON 信封；诊断走 stderr；不写盘（out_dir 例外）。

use crate::canonical::canonical_bytes;
use crate::error::{CoreError, Envelope};
use crate::ops;
use serde_json::{json, Value};

pub fn run(op: &str, input: &[u8]) -> Envelope {
    let result = std::panic::catch_unwind(|| match ops::parse_request(input) {
        Ok(req) => ops::dispatch(op, &req),
        Err(e) => Envelope::failure(&e, None),
    });
    match result {
        Ok(env) => env,
        Err(panic) => {
            let msg = panic_message(&panic);
            eprintln!("nf-app-core: panic 兜底: {msg}");
            Envelope::failure(
                &CoreError::new("NF-E-003")
                    .with_message(format!("内部错误（panic 已兜底）：{msg}"))
                    .with_exit(2),
                None,
            )
        }
    }
}

fn panic_message(panic: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = panic.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = panic.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".to_string()
    }
}

pub fn envelope_bytes(env: &Envelope) -> Vec<u8> {
    match canonical_bytes(&env.to_value()) {
        Ok(mut b) => {
            b.push(b'\n');
            b
        }
        Err(_) => b"{\"ok\":false,\"exit\":2,\"result\":null,\"error\":{\"code\":\"NF-E-003\",\"message\":\"envelope serialization failed\",\"fix\":\"check input\"}}\n".to_vec(),
    }
}

pub fn abi_version() -> Value {
    json!({"abi": crate::ABI_VERSION, "version": crate::CORE_VERSION})
}

pub fn help_text() -> &'static str {
    "nf-app-core <op> [--in <req.json|->] [--json]\n\
     nf-app-core --abi-version\n\
     nf-app-core golden-gen --out <dir>\n\
     ops: canonical pack-hash pack-verify import-sniff import map-suggest\n\
          protocol-validate protocol-render graph-validate graph-compile\n\
          spec-validate assemble validate export pack-diff pack-merge\n\
          pack-update pack-release-create pack-release-verify pack-release-freeze\n\
          overlay-apply ccos-build-task ccos-import-result project-validate\n\
          layout-import sdir-import sdir-validate sdir-diff sdir-merge sdir-repair\n\
          contract-compile contract-solve contract-explain\n          build-journal build-why
          build-plan build-run build-incremental block-plan block-incremental\n\
          graph-typecheck schema-induce sdir-fuse template-induce template-migrate compose-run\n\
          fragment-validate compose-validate compose-render\n\
          source-add source-verify source-chain-build source-chain-verify\n\
          evidence-create evidence-verify evidence-pack evidence-verify-package evidence-freeze evidence-keygen\n\
          plan-solve plan-explain reuse-index reuse-impact\n\
          export-profile export-accessible\n\
     契约：app/docs/CLI.md；请求/响应见 §3；退出码 0/1/2/3/4。\n"
}
