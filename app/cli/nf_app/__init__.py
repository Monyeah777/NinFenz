"""NF APP Python 控制面（nf_app）。

用户流入口：import / map / project / author / assemble / validate / export /
share / pack / ccos / selftest。内部统一经 subprocess 调 Rust 参考实现
nf-app-core（app/core/target/release/nf-app-core[.exe]，可用 NF_APP_CORE 覆盖）。

纪律：
- 不复制仓库内容真源；只按 ID+digest 引用。
- 错误码只从 app/schema/error_codes.json 取，不散落字面量。
- 产物确定性：禁时间戳/随机/绝对路径（history[].at 与本地备份指针是显式例外）。
"""

__version__ = "0.1.0"
APP_VERSION = __version__
