#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""env_check.py — 检查当前 Python 是否具备数据准备所需依赖（numpy/scipy/pandas/networkx/torch）。"""
import importlib
import sys

print(f"executable={sys.executable}  version={sys.version.split()[0]}")
for m in ("numpy", "scipy", "pandas", "networkx", "torch"):
    try:
        mod = importlib.import_module(m)
        print(f"  {m}: OK  {getattr(mod, '__version__', '?')}")
    except Exception as e:  # noqa: BLE001
        print(f"  {m}: MISSING ({type(e).__name__})")
