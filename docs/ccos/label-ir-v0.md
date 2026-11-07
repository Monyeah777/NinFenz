# 标注 IR v0（`cc_label` 的声明层）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-05
> **Status**: v0 已实装**声明层**（`core/label_ir.py` + `nf label ir|validate`）+ **载体层
> （`core/label_carrier.py`：PNG iTXt / JPEG APP15 / WebP NFLA / MP4 free 盒 / PDF 尾部注释；
> `core/label_watermark.py`：PNG 像素水印）**（`nf label embed|extract`）

## 是什么 / 不是什么

`nf-label/1` 是一份**纯数据 IR**：描述「某对象按某个标准**应当**带哪些标识」，并校验声明的形状与
档位齐备度。它**不**写载体、**不**读载体、**不**证明文件里真的带标识——载体写入在
`core/label_carrier.py`（PNG iTXt / JPEG APP15，只证读回/内容面不变/结构合法/对象绑定），
任何「已写入水印/已嵌入元数据」的宣称都不可证。

## 规则表（GB 45438 分类 · v0 映射）

| id | 面 | kind | 从哪档起必需 | 要求 |
|---|---|---|---|---|
| E1 | 显式 | text | minimal | `where`（start/end/ui）+ `value` |
| E2 | 显式 | audio | full | `value`（可听提示） |
| E3 | 显式 | metadata | full | `key` + `value`（生成合成声明字段） |
| I1 | 隐式 | watermark | full | `algorithm` + `value` |
| I2 | 隐式 | metadata | minimal | `key` + `value`（文件元数据字段） |

v0 映射**待按标准原文复核**：本表给的是「哪几类要求」而不是条款号；换标准要改 `STANDARD` 并补判据。

## 怎么用

```bash
# 组装 IR（不给 --items 就是空声明，靠校验面把缺口暴露出来）
nf label ir 产出/海报.png --level minimal --items items.json --out 产出/海报.label.json

# 校验（退出码：ok=0 / invalid=1 / 用法错=4）
nf label validate 产出/海报.label.json
```

`items.json` 是声明项数组，每项带 `face`（explicit/implicit）+ `kind` + 该 kind 的必填字段。

## 判定（可证）

| 检查 | 不过 |
|---|---|
| schema == `nf-label/1`、standard == 当前标准、level ∈ {minimal, full} | invalid |
| `object.path` 非空、`object.digest` 为 64 位十六进制 sha256 | invalid |
| `explicit` / `implicit` 是数组，且每项 kind 在该面允许集合内 | invalid |
| `carrier.embedded` 是布尔 | invalid |
| 档位必需的每条规则都有匹配声明项（kind 相符 + 必填字段非空） | invalid（列出缺哪几条） |
| `carrier.embedded=true` 但本仓无写入子系统 | **ok + warning**（不当成功，只如实提示自称） |


## sidecar 回退载体（v0 已实装）

嵌入载体做不到时，ABI 允许回退 sidecar：把标注 IR 写到对象旁的 `<对象>.label.json`，**与对象摘要绑定**。
`nf-label-sidecar/1` 的 `embedded` **恒为 false**（常量，不是参数）——它证明「这份声明与这份对象对得上」，
不证明「对象里真的带标识」。

```bash
nf label write --object 产出/海报.png --ir 产出/海报.label.json   # 写旁车（绑定摘要）
nf label read 产出/海报.png                                      # 读旁车 + 对账
nf label list                                                    # 清点仓内全部旁车
```

| 检查 | 不过 |
|---|---|
| 旁车在场且 schema == `nf-label-sidecar/1` | invalid |
| 旁车内 IR 通过 `nf-label/1` 校验 | invalid |
| **对象摘要 == 旁车绑定摘要** | invalid（「对象已被改动，标签声明已过期」） |
| 对象可读（被删/权限不足） | invalid |

写盘走 `atomic_write`：半截旁车会让读者读到假声明。读判据只读旁车 + 对象摘要，不联网、不猜。


## 载体（v0 已实装：PNG / JPEG / WebP / MP4 / PDF + PNG 水印）

`nf label embed` 按 magic 选载体，`--mode` 选写入面：

