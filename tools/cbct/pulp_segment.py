#!/usr/bin/env python3
"""Segment the pulp radiolucency in 2D, per tooth, BEFORE anything is meshed.

This is the step that should have come first. Everything until now inferred the
pulp from a volume budget and literature priors and then checked the result;
that inverts the problem, and it cost a great deal of time. Here the CBCT is
asked directly what is radiolucent inside each tooth, the answer is written out
as slices a clinician can check, and only once those are right does a mesh get
built from them.

The segmentation itself is deliberately simple, because every elaboration tried
so far has been a way of compensating for not having looked:

  reference   per axial slice, the 45th percentile of the tooth's own intensity
              -- its dentin. A global threshold cannot work: dentin density
              varies down a tooth and between teeth.
  candidate   interior voxels (>= MIN_DEPTH_MM from the tooth surface, so the
              periodontal ligament and the occlusal fissures are excluded) that
              sit CONTRAST_HU below that reference.
  keep        the component connected in 3D to the chamber seed -- the largest
              candidate blob in the coronal half. Radiolucency that is not
              continuous with the pulp is not pulp.

No volume target, no literature cap, no canal model. Those belong downstream;
what is wanted here is an honest answer to "what is dark inside this tooth".

Usage: pulp_segment.py <vol.nrrd> <split-dir> <out-dir> [contrast_hu]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402

CONTRAST_HU = 260.0
# THE THRESHOLD IS CHOSEN PER TOOTH, FROM THE IMAGE, BY THE LEAKAGE KNEE.
# Sweeping contrast on tooth 9: 200 HU floods dentin (70 mm3, 13% of the tooth),
# 520 HU leaves visible lumen uncovered (13 mm3), and 300-400 fits the dark
# space exactly (18-23 mm3, 3.4-4.3%). That shape is general: above the knee the
# segmentation grows slowly as the threshold loosens, because it is still filling
# a real lumen; below it the volume runs away as dentin starts to qualify. The
# knee is therefore the lowest contrast that still describes the pulp, and it
# can be found without a volume prior -- which is the point, since a volume prior
# is what put literature numbers ahead of this patient's anatomy.
SWEEP = tuple(range(560, 179, -20))
KNEE_GROWTH = 1.14        # per 20 HU step; above this the segmentation is leaking
MIN_DEPTH_MM = 0.55
# RESTORATIONS AND THEIR HALOES ARE NOT PULP.
# Teeth 19 and 30 carry 340 and 273 mm3 of material saturated at the scanner's
# 3072 HU ceiling, and metal throws a dark beam-hardening halo that thresholds
# exactly like a radiolucent lumen -- at every contrast level tried, red bled
# into the restoration and the shadow around it. That is why those two teeth
# always had the largest volumes and the largest "uncovered radiolucency", and
# no amount of threshold tuning could fix it because the artefact is darker than
# real dentin. Excluded here, and the teeth are FLAGGED: their pulp is partly
# obscured and the model over them is inference, not measurement.
RESTORATION_HU = 2600.0
RESTORATION_MARGIN_MM = 1.4
SEED_MIN_VOX = 20
FACE = None            # set at runtime


def restoration_mm3(sub, tooth_solid, spacing):
    vox = float(np.prod(spacing))
    return float((tooth_solid & (sub >= RESTORATION_HU)).sum()) * vox


def segment_tooth(sub, tooth_solid, spacing, arch, contrast=CONTRAST_HU):
    """Radiolucency inside one tooth, connected to the chamber."""
    face = ndi.generate_binary_structure(3, 1)
    depth = ndi.distance_transform_edt(tooth_solid, sampling=tuple(spacing))
    inner = tooth_solid & (depth >= MIN_DEPTH_MM)
    metal = sub >= RESTORATION_HU
    if metal.any():
        halo = ndi.distance_transform_edt(~metal, sampling=tuple(spacing))
        inner &= halo >= RESTORATION_MARGIN_MM
    dark = np.zeros_like(tooth_solid)
    for k in range(tooth_solid.shape[0]):
        m = tooth_solid[k]
        if m.sum() < 40:
            continue
        ref = float(np.percentile(sub[k][m], 45))
        dark[k] = inner[k] & (sub[k] < ref - contrast)
    if not dark.any():
        return dark, 0.0
    # seed: the biggest dark blob in the coronal half, which is the chamber
    zs = np.where(tooth_solid.any(axis=(1, 2)))[0]
    mid = (int(zs.min()) + int(zs.max())) // 2
    cor = np.zeros_like(dark)
    if arch == "upper":
        cor[:mid] = True
    else:
        cor[mid:] = True
    lab, n = ndi.label(dark, structure=np.ones((3, 3, 3)))
    if n == 0:
        return dark, 0.0
    sizes = ndi.sum(dark, lab, range(1, n + 1))
    cor_ids = set(np.unique(lab[dark & cor])) - {0}
    if cor_ids:
        seed_id = max(cor_ids, key=lambda i: sizes[i - 1])
    else:
        seed_id = int(np.argmax(sizes)) + 1
    keep = lab == seed_id
    # bridge across single-voxel gaps the threshold leaves in a narrow canal,
    # then re-take the component so nothing detached is smuggled back in
    keep = ndi.binary_closing(keep, np.ones((3, 3, 3)))
    keep &= inner
    lab2, n2 = ndi.label(keep, structure=face)
    if n2 > 1:
        s2 = ndi.sum(keep, lab2, range(1, n2 + 1))
        keep = lab2 == (int(np.argmax(s2)) + 1)
    frac = float(keep.sum()) / max(float(dark.sum()), 1.0)
    return keep, frac


def choose_contrast(sub, tooth_solid, spacing, arch):
    """Lowest contrast before the segmentation starts leaking into dentin."""
    vols = []
    for c in SWEEP:
        keep, _ = segment_tooth(sub, tooth_solid, spacing, arch, float(c))
        vols.append(float(keep.sum()))
    best = SWEEP[0]
    for i in range(1, len(SWEEP)):
        prev = max(vols[i - 1], 1.0)
        if vols[i] / prev > KNEE_GROWTH:
            best = SWEEP[i - 1]
            break
        best = SWEEP[i]
    return float(best), list(zip(SWEEP, vols))


def main():
    vol_path, split_dir, outdir = sys.argv[1:4]
    contrast = float(sys.argv[4]) if len(sys.argv) > 4 else CONTRAST_HU
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    roi_full = v.data.astype(np.float32)
    vox = float(np.prod(sp))
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    report = {}
    print(f"contrast {contrast:.0f} HU below each slice's dentin\n")
    print(f"{'Univ':>4s} {'pulp mm3':>8s} {'tooth':>6s} {'p/t%':>5s} "
          f"{'connected%':>10s} {'HU':>8s}")
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
            ms = m.copy()
            for k in range(m.shape[0]):
                if m[k].any():
                    ms[k] = ndi.binary_fill_holes(m[k])
            sub = roi_full[sl]
            c_t = contrast
            if contrast <= 0:
                c_t, _curve = choose_contrast(sub, ms, sp, arch)
            keep, frac = segment_tooth(sub, ms, sp, arch, c_t)
            np.save(os.path.join(outdir, f"{fma}-pulp.npy"), keep)
            tv = ms.sum() * vox
            pv = keep.sum() * vox
            rest = restoration_mm3(sub, ms, sp)
            report[fma] = dict(universal=num, arch=arch,
                               restoration_mm3=round(rest, 2),
                               obscured=bool(rest > 5.0),
                               pulp_mm3=round(pv, 2), tooth_mm3=round(tv, 1),
                               pulp_pct=round(100 * pv / max(tv, 1e-6), 2),
                               connected_frac=round(frac, 3),
                               contrast_hu=c_t, foramina=[])
            print(f"{num:4d} {pv:8.1f} {tv:6.0f} {100 * pv / max(tv, 1e-6):5.1f} "
                  f"{100 * frac:9.0f}% {c_t:8.0f}"
                  + ("  RESTORATION" if rest > 5.0 else ""))
    tot = sum(r["pulp_mm3"] for r in report.values())
    print(f"\n28 teeth, {tot:.1f} mm3 of radiolucent pulp")
    json.dump(dict(method="direct radiolucency segmentation, no volume prior",
                   contrast_hu=contrast, teeth=report),
              open(os.path.join(outdir, "pulp-connect.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
