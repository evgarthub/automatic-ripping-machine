import os
from pathlib import Path

import arm.config
import arm.ripper
import arm.ui

try:
    __version__ = Path(__file__).resolve().parents[1].joinpath('VERSION').read_text().strip()
except OSError:
    __version__ = 'unknown'
