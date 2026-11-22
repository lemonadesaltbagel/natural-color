"""Repository-relative data locations (independent of the working directory)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # repo root
DATA = ROOT / "data"
PARAMS = ROOT / "params"
GAIN_CURVES = DATA / "gain_curves.json"
BT2020_PQ_ICC = DATA / "bt2020_pq.icc"
