#!/usr/bin/env python3
"""Recover apical foramina from the HAND-TRACED pulp, and write them back.

combine_traces.py folds the operator's tracings into a pulp mask and stops there
-- it emits an empty `foramina` list for every tooth. Nothing complained, because
a foramen is not part of the pulp mesh; the loss only shows up two steps later,
where nerve.py and nerve_maxilla.py anchor their branches on those foramina and
silently drew none. That is rule 8's failure mode wearing a different hat: a
missing value that changes no number anyone was printing.

A foramen here is a MEASUREMENT of the traced pulp, not a model: it is where a
canal's apical end actually is. Canals are separate in the apical part of the
tooth even where they merge higher up, so each connected component of the apical
region terminates in exactly one foramen.

Usage: python3 tools/cbct/trace_foramina.py <volume.nrrd> <pulp-dir> [split-dir]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume

APICAL_FRAC = 0.45       # of the pulp's axial extent, measured from the apex
MIN_CANAL_VOX = 20       # below this a component is threshold noise, not a canal
FACE = ndi.generate_binary_structure(3, 1)


def foramina_for(pulp, arch, origin_zyx, vol):
    """One world point per canal terminus. Apical is -z lower, +z upper."""
    zs = np.where(pulp.any(axis=(1, 2)))[0]
    if not len(zs):
        return []
    lo, hi = int(zs.min()), int(zs.max())
    span = hi - lo + 1
    n = max(3, int(round(span * APICAL_FRAC)))
    if arch == "lower":                      # crowns point up: apex is low z
        sub, z0, sgn = pulp[lo:lo + n], lo, +1
    else:                                    # crowns hang down: apex is high z
        sub, z0, sgn = pulp[hi - n + 1:hi + 1], hi - n + 1, -1

    lab, cnt = ndi.label(sub, structure=FACE)
    out = []
    for i in range(1, cnt + 1):
        vox = np.argwhere(lab == i)
        if len(vox) < MIN_CANAL_VOX:
            continue
        tip = vox[:, 0].min() if sgn > 0 else vox[:, 0].max()
        face = vox[vox[:, 0] == tip]         # the terminal slice of this canal
        c = face.mean(axis=0)
        idx = np.array([c[0] + z0, c[1], c[2]]) + np.asarray(origin_zyx, float)
        # WORLD, never indices -- see CLAUDE.md rule 8.
        out.append([float(vol.origin[0] + idx[2] * vol.spacing[0]),
                    float(vol.origin[1] + idx[1] * vol.spacing[0]),
                    float(vol.origin[2] + idx[0] * vol.spacing[0])])
    return out


def main():
    vol_path, pulp_dir = sys.argv[1:3]
    split_dir = sys.argv[3] if len(sys.argv) > 3 else None
    v = Volume.load(vol_path)
    path = os.path.join(pulp_dir, "pulp-connect.json")
    doc = json.load(open(path))

    apex = {}
    if split_dir:                            # tooth apices, to validate against
        for arch in ("upper", "lower"):
            arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
            for lid in range(1, int(arr.max()) + 1):
                vox = np.argwhere(arr == lid)
                if not len(vox):
                    continue
                tip = vox[:, 0].min() if arch == "lower" else vox[:, 0].max()
                f = vox[vox[:, 0] == tip].mean(axis=0)
                apex.setdefault(arch, []).append(
                    np.array([v.origin[0] + f[2] * v.spacing[0],
                              v.origin[1] + f[1] * v.spacing[0],
                              v.origin[2] + tip * v.spacing[0]]))

    total, devs = 0, []
    print(f"{'U':>3} {'arch':<6} {'foramina':>9} {'to apex mm':>11}")
    for fma, rec in sorted(doc["teeth"].items(), key=lambda kv: kv[1]["universal"]):
        pulp = np.load(os.path.join(pulp_dir, f"{fma}-pulp.npy"))
        pts = foramina_for(pulp, rec["arch"], rec["crop_origin_zyx"], v)
        rec["foramina"] = [dict(world_lps=[round(x, 2) for x in p],
                                provenance="MEASURED (hand-traced pulp, "
                                           "apical terminus of the canal)")
                           for p in pts]
        total += len(pts)
        d = ""
        # Validate on SINGLE-canal teeth only. `apex` holds one point per tooth
        # -- the extreme apical voxel -- so on a molar two of the three foramina
        # would be scored against the wrong root's apex and the mean would read
        # 2.6 mm when nothing is wrong.
        if apex.get(rec["arch"]) and len(pts) == 1:
            aps = np.array(apex[rec["arch"]])
            dd = [float(np.min(np.linalg.norm(aps - np.array(p), axis=1)))
                  for p in pts]
            devs += dd
            d = f"{np.mean(dd):.2f}"
        print(f"{rec['universal']:>3} {rec['arch']:<6} {len(pts):>9} {d:>11}")
    doc["foramina_method"] = ("apical terminus of each connected component in "
                              f"the apical {APICAL_FRAC:.0%} of the traced pulp")
    json.dump(doc, open(path, "w"), indent=2)
    print(f"\n{total} foramina over {len(doc['teeth'])} teeth")
    if devs:
        print(f"foramen to tooth apex, {len(devs)} single-canal teeth: "
              f"mean {np.mean(devs):.2f} mm, median {np.median(devs):.2f} "
              f"(literature 0.52)")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
