//! JCS 字符串转义与 ECMAScript 数字口径（RFC 8785）。

use crate::Json;
use std::fmt::Write as _;

pub(crate) fn escape(s: &str, out: &mut String) {
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
pub(crate) fn number(v: f64, out: &mut String) {
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
    number_digits(digits, k, n, out);
}

/// ECMAScript 数字落地：整数 / 小数 / 前导零 三段。
pub(crate) fn number_digits(digits: &str, k: i64, n: i64, out: &mut String) {
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
        number_exponent(digits, k, n, out);
    }
}

/// 指数形态：d.dddde±x。
pub(crate) fn number_exponent(digits: &str, k: i64, n: i64, out: &mut String) {
    out.push_str(&digits[..1]);
    if k > 1 { out.push('.'); out.push_str(&digits[1..]); }
    let _ = write!(out, "e{}", if n - 1 >= 0 { "+" } else { "-" });
    let _ = write!(out, "{}", (n - 1).abs());
}
