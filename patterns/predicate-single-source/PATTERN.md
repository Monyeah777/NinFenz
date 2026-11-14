---
id: predicate-single-source
name: 扫描面收敛：一条判据只准有一处实现
status: active
scope:
  - 代码层
applies_to:
  - desktop/src/core/repo_face.py
  - desktop/src/core/text_hygiene.py
  - desktop/src/core/asset_ledger.py
  - desktop/src/core/conformance_scan.py
rules:
  - 「什么算仓库里的一件」这类谓词只准有一处实现（`core/repo_face.py`）；消费方一律导入，不得各自维护目录白名单或裸 `os.walk(root)`
  - 根级遍历必须走该谓词——被 `.gitignore` 覆盖的生成副本（如 npm 暂存面）由此统一排除，不再被读成「第二份事实」
  - 收敛要有判据兜住：登记「仓库根级扫描面」清单，断言每处都引用单一实现；清单**只许缩小**，新增面须先接进来
evidence:
  - desktop/src/core/repo_face.py
  - desktop/tests/test_repo_face.py
  - check12
  - check23
---

## 为什么

同一条谓词在多个模块各写一遍，必然漂移：有的模块写死目录白名单、有的裸 `os.walk(root)`、有的
只看 `Path.glob`。**平时看不出来**，直到仓库里出现「生成副本」——副本与真件同构、只是落在被忽略的
路径下。此时每一处自实现的谓词都会把副本当成真件读进来，症状是「数字翻倍 / 同一件列两遍 / 文本面
凭空报红」，而**没有任何一条判据会告诉你是谓词不一致**。

实测（2026-10-03）：npm 暂存面（`packaging/npm/payload/`，gitignored 的生成副本）在场时，
`asset_ledger` 的三处根遍历各写一份排除逻辑 ⇒ `verify_root` 报「台账 206 / 托管资产 614」，而真实值
恰为一半（**103 / 307**），`nf asset inventory` 每件列两遍；同一时期 7 个「文本面」扫描器也各自
维护排除表，check12 连带出假红。收敛到单一谓词后，两者同时归零。

## 怎么用

```bash
python -c "import sys;sys.path.insert(0,'desktop/src');from core import repo_face as rf;print(rf.walk_repo_paths('.'))"
python scripts/nf.py asset inventory        # 单一谓词生效后每件只出现一次
cd desktop && python -m unittest tests.test_repo_face -q   # 扫描面清单：只许缩小
```

代码形态：谓词住在**叶子模块**（不 import 任何 core 兄弟）；消费方 `from core import repo_face`，
把自己的目录白名单删掉。判据侧用「面清单 + 只许缩小」把收敛锁住，而不是靠人工记得。

## 反例

在自己的扫描器里写 `for base, dirs, files in os.walk(root): dirs[:] = [d for d in dirs if d not in {'.git', '.rivet', '__pycache__'}]`
——看着很严谨，实际漏掉 `.gitignore` 覆盖面；生成副本一出现就开始污染统计与门禁。

另一个反例是「只改一处」：修了 `text_hygiene` 却留着 `asset_ledger`，于是同一份仓库在两条门禁里
报出两套数字，谁对谁错只能靠人工比对。

## 相关

- 与 `single-source-truth` 的区别：那条管**数据**（真源 + 投影 + 重算断言）；这条管**谓词/行为**——
  同一判据不得有多份实现，且实现要能自证「哪些面在用它」。
- 与 `dependency-direction` 的关系：谓词放叶子模块，天然不会给被依赖方添加反向依赖；收敛扫描面时
  顺手就避开了 SDP 违例。


---

## 现状对照（2026-11-14 · 以 `repo_face` / 消费方 / 判据实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| 谓词载体 | `desktop/src/core/repo_face.py` 的 `walk_repo_paths(root)`（叶子模块，不 import core 兄弟） | 该文件 |
| 消费方 | **3 处**显式导入：`asset_ledger` / `role_model` / `text_hygiene`（+ 判据件 `test_repo_face`） | `grep 'from core import repo_face'` |
| 判据 | `desktop/tests/test_repo_face.py` **12 例**（含「生成副本不进扫描面」断言） | `python -m pytest desktop/tests/test_repo_face.py` |
| 扫描面规模 | 当前 `walk_repo_paths('.')` 返回 **4436** 条（**以实读为准，本文不钉**） | 一行 Python 实跑 |
| 门禁接线 | **check12**（unittest 全量含 `test_repo_face`）· **check23**（资产供应链闭合） | `verify.sh` 定义 + 权重表 |
| 资产对账 | `nf asset inventory` 每件只列一次（无重复计数） | 命令实跑 |

- **历史数值是留痕不是当前值**：正文「实测（2026-10-03）」的「台账 206 / 托管 614 → 真实值 103 / 307」记录的是**当时**副本污染后的对照，**当前值以命令实读为准**。
- 「清单只许缩小」是本规则的可检面：新增扫描面必须先接入单一谓词，再登记——**不许**在新模块里再写一份目录白名单。

## 复现与引用口径

```bash
python -m pytest desktop/tests/test_repo_face.py -q      # 12 例（含生成副本排除断言）
python scripts/nf.py asset inventory                    # 单一谓词下每件只出现一次
python -c "import sys;sys.path.insert(0,'desktop/src');from core import repo_face as rf;print(len(list(rf.walk_repo_paths('.'))))"
```

- 引用本 pattern 时：「一条判据只准有一处实现」是机制断言；**扫描面条数/资产台账数不钉**。
- 复核口径：`grep -rn 'from core import repo_face' desktop/src/core` 看消费方是否都走单一谓词。
