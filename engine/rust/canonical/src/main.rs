//! `nf-canonical` —— RFC 8785（JCS）规范化 JSON 的**独立** Rust 实现（std-only）。
//!
//! 为什么独立：跨语言契约对拍的价值来自「各语言按同一规范各自实现」；
//! 若复用他方解析器/序列化器，对拍只能证明「同一个库没变」。故本实现只依赖 std。
//!
//! 用法：`nf-canonical --file <输入.json>` → 标准输出规范化字节（**无尾换行**）。
//! 口径（RFC 8785）：键按 UTF-16 码元序、字符串最小转义、数字走 ECMAScript Number::toString、
//! 对象/数组无空白。不合法输入（重复键 / NaN / 尾随逗号 / 未配对代理）一律**非零退出并报因**，
//! 不静默降级。
use std::env;
use std::fmt::Write as _;
use std::fs;
use std::process::ExitCode;

#[derive(Debug)]
enum Json {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
}

fn err<T>(msg: &str, at: usize) -> Result<T, String> {
    Err(format!("{msg}（偏移 {at}）"))
}

impl<'a> Parser<'a> {
    fn skip_ws(&mut self) {
        while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }

    fn byte(&self) -> Option<u8> { self.b.get(self.i).copied() }

    fn lit(&mut self, word: &str) -> Result<(), String> {
        if self.b[self.i..].starts_with(word.as_bytes()) {
            self.i += word.len();
            Ok(())
        } else {
            err("字面量不合法", self.i)
        }
    }

    fn value(&mut self) -> Result<Json, String> {
        self.skip_ws();
        match self.byte() {
            Some(b'{') => self.object(),
            Some(b'[') => self.array(),
            Some(b'"') => Ok(Json::Str(self.string()?)),
            Some(b't') => { self.lit("true")?; Ok(Json::Bool(true)) }
            Some(b'f') => { self.lit("false")?; Ok(Json::Bool(false)) }
            Some(b'n') => { self.lit("null")?; Ok(Json::Null) }
            Some(c) if c == b'-' || c.is_ascii_digit() => self.number(),
            _ => err("值不合法", self.i),
        }
    }

    fn object(&mut self) -> Result<Json, String> {
        self.i += 1;
        let mut out: Vec<(String, Json)> = Vec::new();
        self.skip_ws();
        if self.byte() == Some(b'}') { self.i += 1; return Ok(Json::Obj(out)); }
        loop {
            self.skip_ws();
            if self.byte() != Some(b'"') { return err("对象键必须是字符串", self.i); }
            let k = self.string()?;
            if out.iter().any(|(ek, _)| *ek == k) {
                return err("重复键（I-JSON 不许）", self.i);
            }
            self.skip_ws();
            if self.byte() != Some(b':') { return err("缺冒号", self.i); }
            self.i += 1;
            let v = self.value()?;
            out.push((k, v));
            self.skip_ws();
            match self.byte() {
                Some(b',') => { self.i += 1; }
                Some(b'}') => { self.i += 1; break; }
                _ => return err("对象未闭合", self.i),
            }
        }
        Ok(Json::Obj(out))
    }

    fn array(&mut self) -> Result<Json, String> {
        self.i += 1;
        let mut out = Vec::new();
        self.skip_ws();
        if self.byte() == Some(b']') { self.i += 1; return Ok(Json::Arr(out)); }
        loop {
            out.push(self.value()?);
            self.skip_ws();
            match self.byte() {
                Some(b',') => { self.i += 1; }
                Some(b']') => { self.i += 1; break; }
                _ => return err("数组未闭合", self.i),
            }
        }
        Ok(Json::Arr(out))
    }

    fn hex4(&mut self) -> Result<u32, String> {
        if self.i + 4 > self.b.len() { return err("\\u 转义不全", self.i); }
        let s = std::str::from_utf8(&self.b[self.i..self.i + 4]).map_err(|_| "转义非 ASCII".to_string())?;
        let v = u32::from_str_radix(s, 16).map_err(|_| format!("转义非十六进制（偏移 {}）", self.i))?;
        self.i += 4;
        Ok(v)
    }

