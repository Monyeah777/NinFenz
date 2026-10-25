// 发布前自检：把「顶尖 npm 包」的硬要求做成可失败项（prepack 会跑它）。
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { PACKAGE_ROOT, PAYLOAD_DIR } from '../lib/paths.mjs';
import { ALLOW_DIRS, INTERNAL_DIRS, INTERNAL_ROOT_FILES } from './payload-policy.mjs';

const REPO_ROOT = path.resolve(PACKAGE_ROOT, '..', '..');
import { verifyTree, treeSha256, listFiles } from '../lib/payload.mjs';

const pkg = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8'));
const issues = [];
const warns = [];
const allowDirty = process.argv.includes('--allow-dirty');
function need(cond, msg) { if (!cond) issues.push(msg); }

// 1) 供应链：禁安装脚本（npm 生态最常被投放的一环）。
for (const bad of ['preinstall', 'install', 'postinstall']) {
  need(!pkg.scripts || !pkg.scripts[bad], 'package.json 含安装脚本 ' + bad + '（供应链红线：改为惰性首次运行初始化）');
}
// 2) 元数据完整性。
need(pkg.name && pkg.version, '缺 name/version');
need(pkg.license, '缺 license');
need(pkg.repository && pkg.repository.url, '缺 repository');
need(pkg.bugs && pkg.bugs.url, '缺 bugs');
need(pkg.homepage, '缺 homepage');
need(pkg.engines && pkg.engines.node, '缺 engines.node（须声明 Node 下限）');
need(pkg.type === 'module', 'type 应为 module（ESM）');
need(pkg.publishConfig && pkg.publishConfig.provenance === true, 'publishConfig.provenance 必须为 true（发布须带来源证明）');
need(Array.isArray(pkg.files) && pkg.files.indexOf('payload/') >= 0, 'files 未包含 payload/');
need(Array.isArray(pkg.files) && pkg.files.indexOf('bin/') >= 0, 'files 未包含 bin/');
need(pkg.bin && pkg.bin.nf === 'bin/nf.mjs' && pkg.bin.ninfenz === 'bin/nf.mjs', 'bin 须同时暴露 nf 与 ninfenz');
need(Array.isArray(pkg.keywords) && pkg.keywords.length >= 8, 'keywords 过少（影响可发现性）');
// 3) 入口件在位且可执行位由 npm 处理，这里只查存在。
for (const rel of ['bin/nf.mjs', 'lib/paths.mjs', 'lib/python.mjs', 'lib/payload.mjs', 'README.md']) {
  need(fs.existsSync(path.join(PACKAGE_ROOT, rel)), '缺入口件 ' + rel);
}
// 4) payload 清单与逐文件校验。
const manifestPath = path.join(PAYLOAD_DIR, 'payload-manifest.json');
if (!fs.existsSync(manifestPath)) {
  issues.push('缺 payload 清单（修复指引：先跑 npm run stage）');
} else {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  need(manifest.package_version === pkg.version, 'payload.package_version 与 package.json 不一致');
  need(manifest.cli_version === pkg.version, 'payload.cli_version 与 CLI 版本不一致');
  // A2（2026-10-10 审计 P1）：verify 不是新鲜度闸门——staged payload 落后 HEAD 10 个提交、
  // 41 个 payload 面文件仍 0 issue 通过。这里把清单的 source_commit 与 HEAD 对上，并把
  // 「脏工作树暂存」判死（那意味着内容不来自纯提交）。
  const rHead = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: REPO_ROOT, encoding: 'utf8' });
  const head = rHead.status === 0 ? String(rHead.stdout).trim() : '';
  if (head) {
    need(manifest.source_commit === head,
         'payload source_commit 与 HEAD 不一致：清单=' + String(manifest.source_commit).slice(0, 12)
         + ' HEAD=' + head.slice(0, 12) + '（修复指引：npm run stage 重新暂存后提交）');
  }
  const status = spawnSync('git', ['status', '--porcelain', '--untracked-files=no'],
    { cwd: REPO_ROOT, encoding: 'utf8' });
  const treeDirty = status.status === 0 && String(status.stdout || '').trim().length > 0;
  if (treeDirty) {
    need(manifest.worktree_dirty === true,
         'payload 已落后当前脏工作树（清单标 clean，但仓库有未提交改动）'
         + '（修复指引：npm run stage -- --allow-dirty，或提交后重新暂存）');
    need(allowDirty,
         '当前工作树有未提交改动：发布自检仅在 --allow-dirty 下做开发态运行'
         + '（提交后再跑默认严格模式）');
    if (allowDirty) warns.push('开发态：payload 来自脏工作树，不可作为发布 provenance');
  } else {
    need(manifest.worktree_dirty !== true,
         'payload 由脏工作树暂存（worktree_dirty=true）：内容不来自纯提交'
         + '（修复指引：提交后重新暂存）');
  }
  const bad = verifyTree(PAYLOAD_DIR, manifest);
  need(bad.length === 0, 'payload 逐文件校验不过：' + bad.slice(0, 3).join(', '));
  need(treeSha256(manifest) === manifest.tree_sha256, 'payload.tree_sha256 自洽性不过');
  for (const must of ['scripts/nf.py', 'tui/nf.py', 'verify.sh', 'llms.txt', 'LICENSE', 'desktop/src/core/paths.py']) {
    need(manifest.files.some(function (e) { return e.path === must; }), 'payload 缺关键件 ' + must);
  }
  const paths = manifest.files.map(function (e) { return e.path; });
  // 点判据按**路径段**（审计 P1-8）：只看 basename 会放过 `.internal/…/manifest` 这类件——
  // 内部件正是这样漏进 1.0.1 的 tarball。两处（stage 的 keep 与本处）口径现在唯一。
  const dots = paths.filter(function (r) {
    return r.split('/').some(function (seg) { return seg.startsWith('.'); });
  });
  need(dots.length === 0, 'payload 含点文件/点目录（npm 打包含剔除，会导致 tarball 与清单不一致）：' + dots.slice(0, 3).join(', '));
  const pyc = paths.filter(function (r) { return r.indexOf('__pycache__') >= 0 || r.endsWith('.pyc'); });
  need(pyc.length === 0, 'payload 混入字节码缓存：' + pyc.slice(0, 3).join(', '));
  // M1（2026-10-22 安全审计）：内部开发记录不得随包发布。`changes/` 里是未发布变更与审计流水，
  // 属内部材料（CWE-200；SLSA L2「产物只含声明内容」）。stage 侧已排除，这里是**判据**：
  // 排除表被误删/改回时本断言必须红，而不是静默把内部件发出去。
  const devrec = paths.filter(function (r) { return r === 'changes' || r.startsWith('changes/'); });
  need(devrec.length === 0, 'payload 含内部开发记录 changes/（信息暴露）：' + devrec.slice(0, 3).join(', '));

  // N2/L2（2026-10-25）：发布面是**白名单**——payload 的每个顶层目录都必须在 ALLOW_DIRS 里。
  // 这是结构性断言：即使将来有人往生成端加回黑名单逻辑，只要包内出现白名单外的顶层目录就红。
  {
    const tops = new Set();
    for (const r of paths) {
      const parts = r.split('/');
      if (parts.length > 1) tops.add(parts[0] + '/');
    }
    const stray = [...tops].filter(function (d) { return ALLOW_DIRS.indexOf(d) < 0; }).sort();
    need(stray.length === 0, 'payload 含白名单外的顶层目录（默认拒绝）：' + stray.slice(0, 5).join(', '));
  }

  // 内部治理内容不得随包发布（STRATEGY §四：决策意图/交接/复盘属内部材料）
  {
    const internal = paths.filter(function (r) {
      return INTERNAL_DIRS.some(function (d) { return r === d.slice(0, -1) || r.startsWith(d); })
        || INTERNAL_ROOT_FILES.indexOf(r) >= 0;
    });
    need(internal.length === 0, 'payload 含内部治理内容（决策/交接/复盘/CI 取证）：' + internal.slice(0, 5).join(', '));
  }
  // 目录实况 == 清单（审计 P1-9）：只查「清单里的」不查「多出来的」，等于给发布边界留后门。
  const listed = new Set(paths);
  const extras = listFiles(PAYLOAD_DIR).filter(function (r) {
    return r !== 'payload-manifest.json' && !listed.has(r);
  });
  need(extras.length === 0, 'payload 目录有清单外文件（会随 tarball 发布但校验不到）：' + extras.slice(0, 3).join(', '));
  const budget = Number(pkg.config && pkg.config.payload_budget_mb || 14) * 1024 * 1024;
  need(manifest.total_bytes <= budget * 4, 'payload 解包体积超预算：' + (manifest.total_bytes / 1048576).toFixed(1) + ' MB');
  if (manifest.total_bytes > budget * 2) warns.push('payload 偏大（' + (manifest.total_bytes / 1048576).toFixed(1) + ' MB），建议只带运行时面');
}
// 5) 许可证文件。
need(fs.existsSync(path.join(PAYLOAD_DIR, 'LICENSE')), 'payload 缺 LICENSE');

