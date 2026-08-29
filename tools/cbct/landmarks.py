#!/usr/bin/env python3
"""Measure the cementoenamel junction and the alveolar crest, per tooth.

These are the two landmarks that determine gingival form, and both are in the
data: the CEJ is where the enamel cap ends on the tooth, and the crest is the
coronal-most alveolar bone beside it. Measuring them is what makes the generated
gingiva patient-specific rather than a generic mesh morphed to fit.

Both are measured around the tooth as a function of angle, not as single points.
A CEJ is a curve -- it dips apically on the buccal and lingual and rises coronally
between the teeth, which is exactly what gives the gingival margin its scallop.
Reducing it to one height would throw away the shape being reconstructed.

The CEJ-to-crest distance is also a clinical measurement in its own right: about
1-2 mm in health, more where bone has been lost. It is reported per tooth per
aspect so it can be read as well as used.

Usage: python3 tools/cbct/landmarks.py <volume.nrrd> <split-dir> <pred.nii.gz> <out.json>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import threshold_otsu

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from read_nifti import read_nifti

N_ANGLES = 24
BONE_LABEL = {"upper": 1, "lower": 2}
UPPER = set(range(2, 16))


def tooth_frame(mask, arch):
    """Long axis oriented coronally (toward the crown), plus two cross axes."""
    pts = np.argwhere(mask).astype(float)
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    ax = vt[0]
    # coronal is -z for maxillary teeth (crowns hang down) and +z for mandibular
    want_positive_z = arch == "lower"
    if (ax[0] > 0) != want_positive_z:
        ax = -ax
    return c, ax, vt[1], vt[2]


def measure(vol, tooth, bone, arch, spacing):
    """CEJ and crest height per angle, in millimetres along the tooth axis."""
    c, ax, e2, e3 = tooth_frame(tooth, arch)
    roi = vol.astype(np.float32)
    hard = roi[tooth & (roi > 900)]
    if hard.size < 500:
        return None
    enamel_thr = float(threshold_otsu(hard))
    enamel = tooth & (roi > enamel_thr)
    if enamel.sum() < 200:
        return None
    # keep the coronal cap only
    lab, n = ndi.label(enamel)
    if n > 1:
        sz = ndi.sum(enamel, lab, range(1, n + 1))
        enamel = lab == (int(np.argmax(sz)) + 1)

    pts_t = np.argwhere(tooth).astype(float)
    rel = pts_t - c
    t_all = rel @ ax
    u_all, w_all = rel @ e2, rel @ e3
    ang_all = np.degrees(np.arctan2(w_all, u_all))

    pts_e = np.argwhere(enamel).astype(float)
    rel_e = pts_e - c
    t_e = rel_e @ ax
    ang_e = np.degrees(np.arctan2(rel_e @ e3, rel_e @ e2))

    pts_b = np.argwhere(bone).astype(float)
    out = dict(angles=[], cej_mm=[], crest_mm=[], cej_to_crest_mm=[])
    if len(pts_b):
        rel_b = pts_b - c
        t_b = rel_b @ ax
        u_b, w_b = rel_b @ e2, rel_b @ e3
        r_b = np.hypot(u_b, w_b)
        ang_b = np.degrees(np.arctan2(w_b, u_b))
    step = 360.0 / N_ANGLES
    for k in range(N_ANGLES):
        a0 = -180 + k * step
        a1 = a0 + step
        sel_e = (ang_e >= a0) & (ang_e < a1)
        if sel_e.sum() < 5:
            continue
        # CEJ = the most APICAL enamel at this angle (t is coronal-positive)
        cej = float(np.percentile(t_e[sel_e], 5)) * spacing
        crest = np.nan
        if len(pts_b):
            sel_b = (ang_b >= a0) & (ang_b < a1) & (r_b < 60)
            if sel_b.sum() > 20:
                # crest = most CORONAL bone at this angle
                crest = float(np.percentile(t_b[sel_b], 95)) * spacing
        out["angles"].append(round(a0 + step / 2, 1))
        out["cej_mm"].append(round(cej, 2))
        out["crest_mm"].append(None if np.isnan(crest) else round(crest, 2))
        out["cej_to_crest_mm"].append(None if np.isnan(crest) else round(cej - crest, 2))
    out["enamel_threshold_hu"] = round(enamel_thr)
    out["centre_index"] = [round(float(x), 2) for x in c]
    out["axis"] = [round(float(x), 4) for x in ax]
    out["e2"] = [round(float(x), 4) for x in e2]
    out["e3"] = [round(float(x), 4) for x in e3]
    return out


def main():
    vol_path, split_dir, pred_path, out_path = sys.argv[1:5]
    v = Volume.load(vol_path)
    lab, _, _ = read_nifti(pred_path)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    result = {}
    print(f"{'Univ':>4s} {'aspects':>7s}  {'CEJ-to-crest mm':>18s}   note")
    for arch in ("upper", "lower"):
        if arch not in rep:
            continue
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        bone_all = lab == BONE_LABEL[arch]
        # Centroids for every segment in ONE pass, and the per-tooth bounding
        # boxes with them. Re-scanning a 512^3 array once per tooth per segment
        # is 14x14 full-volume comparisons and dominates the runtime.
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        sid_world = {}
        for sid, cen in zip(ids, cents):
            if cen is None or any(np.isnan(cen)):
                continue
            sid_world[sid] = v.world(cen[2], cen[1], cen[0])[:2]
        for t in rep[arch]["teeth"]:
            num = t["universal"]
            target = np.array(t["world"][:2])
            best = min(((float(np.hypot(w[0] - target[0], w[1] - target[1])), sid)
                        for sid, w in sid_world.items()), default=None)
            if best is None:
                continue
            sid = best[1]
            box = boxes[sid - 1]
            if box is None:
                continue
            tooth = np.zeros_like(arr, dtype=bool)
            tooth[box] = arr[box] == sid
            zz, yy, xx = np.where(tooth)
            pad = 26
            sl = tuple(slice(max(0, a.min() - pad), min(s, a.max() + pad))
                       for a, s in zip((zz, yy, xx), tooth.shape))
            m = measure(v.data[sl], tooth[sl], bone_all[sl], arch, float(v.spacing[0]))
            if m is None:
                print(f"{num:4d}  {'-':>7s}  no enamel cap found")
                continue
            # measure() works in the cropped sub-volume, so its centroid is a
            # SUB-volume index. Anything reading this file converts it to world
            # coordinates, which requires the crop corner added back. Omitting it
            # collapses every tooth's landmarks into one small patch of the arch.
            # This is the third time this class of bug has appeared in this
            # pipeline; see CLAUDE.md.
            m["centre_index"] = [round(float(m["centre_index"][i]
                                             + sl[i].start), 2) for i in range(3)]
            m["crop_origin_zyx"] = [int(x.start) for x in sl]
            vals = [x for x in m["cej_to_crest_mm"] if x is not None]
            m["universal"] = num
            m["fma"] = t["fma"]
            m["arch"] = arch
            result[str(num)] = m
            if vals:
                med = float(np.median(vals))
                flag = "" if 0.5 <= med <= 3.0 else ("  <- check" if med > 3.0 else "")
                print(f"{num:4d} {len(vals):7d}  median {med:5.2f}  "
                      f"range {min(vals):5.2f}..{max(vals):5.2f}{flag}")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    allv = [x for r in result.values() for x in r["cej_to_crest_mm"] if x is not None]
    print(f"\n{len(result)} teeth, {len(allv)} aspects measured")
    print(f"CEJ-to-crest overall median {np.median(allv):.2f} mm "
          f"(health is roughly 1-2 mm)")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
