type: fix
surface: ccos
note: 全量档 check12 修复波——分片实测暴露的 8 项失败清零：新 --json 面登记去向（check/resolve/evidence verify/replay）、bench 的 --json 输出改纯 JSON 且不吐机器绝对路径、证据模块读取统一走 core.json_doc（未校验读点回到基线 1）、静默跳过逐站点补理由、Rust 快线回执去重与 Python 真源同步（重编 nf-rs 后逐字节对账恢复）、新增 4 个测试模块的 check12 权重增量实测（--write-weights 合并，预算棘轮复位）；另确认此前「check12 挂死」为误判：实测分片 0/8 全程 224 s 正常完成，全量档在本机约 40 分钟（参考机基线 1265 s）
