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

/// 协议版本（与 daemon.py 的 PROTO 平行编号；改动请求形状即 +1）。
const PROTO: u64 = 1;
const BIND_HOST: &str = "127.0.0.1";
/// 请求体上限（1 MiB）：一条只读判据的 argv 远小于此；设上限防「自称超长」的无界读。
const MAX_REQUEST_BYTES: usize = 1 << 20;
/// 单响应上限：防止失控判据把 worker 与客户端内存一起拖垮。
const MAX_RESPONSE_BYTES: usize = 16 << 20;
/// 单条 argv 上限（字符）与合计上限（字符）：参数是命令/选项/标识符，不是正文载荷。
const MAX_ARGV_CHARS: usize = 8192;
const MAX_ARGV_TOTAL: usize = 65536;
/// 只读命令白名单。未知/未来命令默认拒绝，避免新增写面被 worker 静默继承。
const READ_COMMANDS: &[&str] = &[
    "receipts",
    "stats",
    "purity-facts",
    "purity-scan",
    "code-metrics",
    "conformance",
    "density",
    "depth-scan",
    "layers",
    "schema-lint",
    "schema-validate",
    "score",
    "verify-report",
    "pyval",
];
/// 即使命令在白名单内，这些参数也会写盘或改变分派面，worker 一律拒绝。
const WRITE_OPTIONS: &[&str] = &[
    "--out",
    "--write",
    "--write-baseline",
    "--cwd",
    "--root=",
    "--write=",
    "--out=",
];

static REQUESTS: AtomicU64 = AtomicU64::new(0);
static BYTES_IN: AtomicU64 = AtomicU64::new(0);
static BYTES_OUT: AtomicU64 = AtomicU64::new(0);
static ACTIVE: AtomicUsize = AtomicUsize::new(0);
static STATE_TMP_SEQ: AtomicU64 = AtomicU64::new(0);
const MAX_CONNECTIONS: usize = 16;

pub fn run_serve(args: &[String]) -> Result<ExitCode, String> {
    let mut state: Option<PathBuf> = None;
    let mut root: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--state" => {
                i += 1;
                state = Some(PathBuf::from(args.get(i).ok_or("--state 后缺路径")?));
            }
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            other => return Err(format!("serve 未知参数：{}", other)),
        }
        i += 1;
    }
    let state = state.ok_or("serve 缺 --state（修复指引：给状态文件路径）")?;
    let root = root.ok_or("serve 缺 --root（修复指引：给仓库根目录）")?;
    if !root.is_dir() {
        return Err(format!("--root 不是目录：{}", root.display()));
    }
    let canonical_root =
        std::fs::canonicalize(&root).map_err(|e| format!("解析 --root 失败：{}", e))?;

    let listener =
        TcpListener::bind((BIND_HOST, 0)).map_err(|e| format!("绑 {} 失败：{}", BIND_HOST, e))?;
    let addr = listener
        .local_addr()
        .map_err(|e| format!("取本地地址失败：{}", e))?;
    let port = addr.port();
    let token = make_token()?;

    let payload = json!({
        "proto": PROTO,
        "pid": std::process::id(),
        "port": port,
        "token": token,
        "root": root.to_string_lossy(),
        "started": unix_epoch_ms(),
    });
    let text = serde_json::to_string(&payload).map_err(|e| format!("状态序列化失败：{}", e))?;
    if let Some(dir) = state.parent() {
        if !dir.as_os_str().is_empty() {
            std::fs::create_dir_all(dir).map_err(|e| format!("建状态目录失败：{}", e))?;
        }
    }
    write_state_atomic(&state, text.as_bytes())?;

    for conn in listener.incoming() {
        let stream = match conn {
            Ok(s) => s,
            Err(_) => continue,
        };
        // 每连接一线程（keep-alive/idle 不阻塞 accept）；判据执行仍由 RUN_LOCK 串行。
        if ACTIVE.fetch_add(1, Ordering::SeqCst) >= MAX_CONNECTIONS {
            ACTIVE.fetch_sub(1, Ordering::SeqCst);
            let mut stream = stream;
            let _ = respond(&mut stream, 2, b"", "worker 连接数已满".as_bytes());
            continue;
        }
        let token = token.clone();
        let canonical_root = canonical_root.clone();
        std::thread::spawn(move || {
            let _ = handle(stream, &token, &canonical_root);
            ACTIVE.fetch_sub(1, Ordering::SeqCst);
        });
    }
    Ok(ExitCode::SUCCESS)
}

