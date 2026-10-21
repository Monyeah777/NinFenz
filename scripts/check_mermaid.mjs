#!/usr/bin/env node
/**
 * Markdown 内 Mermaid 图真语法校验（DC-07）。
 *
 * 为什么不是「只检查有没有 mermaid 块」：那只能证明图表存在，不能证明它能编译；
 * 为什么不是「只扫 docs/」：README / CHANGELOG 里的裸图同样会在渲染时变乱码。
 * 本脚本用 mermaid 官方解析器（mermaid.parse）+ jsdom 在 Node 里真的解析每张图，
 * 报错即失败。覆盖仓库全部 tracked Markdown。
 *
 * 依赖（CI 里装到临时目录，见 .github/workflows/mermaid-check.yml）：
 *   mermaid@11.12.0  jsdom@26.1.0
 *
 * 用法：
 *   node scripts/check_mermaid.mjs --modules /path/to/node_modules
 *   node scripts/check_mermaid.mjs --list
 * 负例自证：临时造一个语法错的 mermaid 块后必须 exit 1。
 */
import { spawnSync } from 'node:child_process';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const FENCE_START = /^\s*(\u0060{3,}|~{3,})\s*mermaid\s*$/i;

function parseArgs(argv) {
  const out = { root: '.', modules: process.env.MERMAID_CHECK_MODULES || '', list: false, json: false };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--root') out.root = argv[++i];
    else if (a === '--modules') out.modules = argv[++i];
    else if (a === '--list') out.list = true;
    else if (a === '--json') out.json = true;
    else if (a === '-h' || a === '--help') {
      console.log('用法: node scripts/check_mermaid.mjs [--root DIR] [--modules DIR] [--list] [--json]');
      process.exit(0);
    } else {
      console.error('未知参数: ' + a);
      process.exit(2);
    }
  }
  return out;
}

function mdFiles(root) {
  const g = spawnSync('git', ['-C', root, '-c', 'core.quotepath=off', 'ls-files', '-z', '*.md'],
    { encoding: 'buffer' });
  if (g.status === 0) {
    return g.stdout.toString('utf8').split('\u0000').filter(Boolean);
  }
  const out = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      if (['.git', 'node_modules', '.venv', 'venv'].includes(name)) continue;
      const p = join(dir, name);
      const st = statSync(p);
      if (st.isDirectory()) walk(p);
      else if (name.toLowerCase().endsWith('.md')) out.push(p.slice(root.length + 1));
    }
  };
  walk(root);
  return out;
}

function extractBlocks(text) {
  const blocks = [];
  let inFence = false;
  let fenceChar = '';
  let startLine = 0;
  let buf = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const m = line.match(FENCE_START);
    if (!inFence) {
      if (m) {
        inFence = true;
        fenceChar = m[1][0];
        startLine = i + 1;
        buf = [];
      }
      continue;
    }
    const closeRe = new RegExp('^\\s*' + fenceChar + '{3,}\\s*$');
    if (closeRe.test(line)) {
      blocks.push({ line: startLine, code: buf.join('\n') });
      inFence = false;
      buf = [];
    } else {
      buf.push(line);
    }
  }
  if (inFence) blocks.push({ line: startLine, code: buf.join('\n'), unclosed: true });
  return blocks;
}

async function loadMermaid(modules) {
  const mermaidEntry = join(modules, 'mermaid', 'dist', 'mermaid.core.mjs');
  const jsdomEntry = join(modules, 'jsdom', 'lib', 'api.js');
  let JSDOM;
  try {
    const jsdomMod = await import(pathToFileURL(jsdomEntry).href);
    JSDOM = jsdomMod.JSDOM || (jsdomMod.default && jsdomMod.default.JSDOM);
  } catch (e) {
    throw new Error('无法加载 jsdom（' + jsdomEntry + '）：' + e.message);
  }
  if (!JSDOM) throw new Error('jsdom 导出里没有 JSDOM：' + jsdomEntry);
  const dom = new JSDOM('<!DOCTYPE html><html><body><div id="nf-mermaid"></div></body></html>',
    { pretendToBeVisual: true });
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
  for (const k of ['Element', 'HTMLElement', 'SVGElement', 'DOMParser', 'Node',
    'getComputedStyle', 'MutationObserver']) {
    if (dom.window[k] !== undefined) globalThis[k] = dom.window[k];
  }
  const mod = await import(pathToFileURL(mermaidEntry).href);
  const mermaid = mod.default || mod;
  if (typeof mermaid.parse !== 'function') {
    throw new Error('mermaid 导出里没有 parse：' + mermaidEntry);
  }
  mermaid.initialize({ startOnLoad: false });
  return mermaid;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const root = resolve(args.root);
  const modules = resolve(args.modules || join(root, 'node_modules'));
  const files = mdFiles(root);
  const blocks = [];
  let unclosed = 0;
  for (const rel of files) {
    let text;
    try {
      text = readFileSync(join(root, rel), 'utf8');
    } catch (e) {
      console.error('[ERROR] 读不了 ' + rel + '：' + e.message);
      process.exit(2);
    }
    for (const b of extractBlocks(text)) {
      if (b.unclosed) unclosed += 1;
      blocks.push({ file: rel, line: b.line, code: b.code, unclosed: b.unclosed });
    }
  }
  console.log('Mermaid 校验：md ' + files.length + ' 件，mermaid 块 ' + blocks.length + ' 个');
  if (args.list) {
    for (const b of blocks) console.log('  ' + b.file + ':' + b.line);
    return 0;
  }
  let mermaid;
  try {
    mermaid = await loadMermaid(modules);
  } catch (e) {
    console.error('[ERROR] ' + e.message);
    console.error('提示：CI 会在临时目录安装 mermaid@11.12.0 + jsdom@26.1.0，并用 --modules 指向它');
    return 2;
  }
  const failures = [];
  for (const b of blocks) {
    if (b.unclosed) {
      failures.push({ file: b.file, line: b.line, message: 'mermaid 代码围栏未闭合' });
      continue;
    }
    try {
      await mermaid.parse(b.code);
    } catch (e) {
      const message = String((e && e.message) || e).split('\n').slice(0, 3).join(' ');
      failures.push({ file: b.file, line: b.line, message });
    }
  }
  if (args.json) {
    console.log(JSON.stringify({ files: files.length, blocks: blocks.length, failures }, null, 2));
  }
  if (failures.length) {
    for (const f of failures) {
      console.error('[FAIL] ' + f.file + ':' + f.line + ' ' + f.message);
    }
    console.error('修复指引：改正 mermaid 语法（可用 mermaid.live 预览）；本检查覆盖全部 md，不只 docs/');
    return 1;
  }
  console.log('通过：全部 mermaid 块可被 mermaid 官方解析器解析');
  return 0;
}

main().then((code) => process.exit(code)).catch((e) => {
  console.error('[ERROR] ' + (e && e.stack || e));
  process.exit(2);
});
