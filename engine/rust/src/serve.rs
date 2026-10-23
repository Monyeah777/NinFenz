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
        // 串行处理：一次一个连接（确定性优先）。失败不打断 accept 循环。
        let _ = handle(stream, &token);
    }
    Ok(ExitCode::SUCCESS)
}

fn handle(mut stream: TcpStream, token: &str) -> std::io::Result<()> {
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(30)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(30)));

    let line = match read_request_line(&mut stream) {
        Ok(l) => l,
        Err(e) => return respond(&mut stream, 2, b"", format!("请求不可读：{}", e).as_bytes()),
    };
    if line.len() > MAX_REQUEST_BYTES {
        return respond(&mut stream, 2, b"", "请求超上限".as_bytes());
    }

    let req: Value = match serde_json::from_str(line.trim()) {
        Ok(v) => v,
        Err(e) => return respond(&mut stream, 2, b"", format!("请求不是合法 JSON：{}", e).as_bytes()),
    };
    let proto = req.get("proto").and_then(|v| v.as_u64()).unwrap_or(0);
    if proto != PROTO {
        return respond(&mut stream, 2, b"", "proto 不符".as_bytes());
    }
    let got_token = req.get("token").and_then(|v| v.as_str()).unwrap_or("");
    if got_token != token {
        return respond(&mut stream, 2, b"", "token 不符".as_bytes());
    }
    let argv: Vec<String> = match req.get("argv").and_then(|v| v.as_array()) {
        Some(arr) => arr
            .iter()
            .filter_map(|x| x.as_str())
            .map(|s| s.to_string())
            .collect(),
        None => return respond(&mut stream, 2, b"", "缺 argv".as_bytes()),
    };
    if argv.is_empty() {
        return respond(&mut stream, 2, b"", "argv 为空".as_bytes());
    }
    if !argv_size_ok(&argv) {
        return respond(&mut stream, 2, b"", "argv 超上限".as_bytes());
    }
    if let Some(first) = argv.first() {
        if REFUSED.contains(&first.as_str()) {
            return respond(&mut stream, 2, b"", "拒跑长驻/自指命令".as_bytes());
        }
    }

    let (out, code) = crate::run_capture(&argv);
    respond(&mut stream, code, &out, b"")
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
