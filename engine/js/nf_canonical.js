#!/usr/bin/env node
"use strict";
/**
 * NF 契约语义 canonical —— **第二实现（Node.js，零依赖）**
 *
 * 规范：`nf-sem-canon/1`（真源 = desktop/src/core/contract_semantics.py 的
 * canonicalize / canonical_bytes）。本件只用 Node 标准库（crypto / fs / path），
 * 不引第三方包、不发网络请求。
 *
 * 输入（stdin，UTF-8 JSON）：
 *   {"schema":"nf-sem-canon/1", "subset": <registry 子集>}
 *   - subset 为**数组** ⇒ registry 子集模式：元素是 module id，按真源口径取
 *     modules[:n] 与 protocols[:n//4+1]，再规范形（与 Python canonical_payload 同口径）；
 *   - subset 为**对象** ⇒ payload 模式：直接对该对象做规范形（边缘用例/幂等对拍用）。
 * 输出（stdout，紧凑 JSON）：
 *   {"schema":"nf-sem-canon/1","digest":"sha256:<hex>","bytes_sha256":"<hex>","bytes":<len>}
 *   - digest        = sha256("nf-sem-canon/1\n" + body) —— 语义身份，等价 Python canonical_digest
 *   - bytes_sha256  = sha256(body)（body = 规范 JSON + "\n"，不含版本行）—— 字节级校验
 *
 * 边界（**不夸大**）：本实现只覆盖 canonical 规范形（键排序 / 集合排序去重 / 数字规范化 /
 * 路径 POSIX / 紧凑分隔符 / 版本行）。W1-W3 契约规则（层序闭包 / 域隔离 / 门全性）仍只有
 * Python 单实现，本件不复制、也不声称覆盖。
 *
 * 数字边界：canonicalize 会把「整数值浮点」折叠成整数（与 Python 同口径）；但**浮点表示法**
 * 在科学计数法阈值上与 Python repr 可能不同（如 1e-7）。台架输入限定为可精确同形的十进制
 * 小数；register 里出现越界浮点属未验证面（报告里单列）。
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const CANON_VERSION = "nf-sem-canon/1";
const PAYLOAD_SCHEMA = "nf-sem-canon-payload/1";
const INPUT_SCHEMA = "nf-sem-canon/1";
const ROOT = path.resolve(__dirname, "..", "..");
const REGISTRY_REL = "desktop/src/core/registry.json";

// ---------------------------------------------------------------- 基础比较/类型
/** Python `str` 比较（Unicode 码点序；不用 JS 的 UTF-16 码元序）。 */
function cmpCodePoints(a, b) {
  const A = Array.from(String(a));
  const B = Array.from(String(b));
  const n = Math.min(A.length, B.length);
  for (let i = 0; i < n; i += 1) {
    const x = A[i].codePointAt(0);
    const y = B[i].codePointAt(0);
    if (x !== y) return x < y ? -1 : 1;
  }
  if (A.length === B.length) return 0;
  return A.length < B.length ? -1 : 1;
}

function sortedKeys(obj) {
  return Object.keys(obj).sort(cmpCodePoints);
}

/** Python `type(v)` 的字符串形态（排序键用；集合元素只可能是标量）。 */
function pyTypeName(v) {
  if (v === null) return "<class 'NoneType'>";
  if (typeof v === "boolean") return "<class 'bool'>";
  if (typeof v === "number") {
    return Number.isInteger(v) ? "<class 'int'>" : "<class 'float'>";
  }
  if (typeof v === "string") return "<class 'str'>";
  return "<class 'object'>";
}

/** Python `str(v)`（标量；集合排序键用）。 */
function pyStrScalar(v) {
  if (v === null) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (typeof v === "string") return v;
  return String(v);
}

/** Python json.dumps 的字符串转义（ensure_ascii=False）。 */
function encodeString(s) {
  let out = '"';
  for (const ch of String(s)) {
    const cp = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (cp === 8) out += "\\b";
    else if (cp === 12) out += "\\f";
    else if (cp === 10) out += "\\n";
    else if (cp === 13) out += "\\r";
    else if (cp === 9) out += "\\t";
    else if (cp < 0x20) out += "\\u" + cp.toString(16).padStart(4, "0");
    else out += ch;
  }
  return out + '"';
}

