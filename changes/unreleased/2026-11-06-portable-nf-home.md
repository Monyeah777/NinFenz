type: fix
surface: ccos
note: 机器面路径可移植性补 NF_HOME 前缀（修 --snapshot 模式假红）。`_portable_path` 原来只把「用户家目录 → ~」「仓库根 → .」折叠；当 NF home 被 NARRATIVE_FORGE_HOME 指到仓库树外（--snapshot 给内层独立 home 正是这种）时，daemon status 的 state_file 与 preset 的 home 会原样回吐本机绝对路径，test_cli_json_face 的 portable 判据在快照里假红。现在第三前缀把 NF home 折叠成 `<NF_HOME>`（仍在 ROOT 之后的检查顺序，避免把仓库内 home 误标）。判据：test_cli_json_face 14 项 OK（主树）；手工验：NARRATIVE_FORGE_HOME=D:/tmp-home 时 state_file=`<NF_HOME>/daemon.json`、preset home=`<NF_HOME>/presets`；style 9921=基线；code_metrics 小幅重冻。