| 格式 | 写入面 | 载体机制 | 承诺 |
|---|---|---|---|
| PNG | `--mode text`（缺省） | `iTXt` 块（keyword = `AIGC`，UTF-8） | 读回 + **不改像素** + 结构合法 |
| PNG | `--mode watermark` | 像素最低位帧（24×24 块冗余 × 多数表决） | 读回 + **删掉文本块仍在** + 扛裁剪/重存；**不**扛 JPEG/缩放 |
| JPEG | `text` | `APP15` 段（`AIGC\0` + JSON） | 读回 + 扫描数据原样 + 段结构合法 |
| WebP | `text` | RIFF 尾部私有块 `NFLA`（同步 RIFF 长度） | 读回 + 媒体块逐字节不变 + 解码器可开 |
| MP4 | `text` | 顶层 `free` 盒（尾部追加） | 读回 + 原始盒逐字节保留 |
| PDF | `text` | `%%EOF` 后注释行（base64） | 读回 + 原文件前缀逐字节保留 |

**WebP/MP4/PDF 的承诺比图片弱**：不是写元数据，而是**在容器尾部追加可忽略块**——旧解码器照样能开，
要删也只要截掉尾部。这三条都只证明「可读回 + 媒体字节没被碰」，不证明「别人删不掉」。

```bash
nf label embed --object 产出/海报.png  --ir 产出/海报.label.json            # 文本块（不改像素）
nf label embed --object 产出/海报.png  --ir 产出/海报.label.json \
            --mode watermark --out 产出/海报.wm.png                      # 像素水印（删块仍在）
nf label embed --object 产出/片段.mp4  --ir 产出/片段.label.json            # MP4 free 盒
nf label embed --object 产出/报告.pdf  --ir 产出/报告.label.json            # PDF 尾部注释
nf label extract 产出/海报.wm.png                                          # auto：先文本块，再水印
```

**水印的边界（实测，2026-11-08）**：低位水印扛得住裁剪、无损重存；**扛不住** JPEG 重编码 / 缩放 /
拍屏，且**零余量**——连 σ=1 高斯噪声、亮度 ×1.05 都会读不回。这不是实现没调好，是 LSB 的物理边界：
有损变换改的就是最低位。完整攻击矩阵（16 条）与 BER 见 `results/ccos/watermark_bench.json`，
复跑：`python scripts/watermark_bench.py --write|--check`，判据 `test_watermark_bench.py`（10 项）：

| 攻击 | 读回 | BER | payload 一致 |
|---|---|---|---|
| 无损重存（PNG） | ✓ | 0.0000 | ✓ |
| 裁剪 10%（中心） | ✓ | 0.0000 | ✓ |
| 裁剪 25%（中心） | ✓ | 0.0000 | ✓ |
| 裁剪 50%（中心） | ✓ | 0.0000 | ✓ |
| 缩放 0.5× | ✗ | — | ✗ |
| 缩放 0.75× | ✗ | — | ✗ |
| 放大 1.5× | ✗ | — | ✗ |
| 放大 2× | ✗ | — | ✗ |
| JPEG q=95 重编码 | ✗ | — | ✗ |
| JPEG q=85 重编码 | ✗ | — | ✗ |
| JPEG q=70 重编码 | ✗ | — | ✗ |
| JPEG q=50 重编码 | ✗ | — | ✗ |
| 高斯噪声 σ=1 | ✗ | — | ✗ |
| 高斯噪声 σ=3 | ✗ | — | ✗ |
| 亮度 ×1.05 | ✗ | — | ✗ |
| 模拟拍屏（0.9× + blur + q=80） | ✗ | — | ✗ |


**v1 设计结论（DCT 探针实测，2026-11-08）**：LSB 换成频域后要分两步走——

- **绝对量化 QIM**（中频系数按步长量化）：PSNR 41.2 dB，扛 JPEG q=95/85 与 σ=1 噪声，
  **不扛 q≤70**（BER≈0.49，系统性失效：固定步长与 JPEG 量化表对不上）；
- **关系嵌入**（比较两系数幅值大小）：PSNR 34.9 dB，**扛 q=95/85/70/50 与 σ=1**（BER=0），
  代价是可见性下降 6 dB——鲁棒性来自**相对关系**而非绝对量化，与论文里 SVD 奇异值稳定的思路一致；
- 两条机制**都不扛几何攻击**（缩放/拍屏 BER≈0.44–0.51）：说明下一阶段必须加**同步层**（模板/SIFT），
  继续调嵌入参数是无解的。

完整数据：`results/ccos/watermark_dct_probe.json`（复跑 `python scripts/watermark_dct_probe.py --write|--check`，
判据 `test_watermark_dct_probe.py` 7 项把「哪些扛、哪些必扛不住、代价多少」都锁住）。

