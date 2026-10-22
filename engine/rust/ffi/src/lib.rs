//! NF C ABI 绑定层（P5-07.3）。
//!
//! 为什么是它：desktop/src/core/engine_loader.py 里 ABI_SYMBOL = "nf_engine_abi_version"
//! 早已写死，且**全仓没有任何产出方**——即「同进程 FFI 装载」这条计划承诺（§16.4 的快路径）
//! 一直没有载体。本 crate 就是那个产出方：编成 cdylib 后由 ctypes 直接 dlopen。
//!
//! 边界（诚实）：
//! - 本层只导出**纯函数 + 版本号**，不做任何写盘/网络/全局状态，故 ABI 面小到可逐条枚举；
//! - 跨语言对拍的**语义**仍由 scripts/cross_lang_verify.py 的规范向量判定；本层只保证
//!   「装载得了、调得动、版本对得上」（§16.8 的 ABI/FFI 噪声风险由此收敛）；
//! - 字符串一律以 (ptr, len) 传入传出，避免 C 字符串的 NUL 截断与编码歧义。

use std::os::raw::c_char;

/// ABI 版本号。engine_loader.engine_abi() 读的就是它。
///
/// 版本升级判据：导出面（符号名 / 签名 / 语义）任一变化即 +1；纯内部重构不动它。
pub const ABI_VERSION: u32 = 1;

/// 导出符号：ABI 版本（无参数，恒可调用，用于「装载成功与否」的探针）。
#[no_mangle]
pub extern "C" fn nf_engine_abi_version() -> u32 {
    ABI_VERSION
}

/// 把 UTF-8 字节逐字节反转后写进调用方给的缓冲；成功时返回写出的字节数 `len`。
///
/// 契约（调用方按此判错，不做隐式截断，也**不**用返回值暗示「所需长度」）：
/// - 非法输出缓冲（`out` 为空 / `cap < len`）一律**拒绝**：一个字节都不写、返回 **0**。
///   为什么不再「返回所需长度」：调用方极易把返回值当「已写 `len` 字节」，而后据此判
///   「已加密 / 已写盘」——那是静默失败（VULN-02 F1，CWE-393 / ASVS V5.3）。
///   要拿所需长度就自己按输入长度算（本函数是**定长搬运**，所需长度恒等于 `len`）。
/// - 成功写入返回 len；
/// - 输入指针为空时返回 0（拒绝非法调用，不裸崩）；**任何 len（含 0）都不进
///   `from_raw_parts`**——`null + len=0` 也是 UB（VULN-02 F2，CWE-476 / CWE-758）。
///
/// # Safety
/// 调用方须保证 input[0..len] 与 out[0..cap] 是可读/可写的有效区间；
/// 这是 C ABI 的固有前提。
// SAFETY: C ABI 出口必然 `unsafe`；本函数把调用方承诺的有效区间收窄成**可判前置条件**：
// 任一指针为空即拒绝返回 0，绝不把可能为空的指针交给 `from_raw_parts`（见下方 F2 守卫）。
#[no_mangle]
pub unsafe extern "C" fn nf_reverse_bytes(input: *const u8, len: usize, out: *mut u8,
                                          cap: usize) -> usize {
    if input.is_null() {
        // F2：**任何** null 都拒绝，不只 len>0。`from_raw_parts(null, 0)` 仍是 UB
        //（标准库要求指针非空且对齐，即使 len==0）。
        return 0;
    }
    if out.is_null() || cap < len {
        // F1：拒绝而不是「返回 len」。返回 len 会让调用方以为写成功（静默失败）。
        return 0;
    }
    let src = std::slice::from_raw_parts(input, len);
    let dst = std::slice::from_raw_parts_mut(out, len);
    for i in 0..len {
        dst[i] = src[len - 1 - i];
    }
    len
}

