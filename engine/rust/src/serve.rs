//! `nf-rs serve` —— NF 只读快线的**常驻 worker**（把「每条命令一次进程启动」换成「一次启动、长期热跑」）。
//!
//! 与 `desktop/src/core/daemon.py` 同一条纪律：
//!   - 只绑 `127.0.0.1` 回环（worker 能跑任意只读判据，绝不能出回环）；
//!   - 一次性令牌：请求必须带令牌才算数（回环不是信任边界，令牌是第二道门槛）；
//!   - 单线程串行：不并发跑仓库命令（确定性优先）；
//!   - 协议版本化、极简：
//!     请求 = 一行 JSON：`{"proto":1,"token":"…","argv":["stats","--root","…","--json"]}`
//!     响应 = 三行明文头 + 原始字节：`<exit>\n<out_len>\n<err_len>\n` + stdout 字节 + stderr 字节
//!   - 状态落 `--state` 文件（pid/port/token/root/proto/started），令牌不进日志。
//!
//! 只读纪律：本 worker 复用 `main::run()` 的分派面（只有只读判据，无任何写面），
//! 通过 `crate::run_capture` 把 stdout 换成内存缓冲——**零分叉面逻辑**，字节一致性天然继承。

use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use serde_json::{json, Value};

mod part1;

pub(crate) use part1::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_is_csprng_sized_and_unique() {
        let first = make_token().unwrap();
        let second = make_token().unwrap();
        assert_eq!(first.len(), 64);
        assert!(first.bytes().all(|b| b.is_ascii_hexdigit()));
        assert_ne!(first, second);
    }

    #[test]
    fn token_compare_is_exact() {
        assert!(constant_time_eq(b"same", b"same"));
        assert!(!constant_time_eq(b"same", b"diff"));
        assert!(!constant_time_eq(b"short", b"longer"));
    }

    #[test]
    fn argv_rejects_non_strings_and_write_faces() {
        let non_string = json!({"argv": ["stats", 7]});
        assert!(parse_argv(&non_string).is_err());
        let root = std::env::temp_dir();
        assert!(validate_argv(
            &["stats".into(), "--root".into(), root.display().to_string()],
            &std::fs::canonicalize(&root).unwrap(),
        )
        .is_ok());
        assert!(validate_argv(
            &["serve".into(), "--state".into(), "x".into()],
            &std::fs::canonicalize(&root).unwrap(),
        )
        .is_err());
        assert!(validate_argv(
            &["stats".into(), "--out".into(), "x".into()],
            &std::fs::canonicalize(&root).unwrap(),
        )
        .is_err());
    }

    #[test]
    fn argv_root_must_match_worker_root() {
        let allowed = std::env::temp_dir();
        let denied = std::env::temp_dir().join("nf-serve-denied");
        std::fs::create_dir_all(&denied).unwrap();
        let err = validate_argv(
            &[
                "stats".into(),
                "--root".into(),
                denied.display().to_string(),
            ],
            &std::fs::canonicalize(&allowed).unwrap(),
        )
        .unwrap_err();
        assert!(err.contains("必须等于"));
    }

    #[test]
    fn request_line_is_bounded_and_batched() {
        let mut reader = std::io::Cursor::new(vec![b'a'; MAX_REQUEST_BYTES + 2]);
        let err = read_request_line(&mut reader).unwrap_err();
        assert_eq!(err.kind(), std::io::ErrorKind::InvalidData);
    }

    #[test]
    fn state_write_is_complete_and_leaves_no_temp() {
        let dir = crate::testutil::fixture("serve-state-atomic");
        let path = dir.join("state.json");
        write_state_atomic(&path, br#"{"ok":true}"#).unwrap();
        assert_eq!(std::fs::read(&path).unwrap(), br#"{"ok":true}"#);
        let leftovers: Vec<_> = std::fs::read_dir(&dir)
            .unwrap()
            .filter_map(Result::ok)
            .filter(|e| e.file_name().to_string_lossy().ends_with(".tmp"))
            .collect();
        assert!(leftovers.is_empty());
    }
}
