#!/usr/bin/env node
// 站点数字与真源同步（发布钩子）：站点一次都不许发布旧数字。
//
// 真源两条：
//   1) 质量凭证 = 仓库根 llms.txt 的 nf:stats 区块（由 nf stats --write 生成，唯一事实）
//   2) 规模数字 = protocol/repo_stats.json（生成物）
//   并交叉核对两者（version / checks / PASS 三处必须自洽）。
//
// 用法：
//   node site/tools/sync-numbers.mjs           # 只检查；漂移或缺失即退出码 1（发布前把关）
//   node site/tools/sync-numbers.mjs --write   # 把质量凭证串同步进所有出现的面
//
// 覆盖面：站点全部对外面，含机器面（nf.txt / agent.txt / llms-full.txt / facts.json / use 页）。
// 机读面**必须**带 canonical 质量凭证串——机器面写着一组过时数字，比没写更糟（会被当成事实引用）。
//
// 为什么需要它：2026-10-06 实测漂移过（站点写 v2.29/check1-39/PASS=68，真源已 v2.30/check1-40/PASS=72）。

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const HERE = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const SITE = path.resolve(HERE, '..');
const ROOT = path.resolve(SITE, '..');

//: 必须出现 canonical 质量凭证串的面（缺 = 失败）
const REQUIRED = ['index.html', 'en/index.html', 'llms.txt', 'llms-full.txt', 'facts.json',
                  'nf.txt', 'agent.txt', 'use/index.html', 'en/use/index.html'];
//: 允许出现（出现即必须是 canonical；不要求出现）
const OPTIONAL = ['robots.txt', 'sitemap.xml', '404.html', 'README.md'];
//: 规模数字必须齐全的面（同一条规模行上）
const SCALE_FILES = ['index.html', 'en/index.html', 'llms.txt', 'llms-full.txt'];

const RE = /verify v\d+\.\d+ · check\d+-\d+ · PASS=\d+/g;

function read(p) { return fs.readFileSync(p, 'utf8'); }

// ---- 真源 1：llms.txt 的 nf:stats 区 ----
const src = read(path.join(ROOT, 'llms.txt'));
const m = src.match(/verify v(\d+\.\d+) · check(\d+)-(\d+) · PASS=(\d+)/);
if (!m) { console.error('未能在 llms.txt 的 nf:stats 区找到质量凭证真源'); process.exit(2); }
const want = 'verify v' + m[1] + ' · check' + m[2] + '-' + m[3] + ' · PASS=' + m[4];

// ---- 真源 2：protocol/repo_stats.json（交叉核对）----
const stats = JSON.parse(read(path.join(ROOT, 'protocol', 'repo_stats.json')));
const want2 = 'verify v' + stats.verify_version + ' · check1-' + stats.verify_checks + ' · PASS=' + stats.baseline_pass;
console.log('真源（llms.txt）      : ' + want);
console.log('真源（repo_stats.json）: ' + want2);
let fail = 0;
if (want !== want2) {
  console.error('✗ 两条真源不自洽：llms.txt 与 protocol/repo_stats.json 的质量凭证不一致');
  fail = 1;
}

// ---- 质量凭证面 ----
const write = process.argv.includes('--write');
const LIVE_FILES = [...new Set(REQUIRED.concat(OPTIONAL, ['run.sh']))];

// canonical 串存在，不代表同一面上的**局部计数**也正确。这里把 check 数、
// PASS 数与 doctor 期望单独对账，防止“页脚写对了、正文仍写旧值”的假绿。
for (const f of LIVE_FILES) {
  const p = path.join(SITE, f);
  if (!fs.existsSync(p)) continue;
  let t = read(p);
  const badChecks = [...new Set([...t.matchAll(/check1-(\d+)/g)].map((x) => x[1])
    .filter((n) => n !== String(stats.verify_checks)))];
  const badPasses = [...new Set([...t.matchAll(/PASS=(\d+)/g)].map((x) => x[1])
    .filter((n) => n !== String(stats.baseline_pass)))];
  if (badChecks.length) {
    console.error('✗ site/' + f + ' 局部 check 数漂移：check1-' + badChecks.join(' / check1-')
                  + '（真源 check1-' + stats.verify_checks + '）');
    fail = 1;
    if (write) {
      t = t.replace(/check1-\d+/g, 'check1-' + stats.verify_checks);
      fs.writeFileSync(p, t, 'utf8');
    }
  }
  if (badPasses.length) {
    console.error('✗ site/' + f + ' 局部 PASS 数漂移：PASS=' + badPasses.join(' / PASS=')
                  + '（真源 PASS=' + stats.baseline_pass + '）');
    fail = 1;
    if (write) {
      t = t.replace(/PASS=\d+/g, 'PASS=' + stats.baseline_pass);
      fs.writeFileSync(p, t, 'utf8');
    }
  }
}

