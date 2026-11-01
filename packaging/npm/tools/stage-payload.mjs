// 把仓库的受跟踪文件暂存成 npm payload（含 sha256 清单 + 固定 mtime），并做口径一致性闸门。
// 用法：node tools/stage-payload.mjs [--allow-tests-off] [--quiet]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { PACKAGE_ROOT, PAYLOAD_DIR } from '../lib/paths.mjs';
import { ALLOW_DIRS, EXCLUDE_DIRS, EXCLUDE_ANY, EXCLUDE_FILES,
         INTERNAL_DIRS, INTERNAL_ROOT_FILES } from './payload-policy.mjs';

const args = process.argv.slice(2);
const quiet = args.includes('--quiet');
//: A1（2026-10-10 审计 P1）：内容取自工作树却标 HEAD 会让 provenance 失真。默认对脏树 fail-closed；
//: 本地迭代显式 --allow-dirty（清单如实记 worktree_dirty:true）。
const allowDirty = args.includes('--allow-dirty');
//: A6：README 体积口径是受跟踪文件，静默改写不可接受——显式 --sync-readme 才写。
const syncReadme = args.includes('--sync-readme');
const pkg = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8'));
const REPO_ROOT = path.resolve(PACKAGE_ROOT, '..', '..');

// 排除面：非运行时/历史/CI/打包器自身/构建产物/测试面（其余全收）。
//
// **desktop/tests/ 必须排除**（2026-10-10 全仓审计 X1，P1）：该目录装着第三方夹具
// （`fixtures/external/anthropic-official/*.SKILL.md`），其中 `docx.SKILL.md` 自述
// `license: Proprietary. LICENSE.txt has complete terms`——发布物内含专有内容（CWE-1104）。
// 测试面本就不该进运行时包：npm payload 的用途是让 `nf` 跑起来，不是分发测试套件。
// 该夹具已一并换成自写件（同一次修复的第 ② 步），本行是纵深（换件失误也不会外泄）。
// （`.release-frozen/` 曾在此列：2026-10-11 该 golden master 机制退役，目录与生成脚本已删除，
// 故不再需要排除项——保留注释是为了下次有人「重建快照」时记得它必须自带门禁。）
const EPOCH = new Date('2020-01-01T00:00:00Z');

function trackedFiles() {
  const r = spawnSync('git', ['ls-files', '-z'], { cwd: REPO_ROOT, maxBuffer: 128 * 1024 * 1024 });
  if (r.error || r.status !== 0) {
    throw new Error('git ls-files 失败（修复指引：在 git 检出里跑；' + (r.error ? r.error.message : 'status ' + r.status) + '）');
  }
  return String(r.stdout).split('\u0000').filter(Boolean).map(function (s) { return s.replace(/\\/g, '/'); });
}

function keep(rel) {
  // **点判据按路径段，不按 basename**（2026-10-10 审计 P1-8）：此前只看最后一段，于是
  // `.release-frozen/v2.12.0/sha256.manifest`（basename 不以点开头）被判「非点文件」而进包——
  // 内部冻结件就这样随 npm 发布物外泄（已实测在 1.0.1 的 tarball 里）。npm 打包剔除的是
  // **点名/点目录**，语义本来就按段，两处口径现在唯一。
  if (rel.split('/').some(function (seg) { return seg.startsWith('.'); })) return false;
  const parts = rel.split('/');
  if (parts.length === 1) {
    // 顶层文件：扁平面全收（逐件可 review），只拒点名残留件与内部治理件
    if (EXCLUDE_FILES.indexOf(rel) >= 0) return false;
    if (INTERNAL_ROOT_FILES.indexOf(rel) >= 0) return false;
  } else {
    // 顶层目录：**默认拒绝**——不在白名单里就不进包（N2/L2 的根因修法）
    if (ALLOW_DIRS.indexOf(parts[0] + '/') < 0) return false;
    if (INTERNAL_DIRS.indexOf(parts[0] + '/') >= 0) return false;   // 内部治理内容不进包
    // 白名单内部仍需排除的子面（专有夹具等，见 EXCLUDE_DIRS 注释）
    for (const d of EXCLUDE_DIRS) if (rel.startsWith(d)) return false;
  }
  for (const a of EXCLUDE_ANY) if (rel.indexOf(a) >= 0) return false;
  return true;
}

