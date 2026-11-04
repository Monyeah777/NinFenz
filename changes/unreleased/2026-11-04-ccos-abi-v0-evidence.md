type: feat
surface: ccos
note: CCOS ABI v0 七个系统调用落地六项（cc_attest / cc_verify / cc_replay / cc_check / cc_resolve / cc_diff，cc_label 挂 unimplemented）+ 证据链三件（三形态复验、25 条攻击矩阵基准、零依赖单文件复验器）+ 一条链复现脚本 + 本地 HTTP 面 v0（nf serve --http：health / verify / check；只绑回环、Origin 白名单、体量上限、无客户端可控路径；判定 invalid 也回 200）+ 本地工作台页 /verify（零构建零外链、CSP 锁死、拖拽即验）+ 协议回执去重修复；本 ABI 新增单测 85 项
