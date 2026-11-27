# SBOM 生成说明（audit/tools）

> 状态：**离线未接入**。仓库已有本仓自有 SBOM 证据 results/ccos/sbom.json（610 个材料 + digest 锚，
> 由 scripts/sbom.py 生成），但标准 CycloneDX/SPDX 供应商 SBOM 需要联网解析依赖元数据，
> 离线环境无法完成，因此 K-014（cyclonedx）记为 not-run，禁止写成通过。

## 1. 本仓现有证据

- 自产证据：results/ccos/sbom.json（material 清单 + digest，脚本 scripts/sbom.py）。
- 第三方声明：THIRD-PARTY-NOTICES.md（由 scripts/gen_third_party_notices.py 从 PyPI 元数据生成）。
- 规则对应：K-003（SBOM 产物/生成器，script 已通过）、K-004（第三方声明覆盖，script 已通过）、
  K-014（cyclonedx，tool not-run）。

## 2. CI 生成命令（联网环境）

    # Python 依赖（需 pip 安装 cyclonedx-bom）
    cyclonedx-py requirements .github/requirements-ci.txt --output-file build/sbom-python.cdx.json

    # Rust 依赖（需 cargo-cyclonedx）
    cargo cyclonedx --manifest-path engine/rust/Cargo.toml --format json

    # .NET 依赖（需 CycloneDX .NET 工具）
    dotnet CycloneDX engine/dotnet/Nf.Engine.csproj -o build/sbom-dotnet.json

    # npm 包（包装层无运行时依赖，生成以证明供应链面为空）
    npx @cyclonedx/cyclonedx-npm --output-file build/sbom-npm.cdx.json

## 3. CI 落盘与校验

1. SBOM 写入 results/ci/sbom/，按 commit 命名单文件；
2. 校验 cdx 版本、组件数量与 requirements/Cargo.lock 数量一致（差值为 FAIL）；
3. 把校验结果与文件摘要回填 audit/evidence/<commit>/meta.json 附加段；
4. 只有 CI 证据落盘后，K-014 才可从 not-run 改为实际执行。
