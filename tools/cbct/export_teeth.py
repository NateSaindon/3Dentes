#!/usr/bin/env python3
"""Mesh all 28 measured teeth and decimate them to the atlas's polygon budget.

Two things this must get right.

**Mesh from grey levels, not the mask.** Marching cubes on a binary mask can only
put a vertex on a voxel boundary, so it terraces at 0.16 mm however much it is
smoothed afterwards. The surface is therefore taken from the intensity field,
confined to a dilation of the DentalSegmentator mask, which places it where the
density boundary actually falls (docs/cbct-pilot.md).

**Decimate, but not past the anatomy.** BodyParts3D teeth average 7,101 triangles
and the whole current atlas is 348k, so ~70k per CBCT tooth is ten times over
budget. Quadric decimation to ~8k keeps cusp tips and the occlusal table while
losing voxel noise. Note this does NOT conflict with the exact-welding invariant:
welding merges bitwise-identical vertices to avoid rounding cusps, and runs in
build-assets.mjs on whatever it is given. Decimation happens before that and is a
deliberate, measured reduction rather than a silent tolerance.

Output goes to assets/cbct/stl/, NOT assets/source/stl/. Invariant 3: BodyParts3D
material is CC BY-SA and anatomy measured from the operator's own scan is a
separate work. They must not share a tree.

Usage: python3 tools/cbct/export_teeth.py <volume.nrrd> <split-dir> <out-dir> [target-tris]
"""
import json
import os
import struct
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from segment_tooth import mesh as grey_mesh, write_binary_stl

SURFACE_HU = 1050.0
TARGET_TRIS = 8000


def decimate(verts, faces, target):
    import fast_simplification
    if len(faces) <= target:
        return verts, faces
    frac = 1.0 - (target / len(faces))
    v, f = fast_simplification.simplify(verts.astype(np.float32),
                                        faces.astype(np.int32), frac)
    return np.asarray(v, dtype=np.float64), np.asarray(f, dtype=np.int64)


def main():
    vol_path, split_dir, outdir = sys.argv[1:4]
    target = int(sys.argv[4]) if len(sys.argv) > 4 else TARGET_TRIS
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    roi_full = v.data.astype(np.float32)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    vox = float(np.prod(v.spacing))
    out_report = {}
    print(f"{'Univ':>4s} {'FMA':>9s} {'mask mm3':>9s} {'raw tris':>9s} "
          f"{'final':>7s}  {'side':>5s}")
    for arch in ("upper", "lower"):
        if arch not in rep:
            continue
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            target_xy = np.array(t["world"][:2])
            best = min(ids, key=lambda s: float(np.hypot(
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[0] - target_xy[0],
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[1] - target_xy[1])))
            box = boxes[best - 1]
            pad = 10
            sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                       for b, n in zip(box, arr.shape))
            m = np.zeros(tuple(x.stop - x.start for x in sl), bool)
            m[tuple(slice(b.start - x.start, b.stop - x.start)
                    for b, x in zip(box, sl))] = arr[box] == best
            sub = roi_full[sl]
            origin_idx = (sl[2].start, sl[1].start, sl[0].start)
            got = grey_mesh(m, v, origin_idx, roi=sub, level=SURFACE_HU, band=3)
            if got is None:
                print(f"{t['universal']:4d} {t['fma']:>9s}  mesh failed")
                continue
            verts, faces = got
            raw = len(faces)
            verts, faces = decimate(verts, faces, target)
            path = os.path.join(outdir, f"{t['fma']}.stl")
            write_binary_stl(path, verts, faces)
            cx = float((verts[:, 0].min() + verts[:, 0].max()) / 2)
            side = "left" if cx > 0 else "right"
            expect = t.get("side") or ("left" if t["world"][0] > 0 else "right")
            flag = "" if side == expect else "  *** SIDE MISMATCH ***"
            out_report[t["fma"]] = dict(universal=t["universal"], arch=arch,
                                        mask_mm3=t["mm3"], raw_triangles=raw,
                                        triangles=int(len(faces)),
                                        centroid_x=round(cx, 2), side=side)
            print(f"{t['universal']:4d} {t['fma']:>9s} {t['mm3']:9.1f} {raw:9,d} "
                  f"{len(faces):7,d}  {side:>5s}{flag}")
    with open(os.path.join(outdir, "teeth.json"), "w") as f:
        json.dump(out_report, f, indent=2)
    tot = sum(r["triangles"] for r in out_report.values())
    print(f"\n{len(out_report)} teeth, {tot:,} triangles "
          f"(BodyParts3D equivalent: 198,846)")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