// doctor 的检查项数是运行时行为，不能从页脚的质量凭证串推断。直接问
// `doctor --json`，再核对所有公开命令提示里的 N/N 期望。
const py = process.env.NF_PYTHON || 'python';
const doctorProc = spawnSync(py, [path.join(ROOT, 'scripts', 'nf.py'), 'doctor', '--json'], {
  cwd: ROOT, encoding: 'utf8', env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }
});
let doctorWant = '';
try {
  const doctor = JSON.parse(doctorProc.stdout || '{}');
  if (doctorProc.status === 0 && Number.isInteger(doctor.passed) && Number.isInteger(doctor.total)) {
    doctorWant = doctor.passed + '/' + doctor.total;
  }
} catch {
  // 解析失败统一在下一条报错中说明。
}
if (!doctorWant) {
  console.error('✗ 无法从 `python scripts/nf.py doctor --json` 取得体检计数');
  fail = 1;
} else {
  for (const f of LIVE_FILES) {
    const p = path.join(SITE, f);
    if (!fs.existsSync(p)) continue;
    const t = read(p);
    const pairs = [
      ...t.matchAll(/\bdoctor\b[^\n]{0,12}?[（(]?(\d+)\s*\/\s*(\d+)/g),
      ...t.matchAll(/体检[:：][^\n]{0,12}?(\d+)\s*\/\s*(\d+)/g),
    ];
    const bad = [...new Set(pairs.map((x) => x[1] + '/' + x[2])
      .filter((x) => x !== doctorWant))];
    if (bad.length) {
      console.error('✗ site/' + f + ' doctor 期望值漂移：' + bad.join(' / ')
                    + '（真源 ' + doctorWant + '）');
      fail = 1;
    }
  }
}

for (const f of REQUIRED.concat(OPTIONAL)) {
  const p = path.join(SITE, f);
  if (!fs.existsSync(p)) {
    if (REQUIRED.includes(f)) { console.error('✗ 缺面：site/' + f + '（REQUIRED 列表里的机器面不在场）'); fail = 1; }
    continue;
  }
  const t = read(p);
  const found = t.match(RE) || [];
  const bad = [...new Set(found.filter((x) => x !== want))];
  if (!found.length) {
    if (REQUIRED.includes(f)) {
      console.error('✗ site/' + f + ' 未出现 canonical 质量凭证串（机读面必须带上：' + want + '）');
      fail = 1;
    } else {
      console.log('  ' + f + ': 未出现该组数字（非必含面，跳过）');
    }
    continue;
  }
  if (bad.length) {
    fail = 1;
    console.error('✗ site/' + f + ': ' + bad.length + ' 处漂移 -> ' + bad.join(' / '));
    if (write) {
      fs.writeFileSync(p, t.replace(RE, want), 'utf8');
      console.error('  └ 已改写为 ' + want + '（请复核后提交）');
    }
  } else {
    console.log('  ' + f + ': ' + found.length + ' 处一致');
  }
}

// ---- 规模数字面（同一条规模行必须齐 8 个数）----
const SCALE = [stats.registered_packs, stats.pack_assets, stats.concept_graphs,
               stats.standards_total, stats.standards_reachable, stats.standards_unreachable,
               stats.standard_bindings, stats.library_items];
const MARK = /登记包|registered packs/;
for (const f of SCALE_FILES) {
  const p = path.join(SITE, f);
  if (!fs.existsSync(p)) { continue; }
  const lines = read(p).split(/\r?\n/).filter((ln) => MARK.test(ln));
  if (!lines.length) { console.error('✗ site/' + f + ' 找不到规模行（应含「登记包」或「registered packs」）'); fail = 1; continue; }
  const missing = [];
  for (const ln of lines) {
    for (const n of SCALE) {
      if (!new RegExp('(^|[^0-9])' + n + '([^0-9]|$)').test(ln)) { missing.push(f + ' 缺 ' + n); }
    }
  }
  if (missing.length) { console.error('✗ ' + [...new Set(missing)].join('；') + '（真源 protocol/repo_stats.json）'); fail = 1; }
  else { console.log('  ' + f + ': 规模 8 个数齐全'); }
}
const factsPath = path.join(SITE, 'facts.json');
if (fs.existsSync(factsPath)) {
  let fj = null;
  try { fj = JSON.parse(read(factsPath)); } catch (e) { console.error('✗ site/facts.json 不是合法 JSON：' + e.message); fail = 1; }
  if (fj) {
    const sf = (fj.facts || []).find((x) => x.id === 'scale');
    const got = sf && sf.values ? sf.values : {};
    const pairs = [[got.registered_packs, stats.registered_packs], [got.pack_assets, stats.pack_assets],
                   [got.concept_graphs, stats.concept_graphs], [got.standards_total, stats.standards_total],
                   [got.standards_reachable, stats.standards_reachable], [got.standards_unreachable, stats.standards_unreachable],
                   [got.standard_bindings, stats.standard_bindings], [got.library_items, stats.library_items]];
    const offBad = pairs.filter((x) => x[0] !== x[1]);
    if (offBad.length) { console.error('✗ site/facts.json 的 scale.values 与 repo_stats.json 不一致：' + offBad.length + ' 处'); fail = 1; }
    else { console.log('  facts.json: scale.values 与真源一致（8 项）'); }
  }
}

// ---- 真源 3：npm 包（version + 件数/体积口径一处）----
// B13/C1/C2（2026-10-10 审计 P1）：站点此前**同时**出现 ninfenz v1.0.0 与 v1.0.1，件数/体积
// 还有 2947/21.2、2953/20.25、2973 三套。现把 npm 的**版本真源**钉在 packaging/npm/package.json，
// 并要求站点所有 npm 声明行口径唯一（版本 + 件数 + 体积）——一处真源，站点不许再说另一组数。
const npmPkgPath = path.join(ROOT, 'packaging', 'npm', 'package.json');
let NPM_V = '';
try {
  NPM_V = String(JSON.parse(read(npmPkgPath)).version);
} catch (e) {
  console.error('✗ 读不到 packaging/npm/package.json 的 version：' + e.message);
  fail = 1;
}
if (NPM_V) {
  const NPM_FACES = ['index.html', 'en/index.html', 'llms.txt', 'llms-full.txt', 'facts.json',
                     'agent.txt', 'README.md', 'use/index.html', 'en/use/index.html'];
  const counts = new Set();
  const sizes = new Set();
  const VER_NEAR = new RegExp('ninfenz[\\s\\S]{0,40}?[@v](\\d+\\.\\d+\\.\\d+)', 'g');
  const VER_JSONLD = new RegExp('"softwareVersion":\\s*"(\\d+\\.\\d+\\.\\d+)"', 'g');
  for (const f of NPM_FACES) {
    const p = path.join(SITE, f);
    if (!fs.existsSync(p)) { continue; }
    const t = read(p);
    const vers = [...t.matchAll(VER_NEAR)].map((x) => x[1])
      .concat([...t.matchAll(VER_JSONLD)].map((x) => x[1]));
    const bad = [...new Set(vers.filter((v) => v !== NPM_V))];
    if (bad.length) {
      console.error('✗ site/' + f + ' npm 版本口径漂移：' + bad.map((v) => 'v' + v).join(' / ')
                    + ' ≠ packaging/npm/package.json=' + NPM_V);
      fail = 1;
      if (write) {
        fs.writeFileSync(p, t.replace(/ninfenz v\d+\.\d+\.\d+/g, 'ninfenz v' + NPM_V)
          .replace(/ninfenz@\d+\.\d+\.\d+/g, 'ninfenz@' + NPM_V), 'utf8');
        console.error('  └ 已改写为 v' + NPM_V + '（请复核后提交）');
      }
    }
    for (const ln of t.split(/\r?\n/).filter((l) => /ninfenz/.test(l))) {
      const c = ln.match(/(\d+)\s*(?:文件|files)/);
      if (c) { counts.add(c[1]); }
      const s = ln.match(/(\d+\.\d+)\s*MB/);
      if (s) { sizes.add(s[1]); }
    }
  }
  if (counts.size > 1) { console.error('✗ 站点 npm 件数口径不唯一：' + [...counts].join(' / ')); fail = 1; }
  if (sizes.size > 1) { console.error('✗ 站点 npm 体积口径不唯一：' + [...sizes].join(' / ')); fail = 1; }
  const payloadPath = path.join(ROOT, 'packaging', 'npm', 'payload', 'payload-manifest.json');
  if (fs.existsSync(payloadPath)) {
    try {
      const payload = JSON.parse(read(payloadPath));
      const wantCount = String(payload.count);
      const wantMb = (payload.total_bytes / 1048576).toFixed(2);
      if (counts.size && !(counts.size === 1 && counts.has(wantCount))) {
        console.error('✗ 站点 npm 件数与 payload 清单不一致：' + [...counts].join(' / ')
                      + '（清单 ' + wantCount + '）');
        fail = 1;
      }
      if (sizes.size && !(sizes.size === 1 && sizes.has(wantMb))) {
        console.error('✗ 站点 npm 体积与 payload 清单不一致：' + [...sizes].join(' / ')
                      + '（清单 ' + wantMb + ' MB）');
        fail = 1;
      }
    } catch (e) {
      console.error('✗ packaging/npm/payload/payload-manifest.json 不可解析：' + e.message);
      fail = 1;
    }
  } else {
    console.log('  npm payload 清单不在场（忽略：忽略面，需先 stage）');
  }
  if (!counts.size && !sizes.size) { console.log('  站点未见 npm 件数/体积声明（跳过口径一致性）'); }
  if (!fail) {
    console.log('  npm: 版本 v' + NPM_V + ' · 件数 ' + ([...counts][0] || '—')
                + ' · 体积 ' + ([...sizes][0] || '—') + ' MB（口径唯一）');
  }
}

if (!fail) { console.log('✓ 站点数字与真源一致（质量凭证 + 规模 + npm 口径）'); process.exit(0); }
console.error('✗ 站点数字未过：跑 node site/tools/sync-numbers.mjs --write 同步可自动改写的项，其余按上面指引手改');
process.exit(1);
