// tarball 与 payload 清单逐字节核对（审计 A3）。
//
// 为什么需要：verify-package.mjs 只核对 payload 目录与清单，从不核对「npm pack 真打出来的
// tarball」——于是「打包器忽略规则 / 与清单分叉」这一整面无人看。A3（2026-10-10 审计 P1）：
// staged payload 落后 HEAD 10 个提交仍 0 issue 通过，正是缺了「从清单到发布物」的最后一跳。
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { PACKAGE_ROOT, PAYLOAD_DIR, MANIFEST_NAME } from '../lib/paths.mjs';

const args = process.argv.slice(2);
const idx = args.indexOf('--tarball');
const quiet = args.includes('--quiet');

function sha256File(p) {
  return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

function listFiles(dir) {
  const out = [];
  const walk = function (base, rel) {
    for (const ent of fs.readdirSync(base, { withFileTypes: true })) {
      const r = rel ? rel + '/' + ent.name : ent.name;
      if (ent.isDirectory()) walk(path.join(base, ent.name), r);
      else if (ent.isFile()) out.push(r);
    }
  };
  if (fs.existsSync(dir)) walk(dir, '');
  return out.sort();
}

const manifestPath = path.join(PAYLOAD_DIR, MANIFEST_NAME);
if (!fs.existsSync(manifestPath)) {
  console.error('\u2717 payload 未暂存：' + manifestPath + '（修复指引：npm run stage）');
  process.exit(2);
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'nf-tarball-'));
let tarball = '';
if (idx >= 0 && args[idx + 1]) {
  tarball = path.resolve(args[idx + 1]);
  if (!fs.existsSync(tarball)) {
    console.error('\u2717 指定的 tarball 不在场：' + tarball);
    process.exit(2);
  }
  // 解包基准目录始终是本次临时目录；显式传入的 tarball 先复制进来，
  // 避免跨盘 `tar -C` 与 GNU/BSD 参数语义差异。
  const copy = path.join(tmp, path.basename(tarball));
  if (path.resolve(copy) !== path.resolve(tarball)) fs.copyFileSync(tarball, copy);
  tarball = copy;
} else {
  // Windows 上 npm 是 .cmd 垫片：必须经 shell 才能 spawn（Node 对 .cmd 直接 spawn 返 EINVAL）。
  // 传**单个命令串**而不是「shell:true + 参数数组」，避开 DEP0190（参数不转义的告警）。
  const packArgs = ['pack', '--ignore-scripts', '--silent', '--pack-destination', tmp];
  let npmBin = 'npm';
  if (process.platform === 'win32') {
    const cand = path.join(path.dirname(process.execPath), 'npm.cmd');
    npmBin = fs.existsSync(cand) ? cand : 'npm.cmd';
  }
  const opt = { cwd: PACKAGE_ROOT, encoding: 'utf8' };
  // 命令与参数**都要**按需加引号：npm 装在 "C:\Program Files\..." 时，不引命令会按空格切分
  // （2026-10-10 实测：'C:\Program' is not recognized）。
  const q = function (a) { return /\s/.test(a) ? '"' + a + '"' : a; };
  const r = process.platform === 'win32'
    ? spawnSync([q(npmBin)].concat(packArgs.map(q)).join(' '), Object.assign({ shell: true }, opt))
    : spawnSync('npm', packArgs, opt);
  if (r.status !== 0) {
    console.error('\u2717 npm pack 失败：' + (r.error ? r.error.message : (r.stderr || r.stdout)));
    process.exit(2);
  }
  const name = String(r.stdout).trim().split(/\r?\n/).filter(Boolean).pop();
  tarball = path.join(tmp, name);
  if (!fs.existsSync(tarball)) {
    console.error('\u2717 npm pack 未产出 tarball：' + tarball);
    process.exit(2);
  }
}

// cwd = tarball 所在目录 + 只传 basename：GNU tar（Git-Bash/msys）会把带盘符的绝对路径
// 当成「host:path」远程规格（实测报 "Cannot connect to C: resolve failed"），bsdtar 则接受。
// 传相对名对两者都成立（-C 的目标目录是选项值，不参与 host:path 解析）。
// ★ 两端都用**相对路径**：GNU tar（Git-Bash/msys）既会把带盘符的存档路径当 host:path，
// 也会在 -C 上把 "C:\..." 解析歪（实测两种报错各一）。cwd = 暂存目录、-C "." 对
// GNU tar 与 bsdtar 都成立，且不产生任何 Windows 路径解析。
const ex = spawnSync('tar', ['-xzf', path.basename(tarball), '-C', '.'],
                     { cwd: tmp, encoding: 'utf8' });
if (ex.status !== 0) {
  console.error('\u2717 解包失败：' + (ex.stderr || ''));
  process.exit(2);
}
const root = path.join(tmp, 'package');
const issues = [];
function need(ok, msg) { if (!ok) issues.push(msg); }

// 4) 包版本
try {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
  need(pkg.version === manifest.package_version,
    'tarball package.json version=' + pkg.version + ' != 清单 ' + manifest.package_version);
} catch (e) {
  issues.push('tarball 内 package.json 不可读：' + e.message);
}

// 1) 清单自身
const payloadRoot = path.join(root, 'payload');
const manInTar = path.join(payloadRoot, MANIFEST_NAME);
need(fs.existsSync(manInTar), 'tarball 缺 payload/' + MANIFEST_NAME);
if (fs.existsSync(manInTar)) {
  need(sha256File(manInTar) === sha256File(manifestPath),
    'tarball 内清单与本地清单不一致（打包器改了字节）');
}

// 2) 逐文件
for (const e of manifest.files || []) {
  const abs = path.join(payloadRoot, e.path);
  if (!fs.existsSync(abs)) { issues.push('tarball 缺件：payload/' + e.path); continue; }
  if (sha256File(abs) !== e.sha256) { issues.push('tarball 摘要不符：payload/' + e.path); }
}

// 3) 清单外文件
const listed = new Set((manifest.files || []).map(function (e) { return e.path; }));
const extra = listFiles(payloadRoot).filter(function (r) {
  return r !== MANIFEST_NAME && !listed.has(r);
});
need(extra.length === 0, 'tarball 内 payload 有清单外文件：' + extra.slice(0, 3).join(', '));

if (issues.length) {
  for (const i of issues.slice(0, 10)) console.error('\u2717 ' + i);
  console.error('\u2717 tarball 核对未过（' + issues.length + ' 处）');
  process.exit(1);
}
if (!quiet) {
  console.log('\u2713 tarball 与 payload 清单逐字节一致（' + (manifest.files || []).length
    + ' 件 · ' + path.basename(tarball) + '）');
}
