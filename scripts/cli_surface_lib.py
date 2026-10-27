"""CLI 命令面序列化（golden 夹具 `desktop/tests/fixtures/cli_surface.json` 的唯一格式真源）。"""
import argparse

SCHEMA = "nf-cli-surface/1"


def _flags(parser):
    out = []
    for act in parser._actions:
        if isinstance(act, argparse._SubParsersAction):
            continue
        out.append({
            "option": list(act.option_strings),
            "dest": act.dest,
            "nargs": (act.nargs if isinstance(act.nargs, (str, int, type(None)))
                      else str(act.nargs)),
        })
    return out


def _layer(action):
    help_map = {a.dest: a.help for a in getattr(action, "_choices_actions", [])}
    canonical = [a.dest for a in getattr(action, "_choices_actions", [])] or list(action.choices)
    cmds = []
    for name in canonical:
        sp = action.choices[name]
        aliases = sorted(k for k, v in action.choices.items() if v is sp and k != name)
        nested = None
        for act2 in sp._actions:
            if isinstance(act2, argparse._SubParsersAction):
                nested = _layer(act2)
        cmds.append({"name": name, "aliases": aliases, "help": help_map.get(name),
                     "flags": _flags(sp), "nested": nested})
    return cmds


def serialize(root_parser):
    sub = next(a for a in root_parser._actions
               if isinstance(a, argparse._SubParsersAction))
    return {"schema": SCHEMA, "root_flags": _flags(root_parser),
            "commands": _layer(sub)}