function sha256(buf) { return crypto.createHash('sha256').update(buf).digest('hex'); }

function cliVersion() {
  const text = fs.readFileSync(path.join(REPO_ROOT, 'scripts', 'nf.py'), 'utf8');
  const m = text.match(/^NF_CLI_VERSION\s*=\s*"([^"]+)"/m);
  return m ? m[1] : null;
}

function sourceCommit() {
  const r = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: REPO_ROOT, encoding: 'utf8' });
  return r.status === 0 ? String(r.stdout).trim() : 'unknown';
}

//: 可复现构建不能读墙钟。SOURCE_DATE_EPOCH 可显式覆盖；否则取源提交时间。
//: 这样同一提交、同一源树在独立构建中得到逐字节一致的 payload 清单。
function sourceEpoch() {
  const env = process.env.SOURCE_DATE_EPOCH;
  if (env && /^\d+$/.test(env)) return Number(env);
  const r = spawnSync('git', ['show', '-s', '--format=%ct', 'HEAD'],
    { cwd: REPO_ROOT, encoding: 'utf8' });
  return r.status === 0 && /^\d+$/.test(String(r.stdout).trim())
    ? Number(String(r.stdout).trim())
    : 0;
}

//: 工作树是否有**未提交的受跟踪改动**（A1）。null = 判不了（无 git）——不据此拒绝。
function worktreeDirty() {
  const r = spawnSync('git', ['status', '--porcelain', '--untracked-files=no'],
    { cwd: REPO_ROOT, encoding: 'utf8' });
  if (r.status !== 0) return null;
  return String(r.stdout).trim().length > 0;
}

const cli = cliVersion();
if (!cli) throw new Error('取不到 scripts/nf.py 的 NF_CLI_VERSION（修复指引：确认文件在场且格式未变）');
if (cli !== pkg.version) {
  throw new Error('版本口径不一致：package.json=' + pkg.version + ' vs NF_CLI_VERSION=' + cli
    + '（修复指引：发版时两处必须同值——npm 版本即 CLI 版本）');
}

const dirty = worktreeDirty();
if (dirty === true && !allowDirty) {
  // 干净的错误面（不甩 Node 栈）：这是**用法/状态**问题，不是脚本崩溃。
  process.stderr.write('✗ 工作树有未提交的受跟踪改动 ⇒ payload 内容会取自工作树而标成 HEAD='
    + sourceCommit().slice(0, 12) + '（provenance 失真）\n'
    + '  修复指引：先提交，或显式 --allow-dirty 暂存——清单会记 worktree_dirty=true\n');
  process.exit(1);
}

fs.rmSync(PAYLOAD_DIR, { recursive: true, force: true });
fs.mkdirSync(PAYLOAD_DIR, { recursive: true });

// 清单用**数组**而非对象键：仓库路径里含 `+` 等合法文件名字符，而本仓卫生判据把
// JSON 对象键当「标识面」（字符集受限）——用键会让 13 个 `AI+…` 管线文件名被判违规。
const entries = [];
let total = 0;
let count = 0;
for (const rel of trackedFiles()) {
  if (!keep(rel)) continue;
  const src = path.join(REPO_ROOT, rel);
  if (!fs.existsSync(src) || !fs.statSync(src).isFile()) continue;
  const buf = fs.readFileSync(src);
  const dst = path.join(PAYLOAD_DIR, rel);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.writeFileSync(dst, buf);
  fs.utimesSync(dst, EPOCH, EPOCH);
  entries.push({ path: rel, sha256: sha256(buf) });
  total += buf.length;
  count += 1;
}
if (count === 0) throw new Error('payload 为空（修复指引：确认在仓库根且 git ls-files 可用）');

