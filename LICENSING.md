# LICENSING · 分层许可与双授权

> **免责声明：本文件不构成法律意见。商业授权需双方签署正式的商业合同。
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.**
> 本文件只描述**许可边界**；AGPL 的具体含义一律以 GNU 官方文本与官方 FAQ 为准（下文逐条给出原文与链接）。

历史事实：v1.0.5 及更早版本按 MIT 发布，**MIT 授权不可撤销**——任何已获得 MIT 副本的人，对那个版本永久
享有 MIT 权利。切换到 AGPL 只对**新版本**生效。

## 1. 四层边界

| 层 | 范围 | 许可 |
|---|---|---|
| **引擎/CLI/门禁** | `desktop/`、`scripts/`、`engine/`、`tui/`、`verify.sh`、`packaging/` | **AGPL-3.0-only** 或 商业许可（二选一） |
| **协议规范文本** | `01_核心协议.md`、`02_联动注册表.md`、`03_管线库/`、`04_模块库/`、`05_资产库/`、`06_Agent执行协议.md`、`07_*.md`、`protocol/` 机读件、`docs/` | **CC BY 4.0**（署名即可实现与引用） |
| **社区投稿** | `library/NF-*.md`、`library/anchors/`、`community/` | **LicenseRef-Community-Submission**（版权归投稿人） |
| **历史版本** | ≤ v1.0.5 全部内容 | **MIT** |

不在上表明确列举的目录，按 AGPL-3.0-only 处理（默认从紧）。

## 2. 双授权怎么二选一

- **开源 / 内部 / 研究**：直接用 AGPL-3.0-only；
- **商业闭源集成、SaaS 套壳、或不愿承担 copyleft 义务**：购买**商业许可**（见 `COMMERCIAL.md`），
  商业许可在授权范围内**替代** AGPL 适用于该被授权方。

## 3. AGPL 的含义：直接引用 GNU 官方 FAQ（不自造解释）

以下均为 **GNU 官方 FAQ 原文**（英文照抄，中文仅作阅读辅助），出处：
<https://www.gnu.org/licenses/gpl-faq.html>

### 3.1 组织内部使用算不算"分发"？

**Q（原文）**：*Is making and using multiple copies within one organization or company "distribution"?*

**A（原文）**：*No, in that case the organization is just making the copies for itself. As a consequence, a company or
other organization can develop a modified version and install that version through its own facilities, without giving
the staff permission to release that modified version to outsiders. However, when the organization transfers copies to
other organizations or individuals, that is distribution. In particular, providing copies to contractors for use
off-site is distribution.*

（出处锚点：#InternalDistribution）

### 3.2 只在公司内网跑改过的版本，要不要公开源码？

**Q（原文）**：*A company is running a modified version of a GPLed program on a web site. Does the GPL say they must
release their modified sources?*

**A（原文）**：*The GPL permits anyone to make a modified version and use it without ever distributing it to others.
What this company is doing is a special case of that. Therefore, the company does not have to release the modified
sources. The situation is different when the modified program is licensed under the terms of the GNU Affero GPL.*

（出处锚点：#UnreleasedMods）

### 3.3 什么算"通过网络远程与软件交互"（AGPL §13 的触发面）？

**Q（原文）**：*In AGPLv3, what counts as "interacting with [the software] remotely through a computer network?"*

**A（原文）**：*If the program is expressly designed to accept user requests and send responses over a network, then it
meets these criteria. Common examples of programs that would fall into this category include web and mail servers,
interactive web-based applications, and servers for games that are played online. If a program is not expressly designed
to interact with a user through a network, but is being run in an environment where it happens to do so, then it does
not fall into this category. For example, an application is not required to provide source merely because the user is
running it over SSH, or a remote X session.*

（出处锚点：#AGPLv3InteractingRemotely）

### 3.4 "corresponding source" 要提供到哪一步？

**Q（原文）**：*Under AGPLv3, when I modify the Program under section 13, what Corresponding Source does it have to
offer?*

