"""HDR JPEG with an ISO 21496-1 gain map (the format of the studio's HDR JPEG export).

    write(sdr_u8, log2_gain, icc) -> bytes

The primary image is the ordinary SDR rendition, so every viewer shows it; an
HDR-capable display (WebKit on macOS, Chromium/WebView2 on Windows, Photos,
Preview, ...) applies the gain map on top:

    HDR = SDR x 2^(log2_gain x weight)        (linear light, SDR white = 1)

where weight runs from 0 to 1 as the display's headroom grows to the map's.
The gain is luminance-only (one channel), applied in the base colour space.

Metadata is written the three ways readers look for it: ISO 21496-1 binary
in the gain map (Apple ImageIO), Adobe `hdrgm` XMP (Chromium / Ultra HDR,
Adobe), and an MPF index plus a GContainer directory locating the second image.
"""
from __future__ import annotations
import io
import struct

import numpy as np

ISO_NS = b"urn:iso:std:iso:ts:21496:-1\0"
DEN = 1_000_000


def _segment(marker: int, payload: bytes) -> bytes:
    if len(payload) + 2 > 0xFFFF:
        raise ValueError("JPEG segment too large")
    return struct.pack(">BBH", 0xFF, marker, len(payload) + 2) + payload


def _iso_metadata(gmin, gmax, headroom, offset):
    """ISO 21496-1 binary metadata: one channel, gain in the base colour space."""
    frac = lambda v: (int(round(v * DEN)), DEN)
    out = struct.pack(">HHB", 0, 0, 0x40)                     # versions, flags: use base colour space
    out += struct.pack(">IIII", 0, 1, *frac(headroom))        # base / alternate HDR headroom (log2)
    out += struct.pack(">iI", *frac(gmin)) + struct.pack(">iI", *frac(gmax))
    out += struct.pack(">II", 1, 1)                           # gamma 1
    out += struct.pack(">iI", *frac(offset)) * 2              # base / alternate offset
    return out


def _xmp_gainmap(gmin, gmax, headroom, offset) -> bytes:
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" hdrgm:Version="1.0" '
        f'hdrgm:GainMapMin="{gmin:.6f}" hdrgm:GainMapMax="{gmax:.6f}" hdrgm:Gamma="1" '
        f'hdrgm:OffsetSDR="{offset:.6f}" hdrgm:OffsetHDR="{offset:.6f}" '
        f'hdrgm:HDRCapacityMin="0" hdrgm:HDRCapacityMax="{headroom:.6f}" hdrgm:BaseRenditionIsHDR="False"/>'
        '</rdf:RDF></x:xmpmeta>').encode()


def _xmp_primary(gainmap_length: int) -> bytes:
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description xmlns:Container="http://ns.google.com/photos/1.0/container/" '
        'xmlns:Item="http://ns.google.com/photos/1.0/container/item/" '
        'xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" hdrgm:Version="1.0">'
        '<Container:Directory><rdf:Seq>'
        '<rdf:li rdf:parseType="Resource"><Container:Item Item:Semantic="Primary" Item:Mime="image/jpeg"/></rdf:li>'
        '<rdf:li rdf:parseType="Resource"><Container:Item Item:Semantic="GainMap" Item:Mime="image/jpeg" '
        f'Item:Length="{gainmap_length}"/></rdf:li>'
        '</rdf:Seq></Container:Directory></rdf:Description></rdf:RDF></x:xmpmeta>').encode()


def _mpf(primary_size: int, gainmap_size: int, gainmap_offset: int) -> bytes:
    """CIPA DC-007 MP index: two images, offsets relative to this header."""
    entries_at = 8 + 2 + 3 * 12 + 4
    ifd = struct.pack(">H", 3)
    ifd += struct.pack(">HHI4s", 0xB000, 7, 4, b"0100")                 # MPFVersion
    ifd += struct.pack(">HHII", 0xB001, 4, 1, 2)                         # NumberOfImages
    ifd += struct.pack(">HHII", 0xB002, 7, 32, entries_at)               # MPEntry
    ifd += struct.pack(">I", 0)
    entries = struct.pack(">IIIHH", 0x030000, primary_size, 0, 0, 0)    # baseline primary image
    entries += struct.pack(">IIIHH", 0, gainmap_size, gainmap_offset, 0, 0)
    return b"MPF\0" + b"MM\0*" + struct.pack(">I", 8) + ifd + entries


def write(sdr_u8: np.ndarray, log2_gain: np.ndarray, icc: bytes | None = None,
          quality: int = 90, gainmap_quality: int = 85, offset: float = 0.0) -> bytes:
    """sdr_u8: HxWx3 uint8 SDR code values; log2_gain: HxW stops over SDR (>= 0 boosts)."""
    from PIL import Image
    g = np.asarray(log2_gain, dtype=np.float64)
    gmin, gmax = float(g.min()), float(g.max())
    if gmax - gmin < 1e-4:                       # flat gain: keep a valid, non-degenerate range
        gmax = gmin + 1e-4
    headroom = max(gmax, 1e-4)
    gm_code = np.round(np.clip((g - gmin) / (gmax - gmin), 0, 1) * 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(gm_code, "L").save(buf, "JPEG", quality=gainmap_quality)
    gm = buf.getvalue()
    gm = (gm[:2] + _segment(0xE1, b"http://ns.adobe.com/xap/1.0/\0" + _xmp_gainmap(gmin, gmax, headroom, offset))
          + _segment(0xE2, ISO_NS + _iso_metadata(gmin, gmax, headroom, offset)) + gm[2:])

    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(sdr_u8), "RGB").save(buf, "JPEG", quality=quality, icc_profile=icc)
    base = buf.getvalue()
    xmp = _segment(0xE1, b"http://ns.adobe.com/xap/1.0/\0" + _xmp_primary(len(gm)))
    iso = _segment(0xE2, ISO_NS + struct.pack(">HH", 0, 0))           # version-only block in the primary
    head = base[:2] + xmp + iso
    mpf_header_at = len(head) + 4 + 4                                  # marker + length, then "MPF\0"
    mpf_len = len(_segment(0xE2, _mpf(0, 0, 0)))
    primary_size = len(head) + mpf_len + len(base) - 2
    mpf = _segment(0xE2, _mpf(primary_size, len(gm), primary_size - mpf_header_at))
    primary = head + mpf + base[2:]
    assert len(primary) == primary_size
    return primary + gm
