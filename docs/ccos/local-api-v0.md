# 本地 HTTP 面 v0（local api）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
> **Status**: v0 已实装（nf serve --http）· **上位**: docs/ccos/abi-v0.md §4 cc_verify / §2 cc_check

## 是什么

把复验器与体检器从 CLI 摊到**本机 HTTP**：浏览器、前端页面、别的语言都能直接 POST，
不用装 Python、不用装仓库、不用记参数。「不用装也能验」的最小落点就是这个。

内部差距（2026-11-04 实证）：能力全在 CLI 面，`nf serve` 只有 MCP stdio；前端（/workbench、
/verify）没有可调的本地接口——这一层是它们的底座。

## 启动

```bash
python scripts/nf.py serve --http            # 缺省 127.0.0.1:8765
python scripts/nf.py serve --http --port 0   # 端口交给内核挑（测试用）
```

只绑回环：`127.0.0.1` / `localhost` / `::1` 之外一律**拒绝启动**（它是本地工作台，不是网络服务）。

## 端点（v0，全部幂等 + 纯读）

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| GET | /api/health | — | 服务与契约版本、可用端点列表 |
| POST | /api/verify | 自包含证据包 zip 字节 | 四词判定 verdict / level / root / issues |
| POST | /api/check | {object: UTF-8 文本, policy: nf-check-policy/1} | verdict / policy_digest / findings |

机器可读契约：`protocol/endpoint_contract.json` 的 `local.*` 三端点（maps_to 指向真实 CLI）。

## 安全边界（写死，不靠调用方自觉）

- **只绑回环**：非回环 host 直接抛错拒绝启动。
- **CSRF 护栏**：带 `Origin` 的请求必须是本机同端口，否则 403；不带 `Origin`（curl/脚本）放行。
- **体量上限**：请求体 8 MiB；超限先读掉请求体再回 413（不读就回会让客户端看到断连而不是指引）。
- **无客户端可控路径**：请求体一律不当作路径；一切落盘在进程私有临时目录，出作用域即销毁。
- **纯读**：不写仓库、不改任何证据；两个 POST 都只产出判定。

## 判定语义（容易做错的一条）

判定结果是**判定**，不是 HTTP 错误：`invalid` / `revoked` / `expired` 一律 **200**。
4xx 只表示请求本身不成立（格式错、超限、来源不允许），5xx 表示服务侧异常。
反过来做，前端会把「证据不成立」和「服务挂了」混成一件事。

## 判据（可证）

```bash
# 起服务后手测
python scripts/nf.py serve --http --port 8765 &
curl -s http://127.0.0.1:8765/api/health
curl -s -X POST --data-binary @evidence.zip http://127.0.0.1:8765/api/verify

# 单测（起真服务打真请求：端点可用 / invalid 也 200 / Origin 挡跨站 / 体量上限 / 拒绝非回环）
python -m unittest desktop.tests.test_http_api            # 12 项全绿
```

## 边界（如实挂账）

- **不验 hmac 级**：密钥不从 HTTP 收（那是把密钥经网络送进服务端，本机也不该这么用）；
  hmac 级证据请在本地用 `nf evidence verify --key-file`。
- **只收自包含 zip**：单 JSON 形态（回执/信封）需要成员根目录，走 CLI 的 `--root`。
- **无鉴权**：本机单用户场景；将来要暴露到网络必须先做鉴权与限流，当前设计不支持。