    fn string(&mut self) -> Result<String, String> {
        self.i += 1;
        let mut out = String::new();
        loop {
            match self.byte() {
                None => return err("字符串未闭合", self.i),
                Some(b'"') => { self.i += 1; return Ok(out); }
                Some(b'\\') => {
                    self.i += 1;
                    match self.byte() {
                        Some(b'"') => { out.push('"'); self.i += 1; }
                        Some(b'\\') => { out.push('\\'); self.i += 1; }
                        Some(b'/') => { out.push('/'); self.i += 1; }
                        Some(b'b') => { out.push('\u{0008}'); self.i += 1; }
                        Some(b'f') => { out.push('\u{000C}'); self.i += 1; }
                        Some(b'n') => { out.push('\n'); self.i += 1; }
                        Some(b'r') => { out.push('\r'); self.i += 1; }
                        Some(b't') => { out.push('\t'); self.i += 1; }
                        Some(b'u') => {
                            self.i += 1;
                            let hi = self.hex4()?;
                            let cp = if (0xD800..0xDC00).contains(&hi) {
                                if self.byte() != Some(b'\\') || self.b.get(self.i + 1) != Some(&b'u') {
                                    return err("高代理未配对", self.i);
                                }
                                self.i += 2;
                                let lo = self.hex4()?;
                                if !(0xDC00..0xE000).contains(&lo) { return err("低代理不合法", self.i); }
                                0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                            } else if (0xDC00..0xE000).contains(&hi) {
                                return err("孤立低代理", self.i);
                            } else { hi };
                            match char::from_u32(cp) {
                                Some(ch) => out.push(ch),
                                None => return err("码点不合法", self.i),
                            }
                        }
                        _ => return err("转义字符不合法", self.i),
                    }
                }
                Some(c) if c < 0x20 => return err("控制字符必须转义", self.i),
                Some(_) => {
                    let rest = std::str::from_utf8(&self.b[self.i..]).map_err(|_| "非法 UTF-8".to_string())?;
                    let ch = rest.chars().next().ok_or_else(|| "空字符".to_string())?;
                    out.push(ch);
                    self.i += ch.len_utf8();
                }
            }
        }
    }

    fn number(&mut self) -> Result<Json, String> {
        let start = self.i;
        if self.byte() == Some(b'-') { self.i += 1; }
        if self.byte() == Some(b'0') {
            self.i += 1;
        } else if matches!(self.byte(), Some(c) if c.is_ascii_digit()) {
            while matches!(self.byte(), Some(c) if c.is_ascii_digit()) { self.i += 1; }
        } else {
            return err("数字缺整数部分", self.i);
        }
        if self.byte() == Some(b'.') {
            self.i += 1;
            if !matches!(self.byte(), Some(c) if c.is_ascii_digit()) { return err("小数点后缺数字", self.i); }
            while matches!(self.byte(), Some(c) if c.is_ascii_digit()) { self.i += 1; }
        }
        if matches!(self.byte(), Some(b'e') | Some(b'E')) {
            self.i += 1;
            if matches!(self.byte(), Some(b'+') | Some(b'-')) { self.i += 1; }
            if !matches!(self.byte(), Some(c) if c.is_ascii_digit()) { return err("指数缺数字", self.i); }
            while matches!(self.byte(), Some(c) if c.is_ascii_digit()) { self.i += 1; }
        }
        let txt = std::str::from_utf8(&self.b[start..self.i]).map_err(|_| "数字非 ASCII".to_string())?;
        let v: f64 = txt.parse().map_err(|_| format!("数字越界（偏移 {start}）"))?;
        if !v.is_finite() { return err("数字非有限", start); }
        Ok(Json::Num(v))
    }
}

fn escape(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{0008}' => out.push_str("\\b"),
            '\u{000C}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => { let _ = write!(out, "\\u{:04x}", c as u32); }
            c => out.push(c),
        }
    }
    out.push('"');
}

/// ECMAScript Number::toString(x)（RFC 8785 指定的数字口径）。
fn number(v: f64, out: &mut String) {
    if v == 0.0 { out.push('0'); return; }
    let sci = format!("{:e}", v);
    let (mant, exp) = sci.split_once('e').expect("科学计数法必含 e");
    let neg = mant.starts_with('-');
    let mant = mant.trim_start_matches('-');
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let digits = digits.trim_end_matches('0');
    let digits = if digits.is_empty() { "0" } else { digits };
    let k = digits.len() as i64;
    let e: i64 = exp.parse().expect("指数必为整数");
    let n = e + 1;
    if neg { out.push('-'); }
    if k <= n && n <= 21 {
        out.push_str(digits);
        for _ in 0..(n - k) { out.push('0'); }
    } else if 0 < n && n <= 21 {
        out.push_str(&digits[..n as usize]);
        out.push('.');
        out.push_str(&digits[n as usize..]);
    } else if -6 < n && n <= 0 {
        out.push_str("0.");
        for _ in 0..(-n) { out.push('0'); }
        out.push_str(digits);
    } else {
        out.push_str(&digits[..1]);
        if k > 1 { out.push('.'); out.push_str(&digits[1..]); }
        let _ = write!(out, "e{}", if n - 1 >= 0 { "+" } else { "-" });
        let _ = write!(out, "{}", (n - 1).abs());
    }
}

