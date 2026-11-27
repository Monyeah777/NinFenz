"""core.lsp 私有实现分片 4/4（对外只经 core.lsp 门面导入）：check、scan"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.lsp_client import CLIENT_EDITORS

from ._part1 import _REQUIRED_CAPS, M_INITIALIZE, path_to_uri
from ._part3 import LspServer, _check_capabilities, _check_intelligence, _check_lifecycle


def check(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """编辑器面机检（check33 子扫描口径）：把「IDE 集成」从布尔升成协议行为判据。

    内部差距实证：旧 check33 第 5 面只断言 'codeActionProvider' 为真，而门禁自述写着
    「编辑器面」——声明与实测不符。本判据真跑一遍协议行为：能力声明齐备 / 诊断带真实
    位置 / didClose 清理 / 未 shutdown 的 exit 退出码 / 领域解析（真仓库件）/ 补全·悬停·
    跳定义·大纲 / 三种编辑器配置可生成。缺根或不可用如实报 issue，不裸崩。
    """
    r = Path(root)
    if not (r / "verify.sh").is_file():
        return (["读不到仓库根（缺 verify.sh）——编辑器面判据须在 NF 仓库根运行"], {})
    srv = LspServer(root=str(r.resolve()), explicit_root=True)
    probe = path_to_uri(str(r / "editor_face_probe.md"))
    # 握手一次（真实客户端序列；后续请求面都依赖它——协议状态机要求先 initialize）
    init = srv.handle({"jsonrpc": "2.0",
 "id": 1,
 "method": M_INITIALIZE,
 "params": {}})[0]["result"]
    issues = _check_capabilities(srv, init)
    issues += _check_lifecycle(srv, probe, str(r.resolve()))
    issues += _check_intelligence(srv, probe, r)
    counts: Dict[str, int] = {}
    for s in srv.symbols().all_symbols():
        counts[s["kind"]] = counts.get(s["kind"], 0) + 1
    return issues, {"capabilities": len(_REQUIRED_CAPS), "clients": len(CLIENT_EDITORS),
                    "modules": counts.get("module", 0), "assets": counts.get("asset", 0),
                    "events": counts.get("event", 0), "layers": counts.get("layer", 0),
                    "pipelines": counts.get("pipeline", 0)}


#: 扫描器统一入口名（与 integrations / repo_stats / release_gate 一致）。
scan = check
