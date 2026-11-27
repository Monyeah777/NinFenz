use super::*;

/// 协议版本（与 daemon.py 的 PROTO 平行编号；改动请求形状即 +1）。
pub(crate) const PROTO: u64 = 1;

pub(crate) const BIND_HOST: &str = "127.0.0.1";

/// 请求体上限（1 MiB）：一条只读判据的 argv 远小于此；设上限防「自称超长」的无界读。
pub(crate) const MAX_REQUEST_BYTES: usize = 1 << 20;

/// 单响应上限：防止失控判据把 worker 与客户端内存一起拖垮。
pub(crate) const MAX_RESPONSE_BYTES: usize = 16 << 20;

/// 单条 argv 上限（字符）与合计上限（字符）：参数是命令/选项/标识符，不是正文载荷。
pub(crate) const MAX_ARGV_CHARS: usize = 8192;

pub(crate) const MAX_ARGV_TOTAL: usize = 65536;

/// 只读命令白名单。未知/未来命令默认拒绝，避免新增写面被 worker 静默继承。
pub(crate) const READ_COMMANDS: &[&str] = &[
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
pub(crate) const WRITE_OPTIONS: &[&str] = &[
    "--out",
    "--write",
    "--write-baseline",
    "--cwd",
    "--root=",
    "--write=",
    "--out=",
];

pub(crate) static REQUESTS: AtomicU64 = AtomicU64::new(0);

pub(crate) static BYTES_IN: AtomicU64 = AtomicU64::new(0);

pub(crate) static BYTES_OUT: AtomicU64 = AtomicU64::new(0);

pub(crate) static ACTIVE: AtomicUsize = AtomicUsize::new(0);

pub(crate) static STATE_TMP_SEQ: AtomicU64 = AtomicU64::new(0);

pub(crate) const MAX_CONNECTIONS: usize = 16;

pub(crate) fn run_serve(args: &[String]) -> Result<ExitCode, String> {
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

pub(crate) fn handle(mut stream: TcpStream, token: &str, allowed_root: &Path) -> std::io::Result<()> {
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
        if !process_request(&mut stream, &req, token, allowed_root)? {
            break;
        }
    }
    Ok(())
}

/// 单请求：协议/令牌/统计面/参数闸门/执行出口；返回 false 表示关连接。
fn process_request(
    stream: &mut TcpStream,
    req: &Value,
    token: &str,
    allowed_root: &Path,
) -> std::io::Result<bool> {
    let proto = req.get("proto").and_then(|v| v.as_u64()).unwrap_or(0);
    if proto != PROTO {
        respond(stream, 2, b"", "proto 不符".as_bytes())?;
        return Ok(false);
    }
    let got_token = req.get("token").and_then(|v| v.as_str()).unwrap_or("");
    if !constant_time_eq(got_token.as_bytes(), token.as_bytes()) {
        respond(stream, 2, b"", "token 不符".as_bytes())?;
        return Ok(false);
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
        respond(stream, 0, payload.as_bytes(), b"")?;
        return Ok(true);
    }
    let argv = match parse_argv(req) {
        Ok(argv) => argv,
        Err(msg) => {
            respond(stream, 2, b"", msg.as_bytes())?;
            return Ok(false);
        }
    };
    if argv.is_empty() {
        respond(stream, 2, b"", "argv 为空".as_bytes())?;
        return Ok(false);
    }
    if !argv_size_ok(&argv) {
        respond(stream, 2, b"", "argv 超上限".as_bytes())?;
        return Ok(false);
    }
    if let Err(msg) = validate_argv(&argv, allowed_root) {
        respond(stream, 2, b"", msg.as_bytes())?;
        return Ok(false);
    }
    let (out, code) = crate::run_capture(&argv);
    if out.len() > MAX_RESPONSE_BYTES {
        respond(stream, 2, b"", "响应超上限".as_bytes())?;
        crate::recycle_capture_buf(out);
        return Ok(false);
    }
    BYTES_OUT.fetch_add(out.len() as u64, Ordering::Relaxed);
    respond(stream, code, &out, b"")?;
    crate::recycle_capture_buf(out);
    Ok(true)
}

pub(crate) fn read_request_line<R: BufRead>(reader: &mut R) -> std::io::Result<String> {
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

pub(crate) fn parse_argv(req: &Value) -> Result<Vec<String>, &'static str> {
    let arr = req.get("argv").and_then(Value::as_array).ok_or("缺 argv")?;
    let mut argv = Vec::with_capacity(arr.len());
    for item in arr {
        argv.push(item.as_str().ok_or("argv 必须全为字符串")?.to_string());
    }
    Ok(argv)
}

pub(crate) fn validate_argv(argv: &[String], allowed_root: &Path) -> Result<(), String> {
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

pub(crate) fn argv_size_ok(argv: &[String]) -> bool {
    for a in argv {
        if a.len() > MAX_ARGV_CHARS {
            return false;
        }
    }
    argv.iter().map(|a| a.len()).sum::<usize>() <= MAX_ARGV_TOTAL
}

pub(crate) fn respond(stream: &mut impl Write, code: i32, out: &[u8], err: &[u8]) -> std::io::Result<()> {
    let head = format!("{}\n{}\n{}\n", code, out.len(), err.len());
    stream.write_all(head.as_bytes())?;
    stream.write_all(out)?;
    stream.write_all(err)?;
    stream.flush()
}

pub(crate) fn unix_epoch_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

pub(crate) fn make_token() -> Result<String, String> {
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

pub(crate) fn constant_time_eq(left: &[u8], right: &[u8]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    let mut diff = 0u8;
    for (a, b) in left.iter().zip(right) {
        diff |= a ^ b;
    }
    diff == 0
}

pub(crate) fn write_state_atomic(path: &Path, bytes: &[u8]) -> Result<(), String> {
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