entries.sort(function (a, b) { return a.path < b.path ? -1 : (a.path > b.path ? 1 : 0); });
const h = crypto.createHash('sha256');
for (const e of entries) h.update(e.path + '\u0000' + e.sha256 + '\n');
const tree = h.digest('hex');
const epoch = sourceEpoch();

const manifest = {
  schema: 'nf-npm-payload/1',
  package_version: pkg.version,
  cli_version: cli,
  source_commit: sourceCommit(),
  worktree_dirty: dirty === true,
  source_date_epoch: epoch,
  generated_at: new Date(epoch * 1000).toISOString(),
  count: count,
  total_bytes: total,
  tree_sha256: tree,
  files: entries
};
fs.writeFileSync(path.join(PAYLOAD_DIR, 'payload-manifest.json'), JSON.stringify(manifest, null, 2) + '\n', { mode: 420 });

// 包根也放一份 LICENSE（npm 页面与法务面惯例；payload 内那份仍随工作树走）。
const licSrc = path.join(REPO_ROOT, 'LICENSE');
if (fs.existsSync(licSrc)) {
  const licDst = path.join(PACKAGE_ROOT, 'LICENSE');
  fs.writeFileSync(licDst, fs.readFileSync(licSrc));
  fs.utimesSync(licDst, EPOCH, EPOCH);
}

const mb = function (n) { return (n / (1024 * 1024)).toFixed(2) + ' MB'; };
if (!quiet) {
  process.stdout.write('== NF npm payload 暂存 ==\n');
  process.stdout.write('  文件 ' + count + ' 件 · 解包 ' + mb(total) + ' · tree_sha256 ' + tree.slice(0, 16) + '\n');
  process.stdout.write('  CLI 版本 ' + cli + ' · 源提交 ' + manifest.source_commit.slice(0, 12)
    + (manifest.worktree_dirty ? '（**脏工作树**：内容含未提交改动，不可作为发布 provenance）' : '') + '\n');
  process.stdout.write('  预算（解包） ' + pkg.config.payload_budget_mb + ' MB × 3.5 ≈ ' + mb(pkg.config.payload_budget_mb * 3.5 * 1024 * 1024) + '\n');
}
// 包页文案的体积口径与清单**同步**（verify 里做判死）：同 site/tools/sync-numbers.mjs 的分工。
// 为什么：README 就是 npm 页面正文，写着过期件数/体积等于发布旧数字（2026-10-07 实测：README 写
// 2809 件 / 18.74 MB / 39 条门禁，真值已是 2939 件 / 19.72 MB / check1-40）。
const README_PATH = path.join(PACKAGE_ROOT, 'README.md');
const SIZE_RE = /当前体积：\*\*(\d+) 件 · 解包 ([\d.]+) MB\*\*/;
if (fs.existsSync(README_PATH)) {
  const text = fs.readFileSync(README_PATH, 'utf8');
  const want = '当前体积：**' + count + ' 件 · 解包 ' + mb(total) + '**';
  if (!SIZE_RE.test(text)) {
    if (!quiet) process.stdout.write('  [WARN] README 缺体积口径行（verify 会判死；修复指引：补回「当前体积：**N 件 · 解包 X MB**」）\n');
  } else if (!text.includes(want)) {
    // A6（2026-10-10 审计 P2）：README 是**受跟踪**文件，此前 stage 会静默改写它。现改为：
    // 不给 --sync-readme 就只报错退出（让改动可见、可评审），给了才写。
    if (syncReadme) {
      fs.writeFileSync(README_PATH, text.replace(SIZE_RE, want));
      if (!quiet) process.stdout.write('  ✓ README 体积口径已同步（--sync-readme）：' + count + ' 件 · ' + mb(total) + '\n');
    } else {
      process.exitCode = 1;
      process.stdout.write('  ✗ README 体积口径过期：' + text.match(SIZE_RE)[1] + ' 件 / '
        + text.match(SIZE_RE)[2] + ' MB → 应为 ' + count + ' 件 / ' + mb(total)
        + '（修复指引：npm run stage -- --sync-readme 显式同步后提交）\n');
    }
  }
}