/** 数字 → Python json.dumps 文本（整数；非整浮点用 JS 最短表示，边界见文件头）。 */
function encodeNumber(v) {
  if (Object.is(v, -0)) return "0";
  if (Number.isInteger(v)) return String(v);
  return String(v);
}

/** JSON 值 → 文本；spaces=true 复刻 Python json.dumps 默认分隔符（", " / ": "）。 */
function pyDumps(value, spaces) {
  const comma = spaces ? ", " : ",";
  const colon = spaces ? ": " : ":";
  if (value === null) return "null";
  if (value === true) return "true";
  if (value === false) return "false";
  if (typeof value === "number") return encodeNumber(value);
  if (typeof value === "string") return encodeString(value);
  if (Array.isArray(value)) {
    return "[" + value.map((v) => pyDumps(v, spaces)).join(comma) + "]";
  }
  const keys = sortedKeys(value);
  return "{" + keys.map((k) => encodeString(k) + colon + pyDumps(value[k], spaces))
    .join(comma) + "}";
}

// ---------------------------------------------------------------- 规范形
/** 标量集合：按 Python set 相等语义去重（bool/int/float 同值相等），再按 (type, str) 排序。 */
function pyScalarSet(items) {
  const kept = [];
  const same = (a, b) => {
    if (a === null || b === null) return a === null && b === null;
    if (typeof a === "string" || typeof b === "string") {
      return typeof a === "string" && typeof b === "string" && a === b;
    }
    return Number(a) === Number(b); // Python: True==1==1.0；False==0
  };
  for (const item of items) {
    if (!kept.some((k) => same(k, item))) kept.push(item);
  }
  kept.sort((a, b) => {
    const ta = pyTypeName(a);
    const tb = pyTypeName(b);
    if (ta !== tb) return cmpCodePoints(ta, tb);
    return cmpCodePoints(pyStrScalar(a), pyStrScalar(b));
  });
  return kept;
}

function isScalar(v) {
  return v === null || typeof v !== "object";
}

/**
 * 规范形（与 Python canonicalize 同口径）：
 * dict 键排序 / list 集合语义排序去重 / 整数值浮点折叠为整数 / 路径反斜杠→POSIX。
 */
function canonicalize(value, sets) {
  const useSets = sets !== false;
  if (value === null) return null;
  if (Array.isArray(value)) {
    const items = value.map((v) => canonicalize(v, useSets));
    if (!useSets) return items;
    if (items.every((v) => isScalar(v))) return pyScalarSet(items);
    // 对象列表按「规范 JSON 文本」定序（与 Python json.dumps(..., sort_keys=True) 同键）
    return items.slice().sort((a, b) => cmpCodePoints(pyDumps(a, true), pyDumps(b, true)));
  }
  if (typeof value === "object") {
    const out = {};
    for (const key of sortedKeys(value)) out[String(key)] = canonicalize(value[key], useSets);
    return out;
  }
  if (typeof value === "number") {
    if (Object.is(value, -0)) return 0;
    if (Number.isInteger(value)) return value; // JSON 里 2.0 已解析为 2；等价 Python int 折叠
    return value;
  }
  if (typeof value === "string") return value.replace(/\\/g, "/");
  return value;
}