**A（原文，节选）**：*"Corresponding Source" is defined in section 1 of the license, and you should provide what it
lists. So, if your modified version depends on libraries under other licenses, such as the Expat license or GPLv3, the
Corresponding Source should include those libraries (unless they are System Libraries).*

（出处锚点：#AGPLv3CorrespondingSource）

### 3.5 AGPLv3 与 GPLv3 能否互相链接？

**Q（原文）**：*In what ways can I link or combine AGPLv3-covered and GPLv3-covered code?*

**A（原文）**：*Each of these licenses explicitly permits linking with code under the other license. You can always link
GPLv3-covered modules with AGPLv3-covered modules, and vice versa. That is true regardless of whether some of the
modules are libraries.*

（出处锚点：#AGPLGPL）

## 4. 附加许可（AGPL §7）

我们按 §7 授予若干 **additional permissions**（只增权利、不减义务），见 `LICENSE-EXCEPTIONS.md`：
产物与数据例外（E1）、内部使用澄清（E2）、CI/评估例外（E3）、聚合与插件边界（E5）、商标与命名（E6）、
生效与终止（E9）。

**注意**：§7 只允许"additional permissions"；任何**额外限制**（例如单方设定的违约金、强制审计权）都不属于 §7
允许的范围，写进许可证也不会生效（AGPL §10 允许被许可人移除 further restrictions）。所以本仓的**费用与结算
条款只出现在 `COMMERCIAL.md`，不进入 AGPL 授权本身**。

## 5. 输出与数据

用 NF **生成**的产物（文档、图纸、装配结果、报告、中间数据）版权归**使用者**所有，不属于 AGPL 的 covered work，
可自由商用与闭源分发（前提：不是把 NF 源码整体复制成另一产品）。详见 `LICENSE-EXCEPTIONS.md` E1。

## 6. 贡献（inbound）：**用标准 CLA，不用 DCO 承载商业授权**

- 贡献者**必须签署 `CLA.md`**（改编自 Harmony Combined Contributor Agreement v1.0 **Option Five**），
  其中 §2.3 明确授权：*"We may license the Contribution under any license, including copyleft, permissive,
  **commercial, or proprietary** licenses"* —— 这是双授权能合法成立的**唯一**授权来源。
- **DCO 不是授权工具**：DCO 仅表示"我有权提交该作品"，其法律效果是把贡献以**项目当前许可**（AGPL）发布，
  **不包含**"允许作者商业闭源转售"的授权。把商业再许可写进 DCO 是无效发明，故本仓不采用该做法。
- 提交时仍建议 `git commit -s`（便于追溯作者与来源），但**签署 CLA 是必要条件**；细节见 `CONTRIBUTING.md §7`。

## 7. 合规速查

| 你的用法 | 需要做什么 |
|---|---|
| 本地跑 `nf` 给自己用 | 不需要做任何事 |
| 改代码但只自己用/不对外发 | 不需要公开（FAQ #UnreleasedMods） |
| 组织内部部署、不对外提供服务 | 不构成 distribution（FAQ #InternalDistribution）；仍受 AGPL 其他条款约束 |
| 分发修改版二进制/源码 | 附 AGPL 全文 + 提供对应源码 + 标注修改 |
| 把修改版做成**网络服务**给他人用 | 须向使用者提供获取对应源码的途径（AGPL §13；触发面见 FAQ #AGPLv3InteractingRemotely） |
| 参考协议文本写自己的实现 | 遵守 CC BY 4.0：署名 + 标注是否修改 |
| 不想承担 copyleft 义务 | 购买商业许可（`COMMERCIAL.md`） |

## 8. 免责与生效

> **本文件不构成法律意见，也不是商业合同。商业授权需双方签署正式合同。
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
> THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.**

正式商用前请由执业律师终审（尤其是 AGPL 与商业许可的兼容表述、跨境销售、以及 CLA 的管辖条款）。