// 6) 包页文案的体积口径必须与 payload 清单一致（发布旧数字比不写更糟；同 site 的 sync-numbers 口径）。
if (fs.existsSync(manifestPath)) {
  const pageManifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const readmePage = path.join(PACKAGE_ROOT, 'README.md');
  if (!fs.existsSync(readmePage)) {
    issues.push('缺包页 README.md（npm 页面正文）');
  } else {
    const mm = fs.readFileSync(readmePage, 'utf8').match(/当前体积：\*\*(\d+) 件 · 解包 ([\d.]+) MB\*\*/);
    if (!mm) {
      issues.push('README 缺体积口径行（修复指引：补回「当前体积：**N 件 · 解包 X MB**」，npm run stage 会自动同步）');
    } else {
      const wantCount = String(pageManifest.count);
      const wantMb = (pageManifest.total_bytes / 1048576).toFixed(2);
      need(mm[1] === wantCount, 'README 件数过期：README=' + mm[1] + ' vs 清单=' + wantCount + '（修复指引：npm run stage 自动同步后提交）');
      need(mm[2] === wantMb, 'README 体积过期：README=' + mm[2] + ' MB vs 清单=' + wantMb + ' MB（修复指引：npm run stage 自动同步后提交）');
    }
  }
}


process.stdout.write('== NF npm 发布前自检 ==\n');
for (const w of warns) process.stdout.write('  [WARN] ' + w + '\n');
if (issues.length === 0) {
  process.stdout.write('  ✓ 全部通过（0 issue）\n');
} else {
  for (const i of issues) process.stdout.write('  ✗ ' + i + '\n');
  process.exitCode = 1;
}
