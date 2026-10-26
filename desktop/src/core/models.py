"""核心数据模型：Module / Pipeline / AssetPack / Preset。

对齐 NinFenz 协议与桌面工具指令集 3.3-3.5 的数据结构。
"""
from __future__ import annotations

import types
import typing
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

# 模块分类（对应 04_模块库 顶层目录 + 桌面工具功能B的筛选）
CATEGORIES = ["情感类", "生存类", "世界类", "事件类", "通用类", "技术文档类"]


def fid_key(fid: str) -> str:
    """把 full_id 归一为协议比较键：类别段去『类』字后比较。

    存储层 category 为长名（情感类），而管线/标题/预设引用为短名（情感:M22），
    二者语义上指同一模块。统一比较键后 get_module / validator 允许集
    均能双向命中（情感:M22 ↔ 情感类:M22）。
    """
    if ":" in fid:
        c, i = fid.split(":", 1)
        return c.rstrip("类") + ":" + i
    return fid

# 九层骨架（P00 通用骨架声明；P01-P03 为叙事实例，层名可替换）
LAYER_IDS = ["P00", "P10", "P20", "P30", "P40", "P50", "P60", "P70", "P80"]


def _type_ok(value, expected) -> bool:
    """轻量类型守卫（Optional/Union + 基础容器）。"""
    if expected is typing.Any:
        return True
    origin = typing.get_origin(expected)
    if origin in (typing.Union, types.UnionType):
        return any(_type_ok(value, arg) for arg in typing.get_args(expected))
    if expected is type(None):
        return value is None
    if expected is bool:
        return isinstance(value, bool)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected in (list, dict, str, float):
        return isinstance(value, expected)
    return True


def _apply_fields(instance, data: dict, cls) -> None:
    """只写声明字段；已知字段类型不符即 fail-loud（未知键向后兼容地忽略）。"""
    if not isinstance(data, dict):
        raise ValueError("%s.from_json 需要对象，实为 %s" % (cls.__name__, type(data).__name__))
    hints = typing.get_type_hints(cls)
    for key, value in data.items():
        if key not in hints:
            continue
        if not _type_ok(value, hints[key]):
            raise ValueError("%s.%s 须为 %s，实为 %s（修复指引：按 module.json/pipeline.json "
                             "的声明类型修正）" % (cls.__name__, key, hints[key],
                                                   type(value).__name__))
        setattr(instance, key, value)



@dataclass
class Module:
    """模块定义（指令集 3.3 module.json）。

    id: 模块数字号，如 M22（情感:M22 带类前缀的写法在 category 字段分离）
    """
    id: str = ""
    name: str = ""
    category: str = "通用类"
    layer: str = "P40"               # 挂载层位 P00-P80
    replaceable: bool = True
    inputs: list = field(default_factory=list)      # 依赖的模块 id 列表
    outputs: list = field(default_factory=list)     # 输出数据键，如 "sexual:int"
    events_publish: list = field(default_factory=list)
    events_subscribe: list = field(default_factory=list)
    assets: list = field(default_factory=list)      # 引用的资产键
    logic: str = ""                   # 核心逻辑（伪代码/规则）
    source_md: str = ""               # 原始 markdown 全文（装配时拼接）
    enabled: bool = True
    installed_at: str = ""
    source_path: str = ""             # 来源件的仓库相对路径（快照信任标注用）

    @property
    def full_id(self) -> str:
        """带类前缀的全名，如 情感:M22（仓库内同名不同类的消歧方式）"""
        if ":" in self.id:
            return self.id
        return f"{self.category}:{self.id}" if self.category else self.id

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Module":
        m = Module()
        _apply_fields(m, d, Module)
        return m

    def __repr__(self) -> str:
        return f"<Module {self.full_id} · {self.name} @{self.layer}>"


@dataclass
class PipelineLayer:
    """管线单层定义"""
    id: str = "P00"                   # 层位 id
    name: str = ""
    description: str = ""
    optional: bool = False
    default_modules: list = field(default_factory=list)
    allowed_modules: list = field(default_factory=list)


@dataclass
class Pipeline:
    """管线定义（对齐 03_管线库 YAML frontmatter）"""
    id: str = "P01"
    name: str = "标准管线"
    description: str = ""
    structure_type: str = "linear"    # linear / 回卷
    layers: list = field(default_factory=list)      # list[PipelineLayer]，按序
    dependencies: list = field(default_factory=list)  # list[dict{from,to,reason}]
    tags: list = field(default_factory=list)

    @property
    def layer_ids(self) -> list:
        return [l.id for l in self.layers]

    def layer(self, lid: str) -> Optional[PipelineLayer]:
        for l in self.layers:
            if l.id == lid:
                return l
        return None

    def to_json(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "structure_type": self.structure_type,
            "layers": [asdict(l) for l in self.layers],
            "dependencies": self.dependencies, "tags": self.tags,
        }

    @staticmethod
    def from_json(d: dict) -> "Pipeline":
        p = Pipeline()
        raw_layers = d.get("layers", [])
        if not isinstance(raw_layers, list):
            raise ValueError("Pipeline.layers 须为 list，实为 %s" % type(raw_layers).__name__)
        _apply_fields(p, {k: v for k, v in d.items() if k != "layers"}, Pipeline)
        p.layers = []
        for item in raw_layers:
            if not isinstance(item, dict):
                raise ValueError("Pipeline.layers 的元素须为对象，实为 %s"
                                 % type(item).__name__)
            layer = PipelineLayer()
            _apply_fields(layer, item, PipelineLayer)
            p.layers.append(layer)
        return p

    def __repr__(self) -> str:
        return f"<Pipeline {self.id} · {self.name} [{len(self.layers)}层]>"


@dataclass
class AssetPack:
    """资产包定义（指令集 3.4 asset.json）"""
    name: str = ""                    # 如 校园包 / 西幻包
    version: str = "1.0.0"
    entries: dict = field(default_factory=dict)  # {资产键: 内容/说明}
    source_dir: str = ""              # 资产文件目录（本地）
    installed_at: str = ""

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "AssetPack":
        a = AssetPack()
        _apply_fields(a, d, AssetPack)
        return a

    def __repr__(self) -> str:
        return f"<AssetPack {self.name} v{self.version} [{len(self.entries)}键]>"


@dataclass
class Preset:
    """预设配置（指令集 3.5 preset.json）"""
    name: str = "未命名预设"
    pipeline: str = "P01"
    modules: list = field(default_factory=list)   # 勾选的模块 full_id 列表
    asset_pack: str = ""
    created_at: str = ""

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Preset":
        p = Preset()
        _apply_fields(p, d, Preset)
        return p

    def __repr__(self) -> str:
        return f"<Preset {self.name} · {self.pipeline} · {len(self.modules)}模块>"


def now_str() -> str:
    return datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005 - 产物墙钟时间戳是有意语义（本地时间，供人读）