// ---------------------------------------------------------------- registry 子集载荷
function stripBom(text) {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

function loadRegistry(registryPath) {
  const rel = registryPath || process.env.NF_REGISTRY || path.join(ROOT, REGISTRY_REL);
  const raw = fs.readFileSync(rel, "utf8");
  const doc = JSON.parse(stripBom(raw));
  if (doc === null || typeof doc !== "object" || Array.isArray(doc)) {
    throw new Error("registry 顶层须为对象：" + rel);
  }
  return doc;
}

/** 与 Python canonical_payload 同口径：modules[:n]、protocols[:n//4+1]。 */
function buildPayload(reg, subsetIds) {
  const modules = (Array.isArray(reg.modules) ? reg.modules : [])
    .filter((m) => m !== null && typeof m === "object" && !Array.isArray(m));
  const protocols = (Array.isArray(reg.protocols) ? reg.protocols : [])
    .filter((p) => p !== null && typeof p === "object" && !Array.isArray(p));
  let mods = modules.slice();
  let prots = protocols.slice();
  if (subsetIds !== null && subsetIds !== undefined) {
    const wanted = new Set(subsetIds.map((x) => String(x)));
    const n = wanted.size;
    mods.sort((a, b) => cmpCodePoints(String(a.id || ""), String(b.id || "")));
    mods = mods.slice(0, Math.max(1, n));
    prots.sort((a, b) => cmpCodePoints(String(a.id || ""), String(b.id || "")));
    prots = prots.slice(0, Math.max(1, Math.floor(n / 4) + 1));
  }
  return canonicalize({
    schema: PAYLOAD_SCHEMA,
    registry_schema_version: String(reg.registry_schema_version || ""),
    modules: mods,
    protocols: prots,
    mount_points: reg.mount_points || {},
    subscriptions: reg.subscriptions || {},
  });
}

// ---------------------------------------------------------------- 字节/摘要
function canonicalBody(payload) {
  return pyDumps(payload, false) + "\n";
}

function canonicalBytes(payload) {
  return Buffer.concat([
    Buffer.from(CANON_VERSION + "\n", "utf8"),
    Buffer.from(canonicalBody(payload), "utf8"),
  ]);
}

function resultOf(payload) {
  const bytes = canonicalBytes(payload);
  const body = Buffer.from(canonicalBody(payload), "utf8");
  const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
  return {
    schema: INPUT_SCHEMA,
    digest: "sha256:" + sha(bytes),
    bytes_sha256: sha(body),
    bytes: bytes.length,
  };
}

/** 输入 {schema, subset} → 结果对象；形状/版本不对即抛（CLI 转 rc=2）。 */
function run(input) {
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("输入须为 JSON 对象：{schema, subset}");
  }
  if (String(input.schema || "") !== INPUT_SCHEMA) {
    throw new Error("输入 schema 须为 " + INPUT_SCHEMA + "，实为 " + JSON.stringify(input.schema));
  }
  if (!Object.prototype.hasOwnProperty.call(input, "subset")) {
    throw new Error("输入缺 subset（数组=registry 子集；对象=payload）");
  }
  let payload;
  if (Array.isArray(input.subset)) {
    payload = buildPayload(loadRegistry(input.registry), input.subset);
  } else if (input.subset !== null && typeof input.subset === "object") {
    payload = canonicalize(input.subset);
  } else {
    throw new Error("subset 须为数组（registry 子集）或对象（payload）");
  }
  return resultOf(payload);
}

// ---------------------------------------------------------------- CLI
function main() {
  for (const stream of [process.stdout, process.stderr]) {
    if (stream.setDefaultEncoding) stream.setDefaultEncoding("utf8");
  }
  let text = "";
  try {
    text = fs.readFileSync(0, "utf8");
  } catch (exc) {
    process.stderr.write("读取 stdin 失败：" + exc.message + "\n");
    return 2;
  }
  let input;
  try {
    input = JSON.parse(stripBom(text));
  } catch (exc) {
    process.stderr.write("stdin 不是合法 JSON：" + exc.message + "\n");
    return 2;
  }
  try {
    process.stdout.write(JSON.stringify(run(input)) + "\n");
  } catch (exc) {
    process.stderr.write("canonical 失败：" + exc.message + "\n");
    return 2;
  }
  return 0;
}

module.exports = {
  CANON_VERSION,
  PAYLOAD_SCHEMA,
  INPUT_SCHEMA,
  canonicalize,
  buildPayload,
  loadRegistry,
  canonicalBody,
  canonicalBytes,
  resultOf,
  run,
};

if (require.main === module) {
  process.exitCode = main();
}
