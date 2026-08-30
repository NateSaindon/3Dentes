#!/usr/bin/env python3
"""Build the pulp as a SOLID volume: every radiolucency enclosed by dentin.

The earlier model swept a tube of measured cross-sectional area along a tracked
centreline. That is right about the canal's SIZE -- the deficit integral survives
sub-resolution blurring where thresholding cannot -- but wrong about the pulp's
FORM, because it renders a broad coronal chamber as a thin filament of the same
area. The operator's rule is better and is the one used here: anything
radiolucent enclosed by dentin is pulp tissue, and it should be solid.

So two sources are unioned:

  MEASURED SOLID   the low-density region inside the tooth, taken whole rather
                   than reduced to a centreline. This gets the chamber, the pulp
                   horns and the wide part of each canal at their true shape.
  MODELLED TUBE    the swept centreline from pulp_all.py, which continues the
                   canal apically through the region where it is narrower than
                   the point-spread function and no voxel is radiolucent enough
                   to threshold.

Neither alone is right. The solid alone stops partway down each root; the tube
alone is a filament with no chamber.

Usage: python3 tools/cbct/pulp_solid.py <volume.nrrd> <split-dir> <pulp.json> <out-dir>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import marching_cubes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from segment_tooth import write_binary_stl
from meshsmooth import taubin
from export_teeth import decimate

# Threshold at the HALF-MAXIMUM between this tooth's own measured pulp density
# and its dentin, rather than a fixed offset. A fixed offset has no principled
# value: at 260 HU below the slice's 55th percentile it swallowed dentin and
# returned 2772 mm3 against a measured 704, four times too much. The half-maximum
# is where a blurred boundary belongs, and pulp_all.py already measures the pulp
# density per tooth from the eroded chamber core.
PULP_FALLBACK_HU = 500.0
MIN_PIECE_MM3 = 0.8
TARGET_TRIS = 3500


def solid_at(roi, tooth, interior, spacing, pulp_hu, frac):
    """Radiolucency enclosed by dentin at a given fraction toward pulp density."""
    out = np.zeros_like(tooth)
    for k in range(tooth.shape[0]):
        m = tooth[k]
        if m.sum() < 40:
            continue
        vals = roi[k][m]
        dentin = float(np.percentile(vals, 45))
        if dentin - pulp_hu < 200:
            continue
        cut = dentin - frac * (dentin - pulp_hu)
        dark = interior[k] & (roi[k] < cut)
        if dark.sum() < 3:
            continue
        out[k] = dark
    return out


def solid_pulp(roi, tooth, spacing, pulp_hu, target_mm3=None):
    """Radiolucency enclosed by dentin, calibrated to the measured lumen volume.

    The shape comes from the radiolucency and the SIZE comes from the deficit
    integral, because each method is good at one of them. Thresholding at the
    half-maximum returned 1567 mm3 across 28 teeth against a measured 704 -- the
    excess is the partial-volume shell around each lumen, which is a large
    fraction of a structure this small. Published pulp volumes for a full
    dentition come to roughly 760 mm3, so the measurement is the trustworthy
    number and the threshold is what should bend to it.
    """
    dist = ndi.distance_transform_edt(tooth, sampling=spacing)
    interior = tooth & (dist > 0.30)
    vox = float(np.prod(spacing))
    # Calibrate the UNION with the modelled tube, not the solid alone. The tube
    # exists to carry the canal apically past the point where nothing is
    # radiolucent enough to threshold; adding it on top of an already-calibrated
    # solid double-counts, which is what took the total to 1329 mm3 against a
    # measured 704.
    if target_mm3:
        lo, hi = 0.25, 0.99
        for _ in range(12):
            mid = 0.5 * (lo + hi)
            got = solid_at(roi, tooth, interior, spacing, pulp_hu, mid).sum() * vox
            # frac is the fraction of the way from dentin DOWN to pulp density,
            # so a larger frac is a lower cut and includes LESS. The bounds move
            # the opposite way to the intuition.
            if got > target_mm3:
                lo = mid
            else:
                hi = mid
        frac = 0.5 * (lo + hi)
    else:
        frac = 0.5
    out = solid_at(roi, tooth, interior, spacing, pulp_hu, frac)
    # keep pieces that are actually enclosed, and close them into a solid
    out = ndi.binary_closing(out, np.ones((3, 3, 3)))
    for k in range(out.shape[0]):
        if out[k].any():
            out[k] = ndi.binary_fill_holes(out[k])
    lab, n = ndi.label(out, structure=np.ones((3, 3, 3)))
    if n == 0:
        return out
    vox = float(np.prod(spacing))
    sz = ndi.sum(out, lab, range(1, n + 1)) * vox
    keep = [i + 1 for i in range(n) if sz[i] >= MIN_PIECE_MM3]
    return np.isin(lab, keep)


def tube_voxels(rec, v, shape, origin_idx, scale=1.0):
    """Rasterise the modelled canal centrelines into the tooth's ROI grid."""
    out = np.zeros(shape, bool)
    x0, y0, z0 = origin_idx
    sp = float(v.spacing[0])
    for c in rec.get("canals", []):
        cen = np.asarray(c.get("centreline_lps", []), float)
        rad = np.asarray(c.get("radius_mm", []), float)
        if len(cen) < 3 or len(rad) != len(cen):
            continue
        for p, r in zip(cen, rad):
            ix = (p[0] - v.origin[0]) / sp - x0
            iy = (p[1] - v.origin[1]) / sp - y0
            iz = (p[2] - v.origin[2]) / sp - z0
            rr = max(r * scale / sp, 0.9)
            k = int(np.ceil(rr))
            zz, yy, xx = np.ogrid[-k:k + 1, -k:k + 1, -k:k + 1]
            ball = (zz * zz + yy * yy + xx * xx) <= rr * rr
            z, y, x = int(round(iz)), int(round(iy)), int(round(ix))
            z0_, z1_ = max(0, z - k), min(shape[0], z + k + 1)
            y0_, y1_ = max(0, y - k), min(shape[1], y + k + 1)
            x0_, x1_ = max(0, x - k), min(shape[2], x + k + 1)
            if z1_ <= z0_ or y1_ <= y0_ or x1_ <= x0_:
                continue
            sub = ball[z0_ - (z - k):z1_ - (z - k),
                       y0_ - (y - k):y1_ - (y - k),
                       x0_ - (x - k):x1_ - (x - k)]
            out[z0_:z1_, y0_:y1_, x0_:x1_] |= sub
    return out


