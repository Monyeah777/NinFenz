# NFA-L 容器分发（零成本）

零第三方 Python 依赖：镜像只装 Python 标准库 + NF 引擎源码；仓库真源用卷挂载，
镜像本身不含内容，因此可离线、可复现。

## 构建

    docker build -f packaging/nfal/Dockerfile -t nfal .      # 上下文必须是仓库根（COPY 为根相对路径）

云端零成本构建：.github/workflows/docker-nfal.yml（push 改动 packaging/nfal 或 nfal 引擎件即 build + 冒烟，不推注册表）。

## 运行

    docker run --rm -v "$PWD":/repo nfal --root /repo build 03_管线库/P01_标准管线.md --no-tokens
    docker run --rm -v "$PWD":/repo nfal --root /repo check "WorldState.time.day >= 30"
    docker run --rm -v "$PWD":/repo nfal --root /repo eval 03_管线库/P01_标准管线.md --state state.json

真源缺 PyYAML 时，管线围栏回退到零依赖子集解析（见 core.nfal._fence_pipeline），
所以镜像无需 pip install 也能读管线。

## 零成本分发面

- 本机：上述 docker run 即用；
- 免费托管：可与既有 packaging/hf-space 同法上 HF Space 免费层，或推 Docker Hub 公开层；
- 模块入口：python -m core.nfal_cli（容器 ENTRYPOINT 即它）。


---

> **复核（2026-11-14）**：零依赖纪律、构建/运行命令与工作流口径**复核不变**；补「§现状对照」把镜像形态、子命令、判据数与「本机无容器引擎」这一现实写清。

## 现状对照（2026-11-14 · 以 Dockerfile / 工作流 / CLI 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 基座 | 单个 `FROM python:3.12-slim@sha256:5e2bdb1b…`（**按 digest 钉死**，tag 漂移不影响可复现） | `Dockerfile` |
| 镜像内容 | 只 `COPY desktop/src`；**仓库真源按卷挂载**（`VOLUME ["/repo"]`），镜像不含内容 | `Dockerfile` |
| 入口 | `ENTRYPOINT ["python","-m","core.nfal_cli"]` + `CMD ["--help"]` | 同上 |
| 依赖 | **零 pip**（无 `RUN pip install`）；缺 PyYAML 时管线围栏回退零依赖子集解析 | `Dockerfile` + `core/nfal.py` |
| 子命令 | **5 个**：`parse` / `check` / `build` / `eval` / `schema-check` | `python -m core.nfal_cli --help` |
| 云端构建面 | `.github/workflows/docker-nfal.yml`：**2 个 job**（`build-nfal-image` 冒烟 `--help`；`build-hf-space` 导入冒烟），push/PR 同路径触发 | 工作流实读 |
| 判据 | `test_nfal` + `test_nfal_cli` + `test_nfal_rules` 共 **44 例**；工作流契约 5 例 | 本地实跑 |
| 本机复现限制 | **本机无 Docker**：镜像构建只在 CI 跑（workflow 实测 13–45 s），本地只做源码级验证 | 环境实读 |

> 本表只作「当时 → 现行」导航；镜像形态以 `Dockerfile` 为准，构建结果以 CI 运行为准。

## 复现与引用口径

```bash
python -m pytest desktop/tests/test_nfal.py desktop/tests/test_nfal_cli.py desktop/tests/test_nfal_rules.py -q   # 44 例
python -m pytest desktop/tests/test_docker_nfal_workflow_contract.py -q                                        # 工作流契约 5 例
cd desktop/src && PYTHONPATH=. python -m core.nfal_cli --help                                                  # 5 子命令
```

```bash
docker build -f packaging/nfal/Dockerfile -t nfal .   # 需容器引擎；本机无则在 CI 里跑
docker run --rm nfal --help                          # 冒烟（与 workflow 同一命令）
```

- 引用本页时：「镜像只装引擎、内容靠卷挂载」= 长期口径；不要写成「镜像自带内容」。
- 本机没有容器引擎时，**不要**声称「镜像已构建成功」——那是 CI 的结论。
