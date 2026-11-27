#!/usr/bin/env python3
"""Android 单测启动：把 SDK 的 framework res 打成 layoutlib-resources jar 放入 mavenLocal。
本机 Gradle 缺该 artifact；空 jar 只能跑非渲染测试，真实 res 才能跑 Paparazzi。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

M2 = Path.home() / ".m2" / "repository" / "com" / "android" / "tools" / "layoutlib" / "layoutlib-resources" / "15.2.3"
POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>com.android.tools.layoutlib</groupId><artifactId>layoutlib-resources</artifactId><version>15.2.3</version>
<name>Layoutlib resources</name></project>
"""


def sdk_res() -> Path | None:
    # 不内置本机绝对路径：必须由 ANDROID_HOME 指定，未设置时退回空 res jar。
    raw = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not raw:
        return None
    home = Path(raw)
    candidates = sorted((home / "platforms").glob("android-*/data/res"))
    return candidates[-1] if candidates else None


def main() -> int:
    M2.mkdir(parents=True, exist_ok=True)
    jar = M2 / "layoutlib-resources-15.2.3.jar"
    res = sdk_res()
    with tempfile.TemporaryDirectory() as td:
        if res is not None:
            shutil.copytree(res, Path(td) / "res")
            (Path(td) / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="android"/>\n',
                encoding="utf-8",
            )
            subprocess.run(["jar", "cf", str(jar), "res", "AndroidManifest.xml"], check=True, cwd=td)
        else:
            man = Path(td) / "MANIFEST.MF"
            man.write_text("Manifest-Version: 1.0\n", encoding="utf-8")
            subprocess.run(["jar", "cfm", str(jar), str(man)], check=True, cwd=td)
    (M2 / "layoutlib-resources-15.2.3.pom").write_text(POM, encoding="utf-8")
    print(jar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
