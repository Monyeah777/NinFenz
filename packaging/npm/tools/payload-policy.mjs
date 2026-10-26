// 发布面策略（唯一真源）：stage-payload（生成）与 verify-package（自检）**同一份**列表，
// 避免"生成端改了白名单、自检端还按旧表断言"这类两处漂移。
//
// 语义（N2/L2，2026-10-25 安全审计收口）：
//   · **顶层目录默认拒绝**：不在 ALLOW_DIRS 里的一律不进包——黑名单"默认保留"是 `changes/`
//     漏进包（M1）与 `changes/2.12.0/` 同族（L2）的根因；
//   · 顶层**文件**全收（扁平面、逐件可 review），仅拒 EXCLUDE_FILES；
//   · 白名单内部仍需排除的子面见 EXCLUDE_DIRS（专有夹具等）。
export const ALLOW_DIRS = [
  // 运行时必需
  'desktop/', 'scripts/', 'tui/', 'site/', 'integrations/', 'skills/',
  // 协议与内容真源（`nf` 运行时要读）
  'protocol/', 'library/', 'community/', 'decisions/', 'handovers/', 'postmortems/', 'patterns/',
  '03_管线库/', '04_模块库/', '05_资产库/',
  // 文档与许可面
  'docs/', 'LICENSES/',
];

//: 白名单内部的子面排除。**desktop/tests/ 必须排除**（2026-10-10 全仓审计 X1，P1）：该目录
//: 装着第三方夹具（`fixtures/external/anthropic-official/*.SKILL.md`），其中 `docx.SKILL.md`
//: 自述 `license: Proprietary` —— 发布物内含专有内容（CWE-1104）。其余项是白名单化之前的历史
//: 兜底（现在多数已由"默认拒绝"覆盖，保留作纵深）。
export const EXCLUDE_DIRS = ['engine/', 'results/', '.github/', '.gitee/', 'packaging/', '.git/',
                             'desktop/tests/', 'changes/'];
export const EXCLUDE_ANY = ['__pycache__/', '.pyc', 'tui/dist/', '.DS_Store'];

//: **内部治理内容**（决策记录 / 接力 / 复盘）：不进发布物。
//: 依据 STRATEGY §四「计划类文档不发布公开仓库」「结果状态才入库」——决策意图、交接上下文、
//: 复盘的归因过程属于内部材料，随 npm 分发给终端用户等于把作者的判断过程公开（意图暴露）。
//: 运行时**目录本身**仍可由 `nf decisions/handover/postmortem` 按需创建；这里只拒绝既有内容。
export const INTERNAL_DIRS = ['decisions/', 'handovers/', 'postmortems/', 'changes/'];
export const INTERNAL_ROOT_FILES = ['CI-RED-TRIAGE.md'];
//: 单件排除（脚手架残留，2026-10-10 审计 P2-14）：仓库根 `trace.json` 是 `nf assemble --trace`
//: 留下的 404 B 占位件（phase=clarify / requirement="需求"），不是运行时依赖，不该进发布物。
export const EXCLUDE_FILES = ['trace.json', 'setup.py'];