fn handle(mut stream: TcpStream, token: &str, allowed_root: &Path) -> std::io::Result<()> {
    let _ = stream.set_nodelay(true);
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(30)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(30)));
    let mut reader = BufReader::new(stream.try_clone()?);

    // 一条连接可承载多请求（keep-alive）；EOF/空行/协议错误即关闭。
    loop {
        let line = match read_request_line(&mut reader) {
            Ok(l) => l,
            Err(e) if e.kind() == std::io::ErrorKind::InvalidData => {
                respond(&mut stream, 2, b"", e.to_string().as_bytes())?;
                break;
            }
            Err(_) => break,
        };
        if line.trim().is_empty() {
            break;
        }
        REQUESTS.fetch_add(1, Ordering::Relaxed);
        BYTES_IN.fetch_add(line.len() as u64, Ordering::Relaxed);
        let req: Value = match serde_json::from_str(line.trim()) {
            Ok(v) => v,
            Err(e) => {
                respond(
                    &mut stream,
                    2,
                    b"",
                    format!("请求不是合法 JSON：{}", e).as_bytes(),
                )?;
                break;
            }
        };
        let proto = req.get("proto").and_then(|v| v.as_u64()).unwrap_or(0);
        if proto != PROTO {
            respond(&mut stream, 2, b"", "proto 不符".as_bytes())?;
            break;
        }
        let got_token = req.get("token").and_then(|v| v.as_str()).unwrap_or("");
        if !constant_time_eq(got_token.as_bytes(), token.as_bytes()) {
            respond(&mut stream, 2, b"", "token 不符".as_bytes())?;
            break;
        }
        // 只读观测面：请求/字节计数（RSS 由宿主侧取）。
        if req.get("op").and_then(|v| v.as_str()) == Some("stats") {
            let payload = json!({
                "pid": std::process::id(),
                "proto": PROTO,
                "requests": REQUESTS.load(Ordering::Relaxed),
                "bytes_in": BYTES_IN.load(Ordering::Relaxed),
                "bytes_out": BYTES_OUT.load(Ordering::Relaxed),
            })
            .to_string();
            BYTES_OUT.fetch_add(payload.len() as u64, Ordering::Relaxed);
            respond(&mut stream, 0, payload.as_bytes(), b"")?;
            continue;
        }
        let argv = match parse_argv(&req) {
            Ok(argv) => argv,
            Err(msg) => {
                respond(&mut stream, 2, b"", msg.as_bytes())?;
                break;
            }
        };
        if argv.is_empty() {
            respond(&mut stream, 2, b"", "argv 为空".as_bytes())?;
            break;
        }
        if !argv_size_ok(&argv) {
            respond(&mut stream, 2, b"", "argv 超上限".as_bytes())?;
            break;
        }
        if let Err(msg) = validate_argv(&argv, allowed_root) {
            respond(&mut stream, 2, b"", msg.as_bytes())?;
            break;
        }
        let (out, code) = crate::run_capture(&argv);
        if out.len() > MAX_RESPONSE_BYTES {
            respond(&mut stream, 2, b"", "响应超上限".as_bytes())?;
            crate::recycle_capture_buf(out);
            break;
        }
        BYTES_OUT.fetch_add(out.len() as u64, Ordering::Relaxed);
        respond(&mut stream, code, &out, b"")?;
        crate::recycle_capture_buf(out);
    }
    Ok(())
}

fn read_request_line<R: BufRead>(reader: &mut R) -> std::io::Result<String> {
    let mut buf: Vec<u8> = Vec::new();
    // `take` 让无换行输入也有硬上界；BufRead 批量取数，不再一字节一次 syscall。
    let read = reader
        .by_ref()
        .take((MAX_REQUEST_BYTES + 2) as u64)
        .read_until(b'\n', &mut buf)?;
    if read == 0 {
        return Ok(String::new());
    }
    if buf.len() > MAX_REQUEST_BYTES + 1
        || (buf.len() == MAX_REQUEST_BYTES + 2 && !buf.ends_with(b"\n"))
    {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "请求超上限",
        ));
    }
    if buf.last() == Some(&b'\n') {
        buf.pop();
    }
    if buf.last() == Some(&b'\r') {
        buf.pop();
    }
    if buf.len() > MAX_REQUEST_BYTES {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "请求超上限",
        ));
    }
    String::from_utf8(buf)
        .map_err(|_| std::io::Error::new(std::io::ErrorKind::InvalidData, "非 UTF-8 请求"))
}