fn emit(v: &Json, out: &mut String) {
    match v {
        Json::Null => out.push_str("null"),
        Json::Bool(true) => out.push_str("true"),
        Json::Bool(false) => out.push_str("false"),
        Json::Num(x) => number(*x, out),
        Json::Str(s) => escape(s, out),
        Json::Arr(items) => {
            out.push('[');
            for (i, it) in items.iter().enumerate() {
                if i > 0 { out.push(','); }
                emit(it, out);
            }
            out.push(']');
        }
        Json::Obj(kv) => {
            let mut sorted: Vec<&(String, Json)> = kv.iter().collect();
            sorted.sort_by(|a, b| {
                let (x, y) = (a.0.encode_utf16().collect::<Vec<u16>>(), b.0.encode_utf16().collect::<Vec<u16>>());
                x.cmp(&y)
            });
            out.push('{');
            for (i, (k, val)) in sorted.iter().enumerate() {
                if i > 0 { out.push(','); }
                escape(k, out);
                out.push(':');
                emit(val, out);
            }
            out.push('}');
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut file: Option<String> = None;
    let mut rule = "jcs".to_string();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--file" => { i += 1; file = args.get(i).cloned(); }
            "--rule" => { i += 1; rule = args.get(i).cloned().unwrap_or_default(); }
            other => { eprintln!("未知参数：{other}（用法：nf-canonical --file <输入.json>）"); return ExitCode::from(2); }
        }
        i += 1;
    }
    let Some(path) = file else {
        eprintln!("缺 --file（用法：nf-canonical --file <输入.json>）");
        return ExitCode::from(2);
    };
    let bytes = match fs::read(&path) {
        Ok(b) => b,
        Err(e) => { eprintln!("读不到 {path}：{e}"); return ExitCode::from(2); }
    };
    // 「读得到但内容非法」与「读不到」分开：前者是输入错误（1），后者是用法/环境错误（2）。
    // 三语言逐条对齐（C# / Python 侧同一口径），否则对拍器无法用 rc 统一判「拒绝」。
    let text = match String::from_utf8(bytes) {
        Ok(t) => t,
        Err(_) => { eprintln!("输入不是合法 UTF-8"); return ExitCode::from(1); }
    };
    let mut p = Parser { b: text.as_bytes(), i: 0 };
    let v = match p.value() {
        Ok(v) => v,
        Err(msg) => { eprintln!("输入不是合法 JSON：{msg}"); return ExitCode::from(1); }
    };
    p.skip_ws();
    if p.i != p.b.len() { eprintln!("尾随内容（偏移 {}）", p.i); return ExitCode::from(1); }
    if rule != "jcs" { eprintln!("暂不支持的规则：{rule}（当前只有 jcs）"); return ExitCode::from(2); }
    let mut out = String::new();
    emit(&v, &mut out);
    print!("{out}");
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    fn canon(s: &str) -> String {
        let mut p = Parser { b: s.as_bytes(), i: 0 };
        let v = p.value().expect("应能解析");
        let mut out = String::new();
        emit(&v, &mut out);
        out
    }

    /// 与 CLI 同口径的「拒绝」判据：解析失败，或解析后仍有尾随内容。
    fn rejected(s: &str) -> bool {
        let mut p = Parser { b: s.as_bytes(), i: 0 };
        if p.value().is_err() {
            return true;
        }
        p.skip_ws();
        p.i != p.b.len()
    }

    #[test]
    fn vector_basic_ascii() {
        assert_eq!(canon(r#"{"c":"xy","a":[2,1.5,true,null],"b":1}"#),
                   r#"{"a":[2,1.5,true,null],"b":1,"c":"xy"}"#);
    }

    #[test]
    fn keys_sorted_by_utf16_code_units() {
        // RFC 8785 §3.2.3：键按 **UTF-16 码元序**，不是码点序。
        // U+1F600 的码元是 [D83D, DE00]，首码元 D83D < E000 ⇒ 它排在 U+E000 **之前**；
        // 而按码点序（U+E000 < U+1F600）则相反。这正是与仓库 nf-canonical/1 的分歧点。
        let got = canon(r#"{"\ud83d\ude00":1,"\ue000":2}"#);
        let want = "{\"\u{1f600}\":1,\"\u{e000}\":2}";
        assert_eq!(got, want, "UTF-16 码元序：U+1F600 先于 U+E000");
    }

    #[test]
    fn number_ecmascript_forms() {
        assert_eq!(canon("[1,1.5,-0,1e-7,1e21,1e-6,100000000000000000000]"),
                   "[1,1.5,0,1e-7,1e+21,0.000001,100000000000000000000]");
        assert_eq!(canon("[0.5,1e-6,1e-7,2.5e22]"), "[0.5,0.000001,1e-7,2.5e+22]");
    }

    #[test]
    fn string_minimal_escaping() {
        // 最小转义集：仅 " \ 与 C0 控制字符；其余（含 / 与 CJK）原样。
        let esc = "\"a\\\"b\\\\c\\n\\t\\u0001\"";
        assert_eq!(canon(esc), esc);
        assert_eq!(canon("\"a\\/b\""), "\"a/b\"");
        assert_eq!(canon(r#""中""#), r#""中""#);
    }

    #[test]
    fn rejects_bad_input() {
        for bad in [r#"{"a":1,"a":2}"#, "[1,]", "NaN", "01", "\"\\ud800\"",
                    "{\"a\":1} x", "Infinity", "", "{\"a\":1,}"] {
            assert!(rejected(bad), "应被拒：{bad}");
        }
    }

    #[test]
    fn cli_writes_no_trailing_newline() {
        // 逐字节对拍的前提：CLI 输出无尾换行（尾换行会进摘要）。
        let s = canon(r#"{"b":1}"#);
        assert_eq!(s, r#"{"b":1}"#);
        assert!(!s.ends_with('\n'));
    }
}
