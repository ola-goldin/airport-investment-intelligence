"""Seed/demo dataset script (network-free; deterministic).

Thin wrapper over scripts/make_seed_data.py (the generator). Exists so the
documented entry points match the README/spec vocabulary:

  - `python scripts/seed_demo_data.py` -> regenerate the bundled demo datasets
  - `python scripts/download_data.py`  -> optional authoritative public download

The seed is clearly labeled `seed_calibrated` in every API response; it is
NOT live BTS data. See make_seed_data.py for the provenance note.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_seed_data import main  # noqa: E402

if __name__ == "__main__":
    main()