fn parse_argv(req: &Value) -> Result<Vec<String>, &'static str> {
    let arr = req.get("argv").and_then(Value::as_array).ok_or("缺 argv")?;
    let mut argv = Vec::with_capacity(arr.len());
    for item in arr {
        argv.push(item.as_str().ok_or("argv 必须全为字符串")?.to_string());
    }
    Ok(argv)
}

fn validate_argv(argv: &[String], allowed_root: &Path) -> Result<(), String> {
    let first = argv.first().ok_or("argv 为空")?;
    if !READ_COMMANDS.contains(&first.as_str()) {
        return Err(format!("命令不在只读白名单：{}", first));
    }
    let mut i = 1;
    while i < argv.len() {
        let arg = &argv[i];
        if WRITE_OPTIONS
            .iter()
            .any(|bad| arg == bad || arg.starts_with(bad) && bad.ends_with('='))
        {
            return Err(format!("worker 拒跑写面参数：{}", arg));
        }
        if arg == "--root" {
            let requested = argv.get(i + 1).ok_or("--root 后缺值")?;
            let canonical = std::fs::canonicalize(requested)
                .map_err(|e| format!("解析请求 --root 失败：{}", e))?;
            if canonical != allowed_root {
                return Err("请求 --root 必须等于 worker 启动 root".into());
            }
            i += 1;
        }
        i += 1;
    }
    Ok(())
}

fn argv_size_ok(argv: &[String]) -> bool {
    for a in argv {
        if a.len() > MAX_ARGV_CHARS {
            return false;
        }
    }
    argv.iter().map(|a| a.len()).sum::<usize>() <= MAX_ARGV_TOTAL
}

fn respond(stream: &mut impl Write, code: i32, out: &[u8], err: &[u8]) -> std::io::Result<()> {
    let head = format!("{}\n{}\n{}\n", code, out.len(), err.len());
    stream.write_all(head.as_bytes())?;
    stream.write_all(out)?;
    stream.write_all(err)?;
    stream.flush()
}

fn unix_epoch_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn make_token() -> Result<String, String> {
    let mut bytes = [0u8; 32];
    getrandom::getrandom(&mut bytes).map_err(|e| format!("读取 OS 熵源失败：{}", e))?;
    let mut token = String::with_capacity(bytes.len() * 2);
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for byte in bytes {
        token.push(HEX[(byte >> 4) as usize] as char);
        token.push(HEX[(byte & 0x0f) as usize] as char);
    }
    Ok(token)
}

fn constant_time_eq(left: &[u8], right: &[u8]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    let mut diff = 0u8;
    for (a, b) in left.iter().zip(right) {
        diff |= a ^ b;
    }
    diff == 0
}

fn write_state_atomic(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let parent = path.parent().filter(|p| !p.as_os_str().is_empty());
    if let Some(dir) = parent {
        std::fs::create_dir_all(dir).map_err(|e| format!("建状态目录失败：{}", e))?;
    }
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or("状态文件路径缺文件名")?;
    let seq = STATE_TMP_SEQ.fetch_add(1, Ordering::Relaxed);
    let tmp = path.with_file_name(format!(".{}.{}.{}.tmp", name, std::process::id(), seq));

    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let result = (|| -> Result<(), String> {
        let mut file = options
            .open(&tmp)
            .map_err(|e| format!("创建状态临时文件失败：{}", e))?;
        file.write_all(bytes)
            .map_err(|e| format!("写状态临时文件失败：{}", e))?;
        file.sync_all()
            .map_err(|e| format!("同步状态临时文件失败：{}", e))?;
        drop(file);
        std::fs::rename(&tmp, path).map_err(|e| format!("替换状态文件失败：{}", e))?;
        #[cfg(unix)]
        if let Some(dir) = parent {
            std::fs::File::open(dir)
                .and_then(|dir| dir.sync_all())
                .map_err(|e| format!("同步状态目录失败：{}", e))?;
        }
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(&tmp);
    }
    result
}

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
