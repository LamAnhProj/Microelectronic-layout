#!/usr/bin/env python3
"""Compatibility entry point matching the reference layout_agent.py convention."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from chip_lab.cli import main

if __name__ == '__main__':
    sys.argv.insert(1, 'bridge')
    main()
