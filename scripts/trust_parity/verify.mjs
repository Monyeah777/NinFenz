#!/usr/bin/env node
// 独立实现（Node.js）：对冻结 trust 向量做逐字节复算，用于 Python ↔ Node.js parity。
// 不 import 任何 Python/仓内 JS 实现；只读 vectors JSON。entity 族需要完整 JSON Schema 引擎，
// 不在本独立实现范围（如实列入 skipped，不冒充覆盖）。
// 用法：node tools/trust_parity/verify.mjs --vectors results/trust/trust_vectors.json [--json]
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const TAG_RE = /^nf:[a-z0-9-]+:v[1-9][0-9]*:[a-z0-9-]+$/;
const DIGEST_RE = /^[0-9a-f]{64}$/;
const ZERO = "0".repeat(64);
const SEP = Buffer.from([0]);

function sha256(data) {
  return createHash("sha256").update(data).digest("hex");
}

function rejectFloat(node, path) {
  if (typeof node === "number") {
    if (!Number.isFinite(node)) throw new Error(path + ": NONFINITE-FORBIDDEN");
    if (!Number.isInteger(node) || !Number.isSafeInteger(node)) {
      throw new Error(path + ": FLOAT-FORBIDDEN");
    }
    return;
  }
  if (node === null || typeof node === "boolean" || typeof node === "string") return;
  if (Array.isArray(node)) {
    node.forEach((item, i) => rejectFloat(item, path + "[" + i + "]"));
    return;
  }
  if (node && typeof node === "object") {
    if (Object.prototype.hasOwnProperty.call(node, "nonfinite") && node.nonfinite === "NaN") {
      throw new Error(path + ": NONFINITE-FORBIDDEN");
    }
    for (const key of Object.keys(node)) rejectFloat(node[key], path + "." + key);
    return;
  }
  throw new Error(path + ": unsupported type");
}

function canonical(obj) {
  rejectFloat(obj, "$");
  const value = (node) => {
    if (node === null) return "null";
    if (typeof node === "boolean" || typeof node === "number") return String(node);
    if (typeof node === "string") return JSON.stringify(node);
    if (Array.isArray(node)) return "[" + node.map(value).join(",") + "]";
    const keys = Object.keys(node).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + value(node[k])).join(",") + "}";
  };
  return value(obj);
}

function canonicalBytes(obj) {
  return Buffer.from(canonical(obj), "utf8");
}

function digestOf(obj) {
  return sha256(canonicalBytes(obj));
}

function domainDigest(tag, payload) {
  if (!TAG_RE.test(tag)) throw new Error("TAG-FORMAT");
  return sha256(Buffer.concat([Buffer.from(tag, "utf8"), SEP, Buffer.from(payload)]));
}

function leafHash(data) {
  return Buffer.from(sha256(Buffer.concat([Buffer.from([0]), Buffer.from(data)])), "hex");
}

function nodeHash(left, right) {
  return Buffer.from(sha256(Buffer.concat([Buffer.from([1]), left, right])), "hex");
}

function merkleRoot(leaves) {
  if (leaves.length === 0) return null;
  if (leaves.length === 1) return leaves[0];
  let mid = 1;
  while (mid * 2 < leaves.length) mid *= 2;
  return nodeHash(merkleRoot(leaves.slice(0, mid)), merkleRoot(leaves.slice(mid)));
}

function inclusionProof(leaves, index) {
  if (index < 0 || index >= leaves.length) throw new Error("INDEX-OUT-OF-RANGE");
  const proof = [];
  const walk = (sub, i) => {
    if (sub.length <= 1) return;
    let mid = 1;
    while (mid * 2 < sub.length) mid *= 2;
    const left = sub.slice(0, mid);
    const right = sub.slice(mid);
    if (i < mid) {
      walk(left, i);
      proof.push({ side: "right", hash: merkleRoot(right).toString("hex") });
    } else {
      walk(right, i - mid);
      proof.push({ side: "left", hash: merkleRoot(left).toString("hex") });
    }
  };
  walk(leaves, index);
  return proof;
}

