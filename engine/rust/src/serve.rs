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

use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};

use serde_json::{json, Value};

/// 协议版本（与 daemon.py 的 PROTO 平行编号；改动请求形状即 +1）。
const PROTO: u64 = 1;
const BIND_HOST: &str = "127.0.0.1";
/// 请求体上限（1 MiB）：一条只读判据的 argv 远小于此；设上限防「自称超长」的无界读。
const MAX_REQUEST_BYTES: usize = 1 << 20;
/// 单条 argv 上限（字符）与合计上限（字符）：参数是命令/选项/标识符，不是正文载荷。
const MAX_ARGV_CHARS: usize = 8192;
const MAX_ARGV_TOTAL: usize = 65536;
/// 本 worker 拒跑的命令（自指/长驻；与 daemon.py 的 REFUSED_COMMANDS 同纪律）。
const REFUSED: &[&str] = &["serve", "daemon", "shell", "terminal", "lsp"];

static REQUESTS: AtomicU64 = AtomicU64::new(0);
static BYTES_IN: AtomicU64 = AtomicU64::new(0);
static BYTES_OUT: AtomicU64 = AtomicU64::new(0);
static ACTIVE: AtomicUsize = AtomicUsize::new(0);
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

    let listener = TcpListener::bind((BIND_HOST, 0))
        .map_err(|e| format!("绑 {} 失败：{}", BIND_HOST, e))?;
    let addr = listener
        .local_addr()
        .map_err(|e| format!("取本地地址失败：{}", e))?;
    let port = addr.port();
    let token = make_token(port);

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
    std::fs::write(&state, text.as_bytes()).map_err(|e| format!("写状态文件失败：{}", e))?;

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
        std::thread::spawn(move || {
            let _ = handle(stream, &token);
            ACTIVE.fetch_sub(1, Ordering::SeqCst);
        });
    }
    Ok(ExitCode::SUCCESS)
}

fn handle(mut stream: TcpStream, token: &str) -> std::io::Result<()> {
    let _ = stream.set_nodelay(true);
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(30)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(30)));

    // 一条连接可承载多请求（keep-alive）；EOF/空行/协议错误即关闭。
    loop {
        let line = match read_request_line(&mut stream) {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            break;
        }
        REQUESTS.fetch_add(1, Ordering::Relaxed);
        BYTES_IN.fetch_add(line.len() as u64, Ordering::Relaxed);
        if line.len() > MAX_REQUEST_BYTES {
            respond(&mut stream, 2, b"", "请求超上限".as_bytes())?;
            break;
        }

        let req: Value = match serde_json::from_str(line.trim()) {
            Ok(v) => v,
            Err(e) => {
                respond(&mut stream, 2, b"", format!("请求不是合法 JSON：{}", e).as_bytes())?;
                break;
            }
        };
        let proto = req.get("proto").and_then(|v| v.as_u64()).unwrap_or(0);
        if proto != PROTO {
            respond(&mut stream, 2, b"", "proto 不符".as_bytes())?;
            break;
        }
        let got_token = req.get("token").and_then(|v| v.as_str()).unwrap_or("");
        if got_token != token {
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
            }).to_string();
            BYTES_OUT.fetch_add(payload.len() as u64, Ordering::Relaxed);
            respond(&mut stream, 0, payload.as_bytes(), b"")?;
            continue;
        }
        let argv: Vec<String> = match req.get("argv").and_then(|v| v.as_array()) {
            Some(arr) => arr
                .iter()
                .filter_map(|x| x.as_str())
                .map(|s| s.to_string())
                .collect(),
            None => {
                respond(&mut stream, 2, b"", "缺 argv".as_bytes())?;
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
        if let Some(first) = argv.first() {
            if REFUSED.contains(&first.as_str()) {
                respond(&mut stream, 2, b"", "拒跑长驻/自指命令".as_bytes())?;
                break;
            }
        }
        let (out, code) = crate::run_capture(&argv);
        BYTES_OUT.fetch_add(out.len() as u64, Ordering::Relaxed);
        respond(&mut stream, code, &out, b"")?;
        crate::recycle_capture_buf(out);
    }
    Ok(())
}

fn read_request_line(stream: &mut TcpStream) -> std::io::Result<String> {
    let mut buf: Vec<u8> = Vec::new();
    let mut byte = [0u8; 1];
    while buf.len() <= MAX_REQUEST_BYTES {
        match stream.read(&mut byte) {
            Ok(0) => break,
            Ok(_) => {
                if byte[0] == b'\n' {
                    break;
                }
                if byte[0] != b'\r' {
                    buf.push(byte[0]);
                }
            }
            Err(e) => return Err(e),
        }
    }
    String::from_utf8(buf)
        .map_err(|_| std::io::Error::new(std::io::ErrorKind::InvalidData, "非 UTF-8 请求"))
}

fn argv_size_ok(argv: &[String]) -> bool {
    for a in argv {
        if a.len() > MAX_ARGV_CHARS {
            return false;
        }
    }
    argv.iter().map(|a| a.len()).sum::<usize>() <= MAX_ARGV_TOTAL
}

fn respond(stream: &mut TcpStream, code: i32, out: &[u8], err: &[u8]) -> std::io::Result<()> {
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

fn make_token(port: u16) -> String {
    use sha2::Digest;
    let mut h = sha2::Sha256::new();
    h.update(std::process::id().to_string().as_bytes());
    h.update(b":");
    h.update(port.to_string().as_bytes());
    h.update(b":");
    h.update(unix_epoch_ms().to_string().as_bytes());
    let digest = h.finalize();
    digest.iter().map(|b| format!("{:02x}", b)).collect()
}
