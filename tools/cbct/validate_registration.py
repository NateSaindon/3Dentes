#!/usr/bin/env python3
"""Validate a rigid registration produced by register.py.

Raw Dice understates this registration: the two mandible masks have very
different volumes because the fields of view cover different extents, so Dice is
capped well below 1 even for a perfect fit. The ceiling is reported alongside.

The decisive test is held out. The transform is fitted to the MANDIBLE label
alone, so the LOWER TEETH label -- rigidly attached to the mandible but never
seen by the optimiser -- is independent evidence. If the teeth land on each
other, the transform is right for reasons that have nothing to do with
overfitting the bone.

Usage: python3 tools/cbct/validate_registration.py <transform.json> <fixed.nii.gz> <moving.nii.gz>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_nifti import read_nifti
from register import euler


def apply_to(mask, p, spacing, centre, shape):
    R = euler(*np.radians(p["rotation_deg"]))
    t = np.asarray(p["translation_mm"]) / np.asarray(spacing)
    zz, yy, xx = np.indices(shape, dtype=np.float32)
    pts = np.stack([zz - centre[0], yy - centre[1], xx - centre[2]], axis=-1)
    src = pts @ R + np.asarray(centre) - t
    return ndi.map_coordinates(mask.astype(np.float32),
                               [src[..., 0], src[..., 1], src[..., 2]],
                               order=1, mode="constant", cval=0.0) > 0.5


def dice(a, b):
    s = a.sum() + b.sum()
    return 0.0 if s == 0 else 2.0 * float((a & b).sum()) / float(s)


def main():
    tp, fp, mp = sys.argv[1:4]
    p = json.load(open(tp))
    fl, _, pix = read_nifti(fp)
    ml, _, _ = read_nifti(mp)
    sp = tuple(float(x) for x in pix)
    vox = float(np.prod(sp))
    centre = np.array(ndi.center_of_mass(fl == p["label"]))

    print("label            fixed mm3   moving mm3    Dice   ceiling   recall")
    for k, name in ((2, "Mandible"), (4, "Lower Teeth"), (5, "Mand canal"),
                    (1, "Upper Skull"), (3, "Upper Teeth")):
        f = fl == k
        m = ml == k
        if not f.any() or not m.any():
            continue
        mt = apply_to(m, p, sp, centre, f.shape)
        d = dice(f, mt)
        ceiling = 2.0 * min(f.sum(), mt.sum()) / (f.sum() + mt.sum())
        recall = float((f & mt).sum()) / float(f.sum())
        tag = ""
        if k == p["label"]:
            tag = "  <- fitted on this"
        elif k == 4:
            tag = "  <- HELD OUT (rigid with the mandible)"
        elif k in (1, 3):
            tag = "  <- expected to disagree (maxilla moved)"
        print(f"{name:14s} {f.sum()*vox:9.1f} {mt.sum()*vox:11.1f}  {d:6.3f}  "
              f"{ceiling:7.3f}  {recall:6.3f}{tag}")

    # surface agreement on the fitted label
    f = fl == p["label"]
    mt = apply_to(ml == p["label"], p, sp, centre, f.shape)
    fs = f ^ ndi.binary_erosion(f)
    d_out = ndi.distance_transform_edt(~mt, sampling=sp)
    d_in = ndi.distance_transform_edt(mt, sampling=sp)
    signed = np.where(mt, -d_in, d_out)
    vals = np.abs(signed[fs])
    print(f"\nsurface distance, fixed mandible boundary to transformed moving:")
    print(f"  median {np.median(vals):.2f} mm   p90 {np.percentile(vals, 90):.2f} mm"
          f"   p99 {np.percentile(vals, 99):.2f} mm")
    print(f"  within 1 voxel (0.16 mm): {(vals <= 0.16).mean()*100:.1f}%"
          f"   within 0.5 mm: {(vals <= 0.5).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