function foldProof(leafHex, proof) {
  let cur = Buffer.from(leafHex, "hex");
  for (const step of proof) {
    const sib = Buffer.from(step.hash, "hex");
    cur = step.side === "left" ? nodeHash(sib, cur) : nodeHash(cur, sib);
  }
  return cur.toString("hex");
}

function pae(ptype, payload) {
  if (ptype.length === 0) throw new Error("PAE-EMPTY-TYPE");
  return Buffer.concat([
    Buffer.from("DSSEv1 " + ptype.length + " ", "utf8"), ptype,
    Buffer.from(" " + payload.length + " ", "utf8"), payload,
  ]);
}

const STEP_FIELDS = ["schema", "process_id", "step", "prev", "actor", "authorization",
  "input_refs", "output_refs", "state_digest", "type"];

function stepDigest(step) {
  for (const field of STEP_FIELDS) {
    if (!(field in step)) throw new Error("STEP-MISSING-FIELD");
  }
  const body = {};
  for (const key of Object.keys(step)) if (key !== "digest") body[key] = step[key];
  return domainDigest("nf:process:v1:step", canonicalBytes(body));
}

function verifyChain(steps) {
  if (!Array.isArray(steps) || steps.length === 0) return { valid: false, reason: "STEPS-EMPTY" };
  const digests = [];
  let head = ZERO;
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (!step || typeof step !== "object" || Array.isArray(step)) {
      return { valid: false, reason: "STEP-NOT-OBJECT" };
    }
    if (typeof step.prev !== "string" || !DIGEST_RE.test(step.prev)) {
      return { valid: false, reason: "PREV-FORMAT" };
    }
    if (step.step !== i + 1) return { valid: false, reason: "SEQ-ORDER" };
    if (step.prev !== head) return { valid: false, reason: "PREV-MISMATCH" };
    head = stepDigest(step);
    digests.push(head);
  }
  return { valid: true, digests, head };
}

const LEVELS = ["T0", "T1", "T2", "T3", "T4"];
const FACT = { T1: "signature", T2: "time_token", T3: "transparency_sth", T4: "public_anchor" };
const CODES = { T1: "SIGNATURE-MISSING", T2: "ANCHOR-MISSING", T3: "WITNESS-MISSING", T4: "PUBLIC-ANCHOR-MISSING" };

function decide(facts, required, policyOk) {
  if (!LEVELS.includes(required)) throw new Error("required_level 非法");
  if (!policyOk) return { achieved: "none", exit_code: 2, missing: ["POLICY-INVALID"] };
  if (facts.hash !== "ok") return { achieved: "none", exit_code: 1, missing: [] };
  for (const level of LEVELS.slice(1)) {
    if (facts[FACT[level]] === "invalid") return { achieved: "none", exit_code: 1, missing: [] };
  }
  let achieved = "T0";
  for (const level of LEVELS.slice(1)) {
    if (facts[FACT[level]] !== "ok") break;
    achieved = level;
  }
  if (LEVELS.indexOf(achieved) >= LEVELS.indexOf(required)) {
    return { achieved, exit_code: 0, missing: [] };
  }
  const missing = [];
  for (let i = LEVELS.indexOf(achieved) + 1; i <= LEVELS.indexOf(required); i++) {
    missing.push(CODES[LEVELS[i]]);
  }
  return { achieved, exit_code: 2, missing };
}

function eq(a, b) {
  if (a === b) return true;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((item, i) => eq(item, b[i]));
  }
  if (a && b && typeof a === "object" && typeof b === "object") {
    const ka = Object.keys(a).sort();
    const kb = Object.keys(b).sort();
    if (ka.length !== kb.length) return false;
    return ka.every((key, i) => key === kb[i] && eq(a[key], b[key]));
  }
  return false;
}

