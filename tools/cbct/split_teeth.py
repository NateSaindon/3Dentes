#!/usr/bin/env python3
"""Split DentalSegmentator's per-class teeth labels into individual teeth.

DentalSegmentator returns "Upper Teeth" and "Lower Teeth" as single labels. That
is the hard half solved: what defeated the threshold pipeline was pulling a thin
premolar root out of trabecular bone, where tooth-to-bone contrast falls to
~419 HU (docs/cbct-pilot.md). Separating adjacent teeth is easier, because what
lies between them is the interproximal space -- a gap, not a density boundary.

Splitting by 3D shape does not work. A distance transform peaks once per *cusp*
and once per *root*, not once per tooth, so a marker-based watershed on it
returns 87 fragments for 28 teeth. Splitting at a fixed axial level does not work
either: the lower arch has a clean 14-component plateau, but the upper arch never
does, because upper molar roots separate before the crowns do.

What does work is that teeth are *sequential along the dental arch*. Swept as an
angle about a centre placed behind the arch, the voxel histogram has one lobe per
tooth with a minimum at each interproximal contact -- and all roots of a
multi-rooted tooth fall in the same lobe, which is exactly the property the other
two methods lacked. Both arches yield 13 minima, i.e. 14 teeth, unprompted.

Universal numbers follow from arch and order, and FMA ids are read from
tools/manifest.mjs rather than typed here -- the manifest stays the single source
of truth, as CLAUDE.md requires.

Usage: python3 tools/cbct/split_teeth.py <pred.nii.gz> <volume.nrrd> <out-dir>
"""
import json
import os
import re
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from read_nifti import read_nifti

UPPER, LOWER = 3, 4
N_PER_ARCH = 14           # third molars are extracted; see docs/cbct-plan.md
ARCH_CENTRE_OFFSET = 16.0  # mm posterior to the tooth-cloud centroid


def load_manifest_fma(manifest_path):
    """{(arch, side, position): fma} parsed from tools/manifest.mjs."""
    src = open(manifest_path).read()
    out = {}
    for m in re.finditer(
            r"tooth\(\s*'(FMA\d+)'\s*,\s*'(\w+)'\s*,\s*'(\w+)'\s*,\s*(\d+)", src):
        fma, arch, side, pos = m.groups()
        out[(arch, side, int(pos))] = fma
    return out


def universal(arch, order_index):
    """order_index counts 0..13 from the patient's right in the upper arch and
    from the patient's left in the lower arch -- the direction Universal
    numbering runs (1-16 upper right to left, 17-32 lower left to right)."""
    return (2 + order_index) if arch == "upper" else (18 + order_index)


def side_and_position(arch, number):
    """Universal number -> (side, position-from-midline)."""
    if arch == "upper":
        return ("right", 9 - number) if number <= 8 else ("left", number - 8)
    return ("left", 25 - number) if number <= 24 else ("right", number - 24)


def split_arch(mask, v, n_expected=N_PER_ARCH):
    zz, yy, xx = np.where(mask)
    wx = v.origin[0] + xx * v.spacing[0]
    wy = v.origin[1] + yy * v.spacing[1]
    cx = float(wx.mean())
    cy = float(wy.mean()) + ARCH_CENTRE_OFFSET
    th = np.degrees(np.arctan2(wx - cx, -(wy - cy)))
    lo, hi = float(th.min()) - 1.0, float(th.max()) + 1.0
    nb = max(120, int(hi - lo))
    hist, edges = np.histogram(th, bins=nb, range=(lo, hi))
    hs = ndi.gaussian_filter1d(hist.astype(float), 1.6)

    # The count is known -- 14 teeth per arch, third molars extracted -- so take
    # the 13 most PROMINENT minima rather than thresholding. Thresholding fused
    # the right canine and first premolar (one 1140 mm3 segment) while emitting a
    # 0.1 mm3 sliver elsewhere; ranking by prominence cannot do either, because it
    # always returns exactly the number of cuts asked for, at the best candidates.
    from scipy.signal import find_peaks
    idx, props = find_peaks(-hs, prominence=0)
    if len(idx) < n_expected - 1:
        raise SystemExit(f"only {len(idx)} interproximal minima; expected "
                         f"{n_expected - 1}. Check the arch label.")
    # Rank by prominence RELATIVE to the local lobe height, not absolute
    # prominence. Absolute prominence is dominated by the wide gaps between
    # molars and misses the shallow notches between the crowded lower incisors,
    # which left both lower centrals fused in one 788 mm3 segment. A contact is
    # a notch in its own neighbourhood regardless of how big its neighbours are,
    # so normalising by local height makes small teeth compete on equal terms.
    prom = props["prominences"]
    local = np.array([max(hs[max(0, i - 10):i + 11].max(), 1.0) for i in idx])
    best = sorted(idx[k] for k in np.argsort(prom / local)[::-1][:n_expected - 1])

    bounds = [edges[i + 1] for i in best]
    seg = np.digitize(th, bounds)          # 0..n_expected-1, one band per tooth
    out = np.zeros(mask.shape, np.int32)
    out[zz, yy, xx] = seg + 1
    return out, len(best) + 1, (cx, cy)