def main():
    vol_path, split_dir, pulp_json, outdir = sys.argv[1:5]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    roi_full = v.data.astype(np.float32)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    pulp = json.load(open(pulp_json))
    sp = tuple(v.spacing)
    vox = float(np.prod(sp))
    report = {}
    print(f"{'Univ':>4s} {'solid':>8s} {'+tube':>8s} {'total mm3':>10s} {'tris':>6s}")
    for arch in ("upper", "lower"):
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            num, fma = t["universal"], t["fma"]
            tgt = np.array(t["world"][:2])
            best = min(ids, key=lambda s: float(np.hypot(
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[0] - tgt[0],
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[1] - tgt[1])))
            box = boxes[best - 1]
            pad = 8
            sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                       for b, n in zip(box, arr.shape))
            m = np.zeros(tuple(x.stop - x.start for x in sl), bool)
            m[tuple(slice(b.start - x.start, b.stop - x.start)
                    for b, x in zip(box, sl))] = arr[box] == best
            sub = roi_full[sl]
            origin_idx = (sl[2].start, sl[1].start, sl[0].start)
            rec = pulp.get(str(num), {})
            pulp_hu = float(rec.get("pulp_density_hu", PULP_FALLBACK_HU))
            target = rec.get("total_lumen_mm3")
            tub = tube_voxels(rec, v, m.shape, origin_idx) & m
            sol = solid_pulp(sub, m, sp, pulp_hu, target)
            # Keep only the part of the modelled tube that reaches BEYOND the
            # radiolucent solid -- the apical continuation, where the canal is
            # narrower than the point-spread function and nothing is dark enough
            # to threshold. Running the tube alongside the solid over its whole
            # length just re-adds volume the solid already has, which is what put
            # the total at 1329 mm3 against a measured 704.
            tub = tub & ~ndi.binary_dilation(sol, np.ones((3, 3, 3)), 2)
            both = (sol | tub) & m
            # Close hard enough to join the chamber to its canals, then keep
            # only what belongs to the main pulp body. Radiolucency thresholding
            # scatters small dark specks through the coronal dentin of the
            # molars, and shipping them renders the chamber as a cloud of
            # fragments rather than one cavity.
            both = ndi.binary_closing(both, np.ones((3, 3, 3)), iterations=2)
            lab, n = ndi.label(both, structure=np.ones((3, 3, 3)))
            if n > 1:
                szs = ndi.sum(both, lab, range(1, n + 1))
                biggest = float(szs.max())
                keep = [i + 1 for i in range(n)
                        if szs[i] >= max(MIN_PIECE_MM3 / vox, 0.15 * biggest)]
                both = np.isin(lab, keep)
            if both.sum() < 40:
                print(f"{num:4d}   too little pulp found")
                continue
            f = ndi.gaussian_filter(both.astype(np.float32), 0.9)
            verts, faces, _, _ = marching_cubes(f, level=0.5)
            world = np.empty_like(verts)
            world[:, 0] = v.origin[0] + (origin_idx[0] + verts[:, 2]) * sp[0]
            world[:, 1] = v.origin[1] + (origin_idx[1] + verts[:, 1]) * sp[1]
            world[:, 2] = v.origin[2] + (origin_idx[2] + verts[:, 0]) * sp[2]
            world = taubin(world, faces, 10)
            world, faces = decimate(world, faces, TARGET_TRIS)
            world = taubin(world, faces, 3)
            write_binary_stl(os.path.join(outdir, f"{fma}-pulp.stl"), world, faces)
            report[fma] = dict(universal=num, arch=arch,
                               solid_mm3=round(float(sol.sum()) * vox, 1),
                               tube_only_mm3=round(float((tub & ~sol).sum()) * vox, 1),
                               total_mm3=round(float(both.sum()) * vox, 1),
                               triangles=int(len(faces)))
            print(f"{num:4d} {sol.sum()*vox:8.1f} {(tub&~sol).sum()*vox:8.1f} "
                  f"{both.sum()*vox:10.1f} {len(faces):6d}")
    with open(os.path.join(outdir, "pulp-solid.json"), "w") as f:
        json.dump(report, f, indent=2)
    tot = sum(r["total_mm3"] for r in report.values())
    print(f"\n{len(report)} teeth, {tot:.1f} mm3 of pulp "
          f"(centreline model measured 704.4 mm3 of lumen)")


if __name__ == "__main__":
    main()
