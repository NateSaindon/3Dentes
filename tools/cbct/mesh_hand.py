#!/usr/bin/env python3
"""Mesh the hand-traced pulp. Nothing is inferred here -- only smoothed.

The masks come from the operator's tracing, so this step must not second-guess
them: no volume calibration, no literature cap, no canal model, no despeckling.
It smooths the staircase a voxel mask always has, and it verifies that what
comes out is one connected surface. If a tooth looks wrong, the tracing is what
should change, not this.

Usage: mesh_hand.py <vol.nrrd> <pulp-dir> <out-dir> [smooth-before smooth-after]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import marching_cubes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from segment_tooth import write_binary_stl                 # noqa: E402
from meshsmooth import taubin                              # noqa: E402
from pulp_build import decimate_connected, pulp_field      # noqa: E402
from pulp_connect import mesh_components, mesh_field       # noqa: E402


SMOOTH_BEFORE, SMOOTH_AFTER = 30, 8


def main():
    global SMOOTH_BEFORE, SMOOTH_AFTER
    vol_path, pulp_dir, outdir = sys.argv[1:4]
    if len(sys.argv) > 5:
        SMOOTH_BEFORE, SMOOTH_AFTER = int(sys.argv[4]), int(sys.argv[5])
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    rec = json.load(open(os.path.join(pulp_dir, "pulp-connect.json")))["teeth"]
    print(f"{'Univ':>4s} {'mm3':>7s} {'tris':>6s} {'comps':>5s}")
    for fma, r in sorted(rec.items(), key=lambda kv: kv[1]["universal"]):
        P = np.load(os.path.join(pulp_dir, f"{fma}-pulp.npy"))
        if P.sum() < 40:
            print(f"{r['universal']:4d}  too little traced")
            continue
        oz, oy, ox = r["crop_origin_zyx"]
        thin = ndi.distance_transform_edt(P) <= 1.5
        f = pulp_field(P & ~thin, P & thin)
        verts, faces, _, _ = marching_cubes(f, level=0.5)
        if mesh_components(verts, faces) > 1:
            f = mesh_field(P)
            verts, faces, _, _ = marching_cubes(f, level=0.5)
        world = np.empty_like(verts)
        world[:, 0] = v.origin[0] + (ox + verts[:, 2]) * sp[0]
        world[:, 1] = v.origin[1] + (oy + verts[:, 1]) * sp[1]
        world[:, 2] = v.origin[2] + (oz + verts[:, 0]) * sp[2]
        # 30 Taubin passes were tuned for the operator's own tracings, which are
        # already coherent from slice to slice because a person drew them that
        # way. A PREDICTED mask is decided voxel by voxel, so its surface
        # carries a step wherever the classifier changed its mind, and 30
        # passes leave that visible as jagged, faceted canals. More smoothing
        # is not a cosmetic preference here: Taubin's lambda/mu pair is
        # volume-preserving, so the extra passes take out the staircase without
        # thinning a canal that is already only a voxel or two across.
        world = taubin(world, faces, SMOOTH_BEFORE)
        world, faces, _ = decimate_connected(world, faces)
        world = taubin(world, faces, SMOOTH_AFTER)
        write_binary_stl(os.path.join(outdir, f"{fma}-pulp.stl"), world, faces)
        print(f"{r['universal']:4d} {r['pulp_mm3']:7.1f} {len(faces):6d} "
              f"{mesh_components(world, faces):5d}")


if __name__ == "__main__":
    main()