def main():
    pred_path, vol_path, outdir = sys.argv[1:4]
    os.makedirs(outdir, exist_ok=True)
    lab, _, _ = read_nifti(pred_path)
    v = Volume.load(vol_path)
    vox = float(np.prod(v.spacing))
    here = os.path.dirname(os.path.abspath(__file__))
    fma_map = load_manifest_fma(os.path.join(here, "..", "manifest.mjs"))
    report = {}
    for arch, code in (("upper", UPPER), ("lower", LOWER)):
        mask = lab == code
        if not mask.any():
            print(f"{arch}: label absent")
            continue
        split, n, centre = split_arch(mask, v)
        print(f"\n{arch} arch: {mask.sum()*vox:8.1f} mm3 -> {n} teeth "
              f"(expected {N_PER_ARCH})   arch centre ({centre[0]:.1f}, {centre[1]:.1f})")
        print(f"  {'Univ':>4s} {'FMA':>9s} {'mm3':>8s} {'roots':>5s}  centroid (x, y, z) LPS")
        rows = []
        # order: upper runs right (-x) to left (+x); lower runs left to right
        idxs = range(1, n + 1) if arch == "upper" else range(n, 0, -1)
        for order, seg_id in enumerate(idxs):
            m = split == seg_id
            if not m.any():
                continue
            num = universal(arch, order)
            side, pos = side_and_position(arch, num)
            fma = fma_map.get((("maxillary" if arch == "upper" else "mandibular"),
                               side, pos), "?")
            cz, cy2, cx2 = ndi.center_of_mass(m)
            wx, wy, wz = v.world(cx2, cy2, cz)
            # count roots: components in the apical third
            zs = np.where(m)[0]
            third = (zs.max() - zs.min()) // 3
            band = (m if arch == "upper"
                    else m).copy()
            cut = zs.max() - third if arch == "upper" else zs.min() + third
            band[:] = False
            if arch == "upper":
                band[cut:] = m[cut:]
            else:
                band[:cut] = m[:cut]
            cc, ncc = ndi.label(band)
            sz = ndi.sum(band, cc, range(1, ncc + 1)) * vox if ncc else np.array([])
            nroot = int((sz > 15.0).sum())
            rows.append(dict(universal=num, fma=fma, side=side, position=pos,
                             mm3=round(float(m.sum()) * vox, 1), roots=nroot,
                             world=[round(c, 2) for c in (wx, wy, wz)]))
            print(f"  {num:4d} {fma:>9s} {m.sum()*vox:8.1f} {nroot:5d}  "
                  f"({wx:+6.2f}, {wy:+7.2f}, {wz:+6.2f}) [{side[0].upper()}]")
        np.save(os.path.join(outdir, f"{arch}_labels.npy"), split.astype(np.int16))
        report[arch] = dict(total_mm3=round(float(mask.sum()) * vox, 1),
                            n_teeth=n, teeth=rows)
    with open(os.path.join(outdir, "split.json"), "w") as f:
        json.dump(report, f, indent=2)
    tot = sum(d["n_teeth"] for d in report.values())
    print(f"\ntotal teeth: {tot}  (expected 28)")


if __name__ == "__main__":
    main()
