#!/usr/bin/env python3
"""Rigidly register one CBCT volume onto another, mandible to mandible.

The plan called for masked rigid registration with Mattes mutual information,
chosen because CBCT gray values are uncalibrated and shift between exposures
(docs/cbct-survey.md, section 6) -- MI tolerates that where a sum-of-squares
metric would not.

There is now a better option. DentalSegmentator gives a mandible LABEL for each
volume, so the registration can run label-to-label and never look at intensities
at all. That removes the intensity-scaling problem rather than tolerating it, and
it is also the plan's "mask the metric to mandibular structure only" taken to its
limit: the mask IS the signal.

Rigid is the right model here and only here. The mandible is rigid within itself,
but the mandible is NOT rigid with respect to the maxilla -- these are separate
exposures and the condylar position differs between them, which is exactly why
the plan forbids one global transform for both jaws.

Convention: the transform maps MOVING world coordinates into FIXED world
coordinates, both LPS millimetres, as
    x_fixed = R @ (x_moving - centre_moving) + centre_moving + t

Usage:
  python3 tools/cbct/register.py <fixed.nii.gz> <moving.nii.gz> <label> <out.json>
"""
import json
import os
import sys
import time

import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_nifti import read_nifti


def euler(rx, ry, rz):
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def prep(mask, spacing, factor):
    """Downsample a binary mask to a smooth occupancy field for optimisation."""
    small = ndi.zoom(mask.astype(np.float32), 1.0 / factor, order=1)
    return ndi.gaussian_filter(small, 1.0), tuple(s * factor for s in spacing)


def overlap_cost(p, fixed_f, moving_f, sp, centre):
    """Negative soft Dice between fixed and transformed moving occupancy."""
    R = euler(*p[:3])
    t = p[3:] / np.asarray(sp)
    # sample fixed grid positions back into moving space
    zz, yy, xx = np.indices(fixed_f.shape, dtype=np.float32)
    pts = np.stack([zz - centre[0], yy - centre[1], xx - centre[2]], axis=-1)
    src = pts @ R + np.asarray(centre) - t
    vals = ndi.map_coordinates(moving_f, [src[..., 0], src[..., 1], src[..., 2]],
                               order=1, mode="constant", cval=0.0)
    num = 2.0 * float((fixed_f * vals).sum())
    den = float(fixed_f.sum() + vals.sum()) + 1e-6
    return -num / den


def crop_union(a, b, margin=12):
    """Crop both masks to their union bounding box. The mandible fills perhaps a
    third of the volume; optimising over the empty remainder costs time and buys
    nothing."""
    u = a | b
    zz, yy, xx = np.where(u)
    sl = tuple(slice(max(0, v.min() - margin), min(s, v.max() + margin + 1))
               for v, s in zip((zz, yy, xx), u.shape))
    return a[sl], b[sl], sl


def register(fixed, moving, spacing, schedule=(8, 4, 2)):
    """Coarse-to-fine rigid fit. Returns (rotation, translation_mm, dice)."""
    # moment initialisation: match centroids, then refine. Principal axes are not
    # used to initialise rotation -- a mandible's second and third moments are
    # close enough that the axis assignment can flip and start the optimiser in a
    # 180-degree hole.
    cf = np.array(ndi.center_of_mass(fixed))
    cm = np.array(ndi.center_of_mass(moving))
    p = np.zeros(6)
    p[3:] = (cf - cm) * np.asarray(spacing)
    best = None
    for factor in schedule:
        ff, sp = prep(fixed, spacing, factor)
        mf, _ = prep(moving, spacing, factor)
        centre = np.array(ndi.center_of_mass(ff))
        res = minimize(overlap_cost, p, args=(ff, mf, sp, centre),
                       method="Powell",
                       options=dict(maxiter=40, xtol=1e-3, ftol=1e-4))
        p = res.x
        best = -res.fun
        print(f"  level {factor}x ({sp[0]:.2f} mm): dice {best:.4f}  "
              f"rot {np.degrees(p[:3]).round(2)}  trans {p[3:].round(2)} mm",
              flush=True)
    return p, best


def main():
    fixed_path, moving_path, label, out_path = sys.argv[1:5]
    label = int(label)
    fl, _, fpix = read_nifti(fixed_path)
    ml, _, mpix = read_nifti(moving_path)
    if fl.shape != ml.shape:
        raise SystemExit("volumes differ in shape; this tool assumes a common grid")
    fixed = fl == label
    moving = ml == label
    sp = tuple(float(x) for x in fpix)
    print(f"fixed  label {label}: {fixed.sum() * np.prod(sp):9.1f} mm3")
    print(f"moving label {label}: {moving.sum() * np.prod(sp):9.1f} mm3")
    fixed, moving, sl = crop_union(fixed, moving)
    print(f"cropped to union bbox {tuple(s.stop - s.start for s in sl)}")
    t0 = time.time()
    p, dice = register(fixed, moving, sp)
    R = euler(*p[:3])
    result = dict(
        fixed=os.path.basename(fixed_path), moving=os.path.basename(moving_path),
        label=label, metric="soft Dice on the segmentation label",
        rotation_deg=[round(float(x), 4) for x in np.degrees(p[:3])],
        translation_mm=[round(float(x), 4) for x in p[3:]],
        rotation_matrix=[[round(float(c), 6) for c in row] for row in R],
        final_dice=round(float(dice), 4),
        seconds=round(time.time() - t0, 1),
        convention="x_fixed = R @ (x_moving - centre) + centre + t, LPS mm, "
                   "index order (z, y, x)",
        note="rigid, mandible only. The mandible is NOT rigid with respect to "
             "the maxilla across these exposures.")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nfinal Dice {dice:.4f} in {result['seconds']}s -> {out_path}")


if __name__ == "__main__":
    main()
