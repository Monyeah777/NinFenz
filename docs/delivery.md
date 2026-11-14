# Delivery（`nf agent run --assembly --deliver`，WP-23）

> ⛔ 操作指令：本件是 WP-23 交付打包的人读说明；实现 `desktop/src/core/delivery.py`，判据 `desktop/tests/test_delivery_contract.py`，样例包 `results/delivery/wiki-module-M06/`，报告 `results/delivery/delivery-report.json`。只有 delivered + 校验通过的产物才允许打包。
> 状态：v1（G2 · 2026-11-14）· 依据：§13A L7（包完整/路径安全/可重复/sidecar 不阻塞）

## 用法

```bash
python scripts/nf.py agent run --adapter mock --intent spec/intents/sample-document.json \
  --assembly --deliver --sidecar
```

## 包结构

| 文件 | 角色 | 说明 |
|---|---|---|
| `manifest.json` | manifest | `nf-delivery/1`：slot/pipeline/version/files[path/role/digest/size]、output、assembly/validation digest；**无时间戳**（同输入逐字节可复现） |
| `artifact.md` | artifact | 通过 WP-22 校验的产物正文 |
| `evidence/sidecar.json` | sidecar | **可选**：校验报告 + 装配记录摘要；缺失不阻塞交付 |

## 校验（`verify`）

- 重算逐文件 digest/size，与 manifest 比对（篡改可检出）；
- 路径必须相对 POSIX、无 `..`/绝对路径；包内不得含 symlink；
- artifact digest 必须等于 `manifest.output.digest`；
- sidecar 声明与实物必须一致（声明有但缺失 → 红；有实物但未声明 → 红）；
- 报告 `nf-delivery-report/1` 可复算（committed == 实时 verify）。

## 拒收语义（DeliveryError）

| 码 | 触发 |
|---|---|
| `NOT-DELIVERED` | run.status 不是 delivered |
| `OUTPUT-NOT-VALIDATED` | output-report 未过 |
| `EMPTY-ARTIFACT` | 产物为空 |
| `PATH-UNSAFE` | 包内路径不安全 |

## 边界

- 交付包默认不可变（保留纪律见 `docs/sre/BCP_DR.md`）；GC/删除不在本件。
- 离线解包/重复交付属后续外部操作（OPEN）；本件只做本地包 + 可复算校验。
