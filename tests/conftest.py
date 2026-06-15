# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration: make the stdlib CLI (scripts/gv.py) importable as `gv`."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