**同步层探针结论（2026-11-08，负结果但可复算）**：给关系嵌入加「同步字平铺 + 缩放/偏移网格搜索」，
给足网格（缩放 5% 步、偏移 16 px）：

- 干净图 ✓（128/128）、JPEG q=70 ✓（127/128，JPEG 不破坏块网格）、整数比放大 1.25× ✓（128/128）；
- **非整数重采样（0.85/0.9/1.1×）、裁剪 10%、模拟拍屏全部对不齐**（对齐分封顶 81–88/128 ≈ 64–69%）。

这说明**固定 8×8 块网格同步不够**，不是搜索分辨率的问题：重采样后块边界不再落在 8 像素栅格上，
任何网格对齐都收不回来。v1 同步层必须走**内容同步**（SIFT/特征点）或**频谱模板**（周期峰检测）。
数据：`results/ccos/watermark_sync_probe.json`，判据 `test_watermark_sync_probe.py` 7 项。

**几何提示同步结论（2026-11-08，正+负结果）**：

- **负结果（数学）**：周期模板的谱峰位置 = 每图周期数，对缩放**不变**——加 16/13 px 周期模板后，
  0.85/1.1/1.25× 缩放后峰仍在同一 bin（`template_invariance.peaks_moved=false`）。
  所以「频谱模板估缩放」这条路不成立，别再当待实现项。
- **正结果（工程）**：标签里记录**原始尺寸**即可反解缩放；再叠「缩放/裁剪双假设 + 块偏移搜索」，
  0.85/0.9/0.95/1.1/1.25× 缩放、裁剪 10%、JPEG q=70 **全部读回 payload**（缩放估计误差 <0.01）；
  代价：PSNR 32.8 dB，且**依赖元数据存在**（元数据被剥时就退回水印单独扛）。
- **剩余边界**：模拟拍屏（0.9× + blur + q80）仍读不回——模糊破坏系数关系，需更强 delta 或纠错。

数据：`results/ccos/watermark_geometry_probe.json`，判据 `test_watermark_geometry_probe.py` 8 项（含负结果锁死）。
水印帧只带 IR 的摘要帧（版本/标准/对象摘要前缀/条目名/条数），不是整份 IR。

## 与 `cc_label` 的关系

`nf label embed` 按 magic 选载体：**PNG → `iTXt` 块**（keyword = `AIGC`，UTF-8）、
**JPEG → `APP15` 段**（`AIGC\0` + JSON）。`nf label extract` 读回。纯标准库实现，
**只承诺三件能自证的事**：

| 承诺 | 判据 |
|---|---|
| 写进去能读回（同 IR、JSON 语义等价） | `nf label extract` 返回同档位/同声明项 |
| **不改像素** | PNG：所有 IDAT 块拼接后 sha256 一致；JPEG：SOS 到 EOF 的原始字节 sha256 一致 |
| 写后仍是结构合法的文件 | PNG：每块 CRC + 签名 + IHDR 首 / IEND 尾；JPEG：段边界/长度合法、SOI 起、含 SOS |

```bash
nf label embed --object 产出/海报.png  --ir 产出/海报.label.json   # 缺省落 海报.png.labeled.png，不改输入
nf label embed --object 产出/照片.jpg  --ir 产出/照片.label.json   # JPEG 走 APP15，扫描数据原样保留
nf label extract 产出/海报.png.labeled.png
```

**边界**：这是**可见文本载体**（任何人都能剥掉 iTXt 块或 APP15 段），不是水印——抗裁剪/抗转码/
抗截屏都不承诺；MP4/PDF/WebP 等格式没有实测，一律走 `nf label write` 的 sidecar 回退，不宣称已嵌入。
真仓图标（多 IDAT / 辅助块）与真 JPEG 的往返各有判据；JPEG 另有一条「Pillow 在场时解码后像素一致」的
附加判据（环境无 Pillow 则跳过，不冒充已验）。

## 与 `cc_label` 的关系

`cc_label(obj, contract)` 要返回 `{label: {contract, standard, fields, carrier, embedded}}`。v0 做实两块：
**声明层**（IR 形状与齐备度）+ **sidecar 回退**（把声明落到对象旁并与摘要绑定）；`embedded` **恒为
false**，无法证「对象里真的带标识」。因此 ABI 里 `cc_label` 记为 `partial`，不升级为 `implemented`。

## 复核

```bash
python -m unittest desktop.tests.test_label_ir   # 16 项：档位/形状/自称提示/CLI 往返
```
