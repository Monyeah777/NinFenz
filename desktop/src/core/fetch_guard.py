"""出站取件加固：宿主钉住 + 拒跟重定向（机制借鉴 mcp-server-smartsheet-rm check_openapi_drift.py:447-463）。

NF 的 trust_boundary 只管**入站**参数；出站取件（--fetch / 版本探测）此前无一等判据。
本模块拒绝：非 https、宿主不在白名单、跟重定向、带凭据的 URL。
"""
from __future__ import annotations

from typing import Iterable, List
from urllib.parse import urlparse


def check_url(url: str, allowed_hosts: Iterable[str], allow_redirects: bool = False) -> List[str]:
    """→ issue 列表（空 = 通过）。"""
    issues: List[str] = []
    p = urlparse(url or "")
    if p.scheme != "https":
        issues.append("出站 URL 非 https：%r（修复指引：改 https）" % p.scheme)
    host = (p.hostname or "").lower()
    allowed = {h.lower() for h in allowed_hosts}
    if host not in allowed:
        issues.append("宿主未钉住：%r（修复指引：加入白名单或改用已钉宿主）" % host)
    if p.username or p.password:
        issues.append("URL 内嵌凭据（修复指引：凭据走环境变量，不进 URL）")
    if allow_redirects:
        issues.append("取件允许跟重定向（修复指引：关闭重定向跟随，逐跳校验）")
    return issues
