#!/usr/bin/env python3
"""空 Issue 拦截（FG-01）：正文 < 20 字符或模板必填项未填 → 评论模板入口 → 关闭。

手册 FG-01 的伪解点名两件事：① 把「欢迎新人」当成「拦截空 Issue」；② 评论了但不关闭。
本脚本只做判定（纯函数，可本地用模拟 payload 干跑），评论与关闭由 workflow 用 gh 执行——
动作链与判定分离，便于在无 GitHub 凭据的环境里自证判定逻辑。

判定口径：
- 正文先去掉 HTML 注释、模板标题行（#/## 开头的字段名）、占位符（_No response_）与
  复选框提示（- [ ]），再去掉全部空白；剩余可读字符 < 20 视为空 Issue；
- 正文里出现「_No response_」占位（GitHub Issue 表单必填项留空时的落地形态）也算必填项未填；
- 标题不参与长度判定（模板会给 "[BUG] " 前缀，标题短不代表正文空）。

用法：
  python scripts/issue_guard.py --payload event.json --json
  python scripts/issue_guard.py --payload event.json --github-output "$GITHUB_OUTPUT"
负例自证：空正文 / 短正文 / 占位符 三种模拟 payload 必须 close；完整正文必须 keep。
"""
import argparse
import contextlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop" / "src"))
from core import json_doc  # core.json_doc 是结构契约唯一读点

MIN_CHARS = 20
NO_RESPONSE_RE = re.compile(r"_?No response_?", re.I)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s.*$", re.M)
CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]\s.*$", re.M)
QUOTE_META_RE = re.compile(r"^\s*>\s.*$", re.M)


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8")


def meaningful_text(body):
    """→ (有效字符数, 是否出现 No response 占位)。模板脚手架不计入正文。"""
    if not body:
        return 0, False
    text = HTML_COMMENT_RE.sub("", body)
    placeholder = bool(NO_RESPONSE_RE.search(text))
    text = NO_RESPONSE_RE.sub("", text)
    text = HEADING_RE.sub("", text)
    text = CHECKBOX_RE.sub("", text)
    text = QUOTE_META_RE.sub("", text)
    text = re.sub(r"[\s\u3000]+", "", text)
    return len(text), placeholder


def decide(payload):
    issue = (payload or {}).get("issue") or {}
    body = issue.get("body") or ""
    chars, placeholder = meaningful_text(body)
    number = issue.get("number")
    url = issue.get("html_url") or ""
    if chars < MIN_CHARS or placeholder:
        reason = "template_fields_empty" if placeholder and chars >= MIN_CHARS else "body_too_short"
        return {"action": "close", "reason": reason, "chars": chars,
                "placeholder": placeholder, "number": number, "url": url}
    return {"action": "keep", "reason": "body_ok", "chars": chars,
            "placeholder": False, "number": number, "url": url}


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="空 Issue 判定（<20 字符或必填项为空即关闭）")
    ap.add_argument("--payload", required=True, help="GitHub issues 事件 JSON 路径")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--github-output", default=None,
                    help="把 action/reason 写进该文件（$GITHUB_OUTPUT）")
    args = ap.parse_args(argv)
    try:
        payload = json_doc.load(args.payload, dict, what="issues payload")
    except (OSError, ValueError) as exc:
        print(f"[ERROR] payload 读取失败：{exc}")
        return 2
    res = decide(payload)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write("action={}\n".format(res["action"]))
            fh.write("reason={}\n".format(res["reason"]))
            fh.write(f"chars={res['chars']}\n")
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"判定：{res['action']}（{res['reason']}，有效正文 "
              f"{res['chars']} 字符） #{res['number']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
