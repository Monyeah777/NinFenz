"""本地工作台页面（/verify）：零构建、零 CDN、离线可用。

为什么嵌在 Python 里而不是放静态目录：本地面的卖点是「拷走 nf 就能用」，不能依赖额外静态
文件的打包/路径约定——页面只是三段字符串，随服务一起分发，不会出现「页面在、资源 404」。

安全口径：CSP 锁死（default-src 'none'；脚本/样式只允许同源；不允许内联；不允许外链），
页面不引用任何外部资源——离线环境与内网环境都能跑，也不给第三方脚本任何执行位。
"""
from __future__ import annotations

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'self' data:; base-uri 'none'; form-action 'none'")

_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NF 证据复验</title>
<link rel="stylesheet" href="/assets/verify.css">
</head>
<body>
<main>
  <h1>NF 证据复验</h1>
  <p class="lede">把证据包（<code>.zip</code>）拖进来，或选择文件。
     复验全程在本机进行：页面只与本机服务通信，不上传任何地方。</p>
  <section id="drop" class="drop">
    <p><strong>拖拽证据包到此处</strong></p>
    <p class="or">或</p>
    <p><label class="btn">选择文件<input id="file" type="file" accept=".zip" hidden></label></p>
  </section>
  <section id="result" class="result" hidden>
    <h2>判定</h2>
    <dl>
      <dt>结论</dt><dd id="verdict">—</dd>
      <dt>证据强度</dt><dd id="level">—</dd>
      <dt>成员数</dt><dd id="count">—</dd>
      <dt>根</dt><dd id="root" class="mono">—</dd>
    </dl>
    <ul id="issues" class="issues"></ul>
  </section>
  <footer>
    <p class="note"><strong>口径</strong>：成立 = 成员未被改动 + 每条证明折叠到根 + 信封与主体
       自洽；<em>不等于</em>内容质量，也不等于内容真实。不可抵赖需第三方见证。</p>
    <p class="note" id="apiinfo">服务版本读取中…</p>
  </footer>
</main>
<script src="/assets/verify.js"></script>
</body>
</html>
"""

_JS = """(function () {
  "use strict";
  var drop = document.getElementById("drop");
  var input = document.getElementById("file");
  var box = document.getElementById("result");

  function set(id, text) {
    var el = document.getElementById(id);
    if (el) { el.textContent = text; }
  }

  function show(res) {
    box.hidden = false;
    var verdict = res.verdict || (res.ok ? "ok" : "invalid");
    set("verdict", verdict);
    set("level", res.level || "—");
    set("count", String(res.count === undefined ? "—" : res.count));
    set("root", res.root || "—");
    var ul = document.getElementById("issues");
    ul.textContent = "";
    var list = [];
    if (res.issues && res.issues.length) { list = res.issues; }
    else if (res.error) { list = [res.error + (res.fix ? "（" + res.fix + "）" : "")]; }
    for (var i = 0; i < list.length; i++) {
      var li = document.createElement("li");
      li.textContent = list[i];
      ul.appendChild(li);
    }
    box.className = "result " + (verdict === "ok" ? "ok" : "bad");
  }

  function submit(file) {
    if (!file) { return; }
    box.hidden = false;
    box.className = "result";
    set("verdict", "复验中…");
    set("level", "—"); set("count", "—"); set("root", "—");
    document.getElementById("issues").textContent = "";
    file.arrayBuffer().then(function (buf) {
      return fetch("/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/zip" },
        body: buf
      });
    }).then(function (r) { return r.json(); })
      .then(show)
      .catch(function (e) { show({ ok: false, error: String(e) }); });
  }

  if (input) {
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) { submit(input.files[0]); }
    });
  }
  if (drop) {
    drop.addEventListener("dragover", function (e) {
      e.preventDefault(); drop.className = "drop hot";
    });
    drop.addEventListener("dragleave", function () { drop.className = "drop"; });
    drop.addEventListener("drop", function (e) {
      e.preventDefault(); drop.className = "drop";
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        submit(e.dataTransfer.files[0]);
      }
    });
  }
  fetch("/api/health").then(function (r) { return r.json(); }).then(function (h) {
    set("apiinfo", "服务 " + h.api + " · 证据契约 " + h.evidence_schema);
  }).catch(function () { set("apiinfo", "服务不可用：请确认 nf serve --http 在跑"); });
}());
"""

_CSS = """* { box-sizing: border-box; }
body {
  margin: 0; padding: 3rem 1.25rem; background: #0f1115; color: #e7e9ee;
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 46rem; margin: 0 auto; }
h1 { font-size: 1.6rem; margin: 0 0 .5rem; }
h2 { font-size: 1.1rem; margin: 0 0 .75rem; }
.lede { color: #a8afbd; margin: 0 0 1.5rem; }
code, .mono { font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; }
.drop {
  border: 2px dashed #39414f; border-radius: 12px; padding: 2rem 1rem;
  text-align: center; transition: border-color .15s, background .15s;
}
.drop.hot { border-color: #62d0a0; background: #131a19; }
.or { color: #7d8695; margin: .75rem 0; }
.btn {
  display: inline-block; padding: .5rem 1rem; border-radius: 8px;
  background: #1f6feb; color: #fff; cursor: pointer;
}
.result { margin-top: 1.5rem; padding: 1rem 1.25rem; border-radius: 12px;
  border: 1px solid #39414f; background: #14171d; }
.result.ok { border-color: #2f8f6b; }
.result.bad { border-color: #a8434a; }
dl { display: grid; grid-template-columns: 7rem 1fr; gap: .35rem 1rem; margin: 0; }
dt { color: #8b93a1; }
dd { margin: 0; overflow-wrap: anywhere; }
.issues { margin: 1rem 0 0; padding-left: 1.25rem; color: #e0b4b8; }
footer { margin-top: 2.5rem; color: #8b93a1; font-size: .875rem; }
.note { margin: .35rem 0; }
"""


def html() -> bytes:
    return _PAGE.encode("utf-8")


def js() -> bytes:
    return _JS.encode("utf-8")


def css() -> bytes:
    return _CSS.encode("utf-8")