/// 导出符号：自证一次（把 ABI 版本与「装载成功」分开判，避免两者被混为一谈）。
///
/// 自证里**同时**钉住失败语义（F1）：非法输出缓冲必须被拒（返回 0），不能只钉成功路径。
#[no_mangle]
pub extern "C" fn nf_engine_abi_self_test() -> u32 {
    let probe = b"nf-ffi";
    let mut buf = [0u8; 6];
    // SAFETY: probe 与 buf 都是本函数内的固定长度数组，长度一致。
    let n = unsafe { nf_reverse_bytes(probe.as_ptr(), probe.len(), buf.as_mut_ptr(), buf.len()) };
    // SAFETY: probe 是有效切片；out 传空指针正是本负例要验的「拒绝」路径——库内先判
    // out.is_null() 再返回 0，不会解引用它。
    let refused = unsafe { nf_reverse_bytes(probe.as_ptr(), probe.len(), std::ptr::null_mut(), 0) };
    if n == probe.len() && &buf == b"iff-fn" && refused == 0 {
        ABI_VERSION
    } else {
        0
    }
}

/// 导出符号：C 字符串版本的标签（给只认字符串的装载器）。
#[no_mangle]
pub extern "C" fn nf_engine_abi_tag() -> *const c_char {
    static TAG: &[u8] = b"nf-ffi/1\0";
    TAG.as_ptr() as *const c_char
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reverse_in_place_contract() {
        let src = b"abcdef";
        let mut buf = [0u8; 6];
        let n = unsafe { nf_reverse_bytes(src.as_ptr(), 6, buf.as_mut_ptr(), 6) };
        assert_eq!(n, 6);
        assert_eq!(&buf, b"fedcba");
    }

    #[test]
    fn invalid_out_buffer_is_refused() {
        // F1（VULN-02）：容量不足**不许**返回所需长度——那会让调用方误信「已写 len 字节」。
        let src = b"abc";
        let mut buf = [0u8; 2];
        let n = unsafe { nf_reverse_bytes(src.as_ptr(), 3, buf.as_mut_ptr(), 2) };
        assert_eq!(n, 0, "容量不足必须拒绝（返回 0），不得用返回值暗示所需长度");
        assert_eq!(&buf, b"\0\0", "拒绝时一个字节都不许写");
        // 负例：out 为空（cap 也任取）必须返回 0。
        let n = unsafe { nf_reverse_bytes(src.as_ptr(), 3, std::ptr::null_mut(), 0) };
        assert_eq!(n, 0, "out 为空必须拒绝（返回 0）");
        let n = unsafe { nf_reverse_bytes(src.as_ptr(), 3, std::ptr::null_mut(), 3) };
        assert_eq!(n, 0, "out 为空且 cap 足够也必须拒绝（返回 0）");
    }

    #[test]
    fn null_input_is_refused() {
        let n = unsafe { nf_reverse_bytes(std::ptr::null(), 5, std::ptr::null_mut(), 0) };
        assert_eq!(n, 0);
        // F2（VULN-02）：`len == 0` 也必须拒绝——`from_raw_parts(null, 0)` 仍是 UB，
        // 旧守卫只挡了 `len > 0`，会把它放进切片构造。
        let n = unsafe { nf_reverse_bytes(std::ptr::null(), 0, std::ptr::null_mut(), 0) };
        assert_eq!(n, 0, "input=null 且 len=0 也必须拒绝（不许进 from_raw_parts）");
        let mut buf = [0u8; 1];
        let n = unsafe { nf_reverse_bytes(std::ptr::null(), 0, buf.as_mut_ptr(), 1) };
        assert_eq!(n, 0, "input=null 且 len=0（cap 足够）也必须拒绝");
    }

    #[test]
    fn self_test_and_tag_agree_on_version() {
        assert_eq!(nf_engine_abi_self_test(), ABI_VERSION);
        assert_eq!(nf_engine_abi_version(), ABI_VERSION);
        let tag = unsafe { std::ffi::CStr::from_ptr(nf_engine_abi_tag()) };
        assert_eq!(tag.to_str().unwrap(), "nf-ffi/1");
    }
}
