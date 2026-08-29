#!/usr/bin/env python3
"""Locate the alveolar crest per tooth, per aspect, by directed apical search.

Two earlier attempts failed in opposite directions, and both for the same reason:
neither excluded the OTHER teeth.

  - A wide angular sector (bone within ~9.6 mm) reaches into the neighbouring
    teeth's alveolus and reports the crest ~4 mm too apical.
  - A tight shell around the root (0.6 mm) touches the neighbours' crowns, which
    are denser than bone, and reports it ~4 mm too coronal.

The crest is not a percentile of nearby bone. It is the most coronal level at
which bone lies against THIS root. So the search is directed: start at the
measured CEJ, walk apically along the root surface at each angular aspect, and
stop where bone first appears and persists. Every tooth in both arches is masked
out first, so a neighbour's crown can never be mistaken for bone.

Requiring persistence matters. A single dense voxel is noise or a neighbouring
lamina dura clipped in passing; a crest is bone that continues apically.

Validated two ways, both independent of the method:
  1. Interdental crest must sit CORONAL to the mid-facial and mid-lingual crest.
     That is anatomy, and no part of the algorithm enforces it.
  2. Repeatability across the two separate exposures, via the registration.

Usage: python3 tools/cbct/crest.py <volume.nrrd> <split-dir> <landmarks.json> <out.json>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume

BONE_HU = 600.0          # crestal cortical bone; well above PDL/marrow (450-870)
OUT_LO, OUT_HI = 0.35, 1.25   # mm outside the root surface to sample
PERSIST_MM = 0.8         # bone must continue this far apically to count
SEARCH_MM = 14.0         # how far apical of the CEJ to look
N_ANGLES = 24


def crest_for_tooth(vol, tooth, other_teeth, frame, cej_by_angle, spacing):
    c = np.array(frame["centre_index"], float)
    ax = np.array(frame["axis"], float)
    e2 = np.array(frame["e2"], float)
    e3 = np.array(frame["e3"], float)

    # tooth surface radius as a function of (angle, t), from the mask itself
    pts = np.argwhere(tooth).astype(float) - c
    t_all = pts @ ax
    u, w = pts @ e2, pts @ e3
    r_all = np.hypot(u, w)
    ang_all = np.degrees(np.arctan2(w, u))

    dense = (vol > BONE_HU) & ~other_teeth & ~tooth
    step = 360.0 / N_ANGLES
    persist_n = max(2, int(PERSIST_MM / spacing))
    out = {}
    for k in range(N_ANGLES):
        a0 = -180 + k * step
        cej = cej_by_angle.get(k)
        if cej is None:
            continue
        sel = (ang_all >= a0) & (ang_all < a0 + step)
        if sel.sum() < 20:
            continue
        a_mid = np.radians(a0 + step / 2)
        dirv = np.cos(a_mid) * e2 + np.sin(a_mid) * e3
        t_cej = cej / spacing
        hits = []
        n_steps = int(SEARCH_MM / spacing)
        for i in range(n_steps):
            t = t_cej - i
            # root radius at this level, from the tooth mask in this sector
            near = sel & (np.abs(t_all - t) < 2.0)
            if near.sum() < 8:
                hits.append(False)
                continue
            r_surf = float(np.percentile(r_all[near], 92))
            found = False
            for off in np.arange(OUT_LO / spacing, OUT_HI / spacing, 1.0):
                p = c + t * ax + (r_surf + off) * dirv
                iz, iy, ix = int(round(p[0])), int(round(p[1])), int(round(p[2]))
                if not (0 <= iz < dense.shape[0] and 0 <= iy < dense.shape[1]
                        and 0 <= ix < dense.shape[2]):
                    continue
                if dense[iz, iy, ix]:
                    found = True
                    break
            hits.append(found)
        # first level where bone appears and persists
        crest_t = None
        for i in range(len(hits) - persist_n):
            if all(hits[i:i + persist_n]):
                crest_t = t_cej - i
                break
        if crest_t is None:
            continue
        out[k] = round(float((crest_t) * spacing), 2)
    return out


def main():
    vol_path, split_dir, lm_path, out_path = sys.argv[1:5]
    v = Volume.load(vol_path)
    lm = json.load(open(lm_path))
    upper = np.load(os.path.join(split_dir, "upper_labels.npy"))
    lower = np.load(os.path.join(split_dir, "lower_labels.npy"))
    sp = float(v.spacing[0])
    result = {}
    print(f"{'Univ':>4s} {'n':>3s}  {'CEJ-crest median':>16s}  "
          f"{'interdental':>11s} {'mid-facial':>10s}  check")
    for arch, arr in (("upper", upper), ("lower", lower)):
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for key, m in lm.items():
            if m["arch"] != arch:
                continue
            target = np.array([0.0, 0.0])
            # recover this tooth's segment from its stored centroid
            c = np.array(m["centre_index"], float)
            best = min(ids, key=lambda s: np.linalg.norm(np.array(cents[s - 1]) - c))
            box = boxes[best - 1]
            pad = 40
            sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                       for b, n in zip(box, arr.shape))
            tooth = np.zeros(arr.shape, bool)
            tooth[box] = arr[box] == best
            others = ((upper > 0) | (lower > 0)) & ~tooth
            frame = dict(m)
            frame["centre_index"] = [c[i] - sl[i].start for i in range(3)]
            cej_by_angle = {}
            for i, (ang, cej) in enumerate(zip(m["angles"], m["cej_mm"])):
                if cej is not None:
                    cej_by_angle[int((ang + 180 - 7.5) // 15)] = cej
            cr = crest_for_tooth(v.data[sl].astype(np.float32), tooth[sl],
                                 others[sl], frame, cej_by_angle, sp)
            if not cr:
                print(f"{int(key):4d}   -  no crest found")
                continue
            d = {k: round(cej_by_angle[k] - cr[k], 2) for k in cr if k in cej_by_angle}
            vals = list(d.values())
            # aspects: 0/12 are the two cross-axis extremes; interproximal are the
            # sectors nearest the arch tangent. Use e2 (2nd principal axis of the
            # tooth) as the mesiodistal proxy: angles near 0 and 180.
            inter = [d[k] for k in d if k in (0, 1, 11, 12, 13, 23)]
            facial = [d[k] for k in d if k in (5, 6, 7, 17, 18, 19)]
            mi = float(np.median(inter)) if inter else float("nan")
            mf = float(np.median(facial)) if facial else float("nan")
            ok = "OK" if mi < mf else "inverted"
            result[key] = dict(universal=m["universal"], fma=m["fma"], arch=arch,
                               crest_mm={str(k): cr[k] for k in cr},
                               cej_to_crest_mm={str(k): d[k] for k in d},
                               median_mm=round(float(np.median(vals)), 2),
                               interdental_median_mm=round(mi, 2) if inter else None,
                               facial_median_mm=round(mf, 2) if facial else None)
            print(f"{int(key):4d} {len(vals):3d}  {np.median(vals):16.2f}  "
                  f"{mi:11.2f} {mf:10.2f}  {ok}")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    allv = [x for r in result.values() for x in r["cej_to_crest_mm"].values()]
    inv = sum(1 for r in result.values()
              if r["interdental_median_mm"] is not None
              and r["facial_median_mm"] is not None
              and r["interdental_median_mm"] >= r["facial_median_mm"])
    print(f"\n{len(result)} teeth, {len(allv)} aspects")
    print(f"CEJ-to-crest median {np.median(allv):.2f} mm  "
          f"(health roughly 1-2 mm)")
    print(f"anatomical check -- interdental crest coronal to facial: "
          f"{len(result)-inv}/{len(result)} teeth")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
