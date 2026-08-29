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
from read_nifti import read_nifti
from segment_tooth import mesh as grey_mesh, write_binary_stl
from meshsmooth import taubin, mesh_volume

SURFACE_HU = 1050.0
TARGET_TRIS = 8000
EXCLUDE_PAD = 1     # voxels of the neighbour/bone mask to keep clear of
SMOOTH_BEFORE = 26        # Taubin passes on the raw marching-cubes surface
SMOOTH_AFTER = 10         # settles the decimated triangulation


def decimate(verts, faces, target):
    import fast_simplification
    if len(faces) <= target:
        return verts, faces
    frac = 1.0 - (target / len(faces))
    v, f = fast_simplification.simplify(verts.astype(np.float32),
                                        faces.astype(np.int32), frac)
    return np.asarray(v, dtype=np.float64), np.asarray(f, dtype=np.int64)


def main():
    vol_path, split_dir, pred_path, outdir = sys.argv[1:5]
    target = int(sys.argv[5]) if len(sys.argv) > 5 else TARGET_TRIS
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    roi_full = v.data.astype(np.float32)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    # Everything the tooth's own surface must not run into: the jaws, and every
    # other tooth. Meshing the grey field inside a dilation of the mask picks up
    # whatever is dense nearby, and the lamina dura is DENSE and CLOSE -- the PDL
    # measures 0.08-0.16 mm apparent, well inside the dilation band. That is what
    # put a crusty, barnacled surface along one side of every lower root.
    lab, _, _ = read_nifti(pred_path)
    jaws = (lab == 1) | (lab == 2)
    all_teeth = ((np.load(os.path.join(split_dir, "upper_labels.npy")) > 0)
                 | (np.load(os.path.join(split_dir, "lower_labels.npy")) > 0))
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
            sub = roi_full[sl].copy()
            # Push everything that is not this tooth below the isolevel, so the
            # surface cannot cross into bone or into a neighbour no matter how
            # dense they are or how close they sit.
            exclude = (jaws[sl] | all_teeth[sl]) & ~m
            if EXCLUDE_PAD:
                exclude = ndi.binary_dilation(exclude, np.ones((3, 3, 3)),
                                              EXCLUDE_PAD) & ~m
            # Blend two surface definitions rather than clamping one of them.
            #
            # Grey-level meshing is the right model where the tooth borders SPACE
            # -- PDL, air, soft tissue -- because there is a real density edge to
            # find. It is meaningless where the tooth borders another tooth: at a
            # true contact there is no gap, both sides are dentin, and there is no
            # edge. Clamping the neighbour to a low value there just substitutes
            # one artefact for another, a flat terraced facet where the field
            # falls off a cliff.
            #
            # So near a neighbour the surface follows the SEGMENTATION boundary,
            # expressed as a signed distance ramp through the isolevel, and away
            # from one it follows the grey levels. The weight moves smoothly
            # between them so neither transition is itself an edge.
            # The shape field comes from a SMOOTHED occupancy, not a distance
            # transform of the raw mask. DentalSegmentator infers at 0.43 mm and
            # the label is resampled to 0.16 mm, so the mask boundary is a
            # staircase; a distance transform of it inherits every step, and the
            # isosurface then reproduces them as striations. Blurring occupancy
            # puts the boundary at a sub-voxel position instead.
            occ = ndi.gaussian_filter(m.astype(np.float32), 1.3)
            far = ndi.distance_transform_edt(~exclude)
            w = np.clip((far - 1.0) / 3.0, 0.0, 1.0)
            shape_field = SURFACE_HU + 900.0 * (occ - 0.5)
            sub = w * ndi.gaussian_filter(sub, 0.5) + (1.0 - w) * shape_field
            sub = ndi.gaussian_filter(sub, 0.7)
            origin_idx = (sl[2].start, sl[1].start, sl[0].start)
            got = grey_mesh(m, v, origin_idx, roi=sub, level=SURFACE_HU, band=3)
            if got is None:
                print(f"{t['universal']:4d} {t['fma']:>9s}  mesh failed")
                continue
            verts, faces = got
            raw = len(faces)
            v0 = mesh_volume(verts, faces)
            verts = taubin(verts, faces, SMOOTH_BEFORE)
            verts, faces = decimate(verts, faces, target)
            verts = taubin(verts, faces, SMOOTH_AFTER)
            v1 = mesh_volume(verts, faces)
            shrink = 100.0 * (1.0 - v1 / v0) if v0 else 0.0
            path = os.path.join(outdir, f"{t['fma']}.stl")
            write_binary_stl(path, verts, faces)
            cx = float((verts[:, 0].min() + verts[:, 0].max()) / 2)
            side = "left" if cx > 0 else "right"
            expect = t.get("side") or ("left" if t["world"][0] > 0 else "right")
            flag = "" if side == expect else "  *** SIDE MISMATCH ***"
            out_report[t["fma"]] = dict(universal=t["universal"], arch=arch,
                                        mask_mm3=t["mm3"], raw_triangles=raw,
                                        triangles=int(len(faces)),
                                        mesh_mm3=round(v1, 1),
                                        shrink_pct=round(shrink, 2),
                                        centroid_x=round(cx, 2), side=side)
            print(f"{t['universal']:4d} {t['fma']:>9s} {t['mm3']:9.1f} {raw:9,d} "
                  f"{len(faces):7,d}  {side:>5s}  shrink {shrink:+5.1f}%{flag}")
    with open(os.path.join(outdir, "teeth.json"), "w") as f:
        json.dump(out_report, f, indent=2)
    tot = sum(r["triangles"] for r in out_report.values())
    print(f"\n{len(out_report)} teeth, {tot:,} triangles "
          f"(BodyParts3D equivalent: 198,846)")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