function checkVector(vec) {
  const family = vec.family;
  const input = vec.input || {};
  const expected = vec.expected || {};
  try {
    if (family === "canonical") {
      if (expected.valid === false) {
        try {
          canonical(input.value);
          return { id: vec.id, ok: false, detail: "期望拒绝但通过" };
        } catch (err) {
          return { id: vec.id, ok: String(err.message).includes(expected.reason),
                   detail: String(err.message) };
        }
      }
      const text = canonical(input.value);
      const got = { canonical_utf8: text, sha256: sha256(Buffer.from(text, "utf8")), valid: true };
      return { id: vec.id, ok: eq(got, expected), detail: got };
    }
    if (family === "domain") {
      if (expected.tag_ok === false) {
        try {
          domainDigest(input.tag, Buffer.from(input.payload_utf8, "utf8"));
          return { id: vec.id, ok: false, detail: "期望 TAG-FORMAT 拒绝" };
        } catch (err) {
          return { id: vec.id, ok: String(err.message) === expected.reason,
                   detail: String(err.message) };
        }
      }
      const payload = Buffer.from(input.payload_utf8, "utf8");
      const got = { digest: domainDigest(input.tag, payload), tag_ok: true };
      if (expected.distinct_from) {
        const alt = input.tag.endsWith(":leaf")
          ? input.tag.replace(/:leaf$/, ":root")
          : input.tag.replace(/:root$/, ":leaf");
        got.distinct_from = domainDigest(alt, payload);
      }
      return { id: vec.id, ok: eq(got, expected), detail: got };
    }
    if (family === "pae") {
      const ptype = Buffer.from(input.payload_type_utf8, "utf8");
      const payload = Buffer.from(input.payload_b64, "base64");
      if (expected.valid === false) {
        try {
          pae(ptype, payload);
          return { id: vec.id, ok: false, detail: "期望拒绝但通过" };
        } catch (err) {
          return { id: vec.id, ok: String(err.message) === expected.reason,
                   detail: String(err.message) };
        }
      }
      const raw = pae(ptype, payload);
      const got = { pae_b64: raw.toString("base64"), pae_sha256: sha256(raw), valid: true };
      return { id: vec.id, ok: eq(got, expected), detail: got };
    }
    if (family === "merkle") {
      const leaves = (input.leaves_utf8 || []).map((text) => leafHash(Buffer.from(text, "utf8")));
      if (expected.valid === false) {
        try {
          inclusionProof(leaves, input.index);
          return { id: vec.id, ok: false, detail: "期望拒绝但通过" };
        } catch (err) {
          return { id: vec.id, ok: String(err.message) === expected.reason,
                   detail: String(err.message) };
        }
      }
      const root = merkleRoot(leaves);
      const got = {
        valid: true,
        leaf_hashes: leaves.map((leaf) => leaf.toString("hex")),
        root: root.toString("hex"),
        proofs: leaves.map((leaf, index) => {
          const proof = inclusionProof(leaves, index);
          return { index, proof, fold_root: foldProof(leaf.toString("hex"), proof) };
        }),
      };
      return { id: vec.id, ok: eq(got, expected), detail: got };
    }
    if (family === "process") {
      const got = verifyChain(input.steps);
      return { id: vec.id, ok: eq(got, expected), detail: got };
    }
    if (family === "level") {
      const got = decide(input.facts || {}, input.required_level, input.policy_ok !== false);
      return { id: vec.id, ok: eq(got, expected), detail: got };
    }
    return { id: vec.id, ok: true, skipped: family };
  } catch (err) {
    return { id: vec.id, ok: false, detail: "异常：" + String(err.message) };
  }
}

function main() {
  const args = process.argv.slice(2);
  let vectorsPath = "results/trust/trust_vectors.json";
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--vectors") vectorsPath = args[i + 1];
  }
  const doc = JSON.parse(readFileSync(vectorsPath, "utf8"));
  if (doc.schema !== "nf-trust-vectors/1") {
    console.log(JSON.stringify({ ok: false, error: "schema 不是 nf-trust-vectors/1" }));
    process.exit(2);
  }
  const checked = {};
  const skipped = [];
  const mismatches = [];
  for (const vec of doc.vectors || []) {
    const result = checkVector(vec);
    if (result.skipped) { skipped.push(vec.family); continue; }
    checked[vec.family] = (checked[vec.family] || 0) + 1;
    if (!result.ok) mismatches.push(result);
  }
  const report = { ok: mismatches.length === 0, checked, skipped: [...new Set(skipped)],
                   mismatches, total: (doc.vectors || []).length };
  console.log(JSON.stringify(report, null, 2));
  process.exit(report.ok ? 0 : 1);
}

main();
