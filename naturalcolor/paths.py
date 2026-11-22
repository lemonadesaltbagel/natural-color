"""Repository-relative data locations (independent of the working directory)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # repo root
DATA = ROOT / "data"
PARAMS = ROOT / "params"
CM_DIR = DATA / "colormaps"
WORKING_SPACE = DATA / "working_space.json"
GRADATION = DATA / "gradation.bin"
GAIN_CURVES = DATA / "gain_curves.json"
BT2020_PQ_ICC = DATA / "bt2020_pq.icc"
BUILD_IQ = ROOT / "build" / "iq.pkl"
COLORMAPS_ENV = "NATURALCOLOR_COLORMAPS"


def colormap_dirs():
    """Colour-profile search path: $NATURALCOLOR_COLORMAPS (os.pathsep separated), then data/colormaps."""
    extra = [Path(p).expanduser() for p in os.environ.get(COLORMAPS_ENV, "").split(os.pathsep) if p]
    return [*extra, CM_DIR]
