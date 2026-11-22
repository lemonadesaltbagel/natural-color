"""Natural Color — a complete camera colour pipeline.

Architecture (each stage is a pure function, parameters are explicit):

    naturalcolor.io      raw loading, CFA demosaic, image container
    naturalcolor.color   matrices, white balance, colour engine, curves, output profiles
    naturalcolor.model   two looks: camera and studio (+ HDR rendition)
    naturalcolor.calibrate curve / look fitting against a target render
    naturalcolor.cli     command line entry point

Design rules
  * linear-light float64 end to end; clipping only at the output encoder
  * every stage takes and returns plain numpy arrays (decoupled, testable)
  * extracted reference data is read from `out/reference` and `params/*`
"""
__version__ = "2.0"

# A sealed build ships its colour core as authenticated ciphertext; the import
# hook has to be in place before any submodule is imported.  In a normal
# source tree there is no manifest and this is a no-op.
from . import vault as _vault

_vault.install_if_sealed()
