#!/usr/bin/env python3
"""Export pulp and PDL into the CBCT asset tree so the atlas can show them.

Both were modelled and neither was viewable: they existed as STLs in the working
directory and were never added to the manifest. This puts them in the build.

Per tooth, keyed as <FMA>-pulp and <FMA>-pdl so the FMA id stays the join key and
the app can associate each with its tooth. Provenance differs between them and
from the teeth, and the atlas must not present them alike:

  pulp   MEASURED lumen -- intensity-deficit integration
  pdl    MEASURED location, EXAGGERATED thickness -- a 0.2 mm ligament is
         ~1.3 voxels and will not mesh at its true size

Usage: python3 tools/cbct/export_soft.py <pulp-dir> <pdl-dir> <split-dir> <out-dir>
"""
import json
import os
import struct
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from segment_tooth import write_binary_stl
from meshsmooth import taubin, weld
from export_teeth import decimate

TARGET_PULP = 2500
TARGET_PDL = 3000


def load_stl(path):
    b = open(path, "rb").read()
    n = struct.unpack("<I", b[80:84])[0]
    rec = np.frombuffer(b[84:84 + n * 50], dtype=np.uint8).reshape(n, 50)
    return rec[:, 12:48].copy().view("<f4").reshape(n * 3, 3).astype(np.float64)


def process(soup, target, smooth=8):
    verts, faces = weld(soup)
    if len(faces) < 8:
        return None
    verts = taubin(verts, faces, smooth)
    verts, faces = decimate(verts, faces, target)
    return taubin(verts, faces, 3), faces


def main():
    pulp_dir, pdl_dir, split_dir, outdir = sys.argv[1:5]
    os.makedirs(outdir, exist_ok=True)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    teeth = [(t["universal"], t["fma"], a)
             for a in ("upper", "lower") for t in rep[a]["teeth"]]
    made = {"pulp": 0, "pdl": 0}

    for num, fma, arch in sorted(teeth):
        src = os.path.join(pulp_dir, f"{fma}-pulp.stl")
        if os.path.exists(src):
            got = process(load_stl(src), TARGET_PULP)
            if got:
                write_binary_stl(os.path.join(outdir, f"{fma}-pulp.stl"), *got)
                made["pulp"] += 1

    # The PDL is produced per arch, not per tooth. Split it by proximity to each
    # tooth's own pulp centroid so every tooth carries its own ligament and the
    # app can show one without showing all 28.
    for arch in ("upper", "lower"):
        src = os.path.join(pdl_dir, f"pdl-{arch}.stl")
        if not os.path.exists(src):
            continue
        soup = load_stl(src)
        verts, faces = weld(soup)
        centres = []
        ids = []
        for num, fma, a in sorted(teeth):
            if a != arch:
                continue
            p = os.path.join(outdir, f"{fma}-pulp.stl")
            if not os.path.exists(p):
                continue
            v = load_stl(p)
            centres.append(v.mean(axis=0))
            ids.append(fma)
        if not centres:
            continue
        C = np.array(centres)
        fc = verts[faces].mean(axis=1)
        owner = np.argmin(((fc[:, None, :] - C[None, :, :]) ** 2).sum(-1), axis=1)
        for i, fma in enumerate(ids):
            sel = faces[owner == i]
            if len(sel) < 40:
                continue
            got = process(verts[sel].reshape(-1, 3), TARGET_PDL, smooth=6)
            if got:
                write_binary_stl(os.path.join(outdir, f"{fma}-pdl.stl"), *got)
                made["pdl"] += 1
    print(f"pulp meshes: {made['pulp']}   pdl meshes: {made['pdl']}")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
