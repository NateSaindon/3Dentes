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

# Mean permanent mesiodistal crown widths (mm), in the order the arch is walked:
# upper from the patient's right, lower from the patient's left. Population
# averages, used only as a shape prior -- the image evidence dominates wherever
# it is clear, and these break ties where it is not.
WIDTHS = {
    "upper": [9.0, 10.0, 6.5, 7.0, 7.5, 6.5, 8.5,      # 2..8   right
              8.5, 6.5, 7.5, 7.0, 6.5, 10.0, 9.0],     # 9..15  left
    "lower": [10.5, 11.0, 7.0, 7.0, 7.0, 5.5, 5.0,     # 18..24 left
              5.0, 5.5, 7.0, 7.0, 7.0, 11.0, 10.5],    # 25..31 right
}
WIDTH_WEIGHT = 0.9        # how hard the width prior pulls against image evidence


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


def clean_mask(mask, spacing, min_mm3=20.0):
    """Drop disconnected specks before splitting.

    A single stray voxel far around the arch stretches the angular range and the
    partition spends a whole tooth on it, emitting a 0.4 mm3 "second molar" and
    shifting every number after it.
    """
    lab, n = ndi.label(mask)
    if n <= 1:
        return mask
    vox = float(np.prod(spacing))
    sizes = ndi.sum(mask, lab, range(1, n + 1)) * vox
    keep = [i + 1 for i in range(n) if sizes[i] >= min_mm3]
    return np.isin(lab, keep)


def _arc_histogram(mask, v):
    """Voxel histogram along ARC LENGTH around the dental arch.

    Angle alone is not enough: a molar sits at a larger radius than an incisor,
    so equal angles are unequal millimetres, and a width prior expressed in mm
    cannot be applied. Integrating the mean radius per angular bin converts the
    sweep to arc length, where tooth widths mean what they say.
    """
    zz, yy, xx = np.where(mask)
    wx = v.origin[0] + xx * v.spacing[0]
    wy = v.origin[1] + yy * v.spacing[1]
    cx = float(wx.mean())
    cy = float(wy.mean()) + ARCH_CENTRE_OFFSET
    dx, dy = wx - cx, -(wy - cy)
    th = np.degrees(np.arctan2(dx, dy))
    rad = np.hypot(dx, dy)
    lo, hi = float(th.min()) - 1.0, float(th.max()) + 1.0
    nb = max(160, int((hi - lo) * 1.5))
    counts, edges = np.histogram(th, bins=nb, range=(lo, hi))
    rsum, _ = np.histogram(th, bins=nb, range=(lo, hi), weights=rad)
    with np.errstate(invalid="ignore", divide="ignore"):
        rmean = np.where(counts > 0, rsum / np.maximum(counts, 1), np.nan)
    # fill empty bins so the arc-length axis stays monotonic
    idx = np.arange(nb)
    good = ~np.isnan(rmean)
    rmean = np.interp(idx, idx[good], rmean[good])
    dtheta = np.radians(edges[1] - edges[0])
    ds = rmean * dtheta                      # mm of arc per bin
    s_edge = np.concatenate([[0.0], np.cumsum(ds)])
    dens = ndi.gaussian_filter1d(counts.astype(float), 1.6)
    return dens, s_edge, edges, th, (cx, cy)


def _dp_cuts(dens, s_edge, widths, weight=WIDTH_WEIGHT):
    """Place len(widths)-1 cuts by dynamic programming.

    Cost has two terms: the histogram density at each cut (a contact is a
    trough, so a good cut is cheap) and squared deviation of each segment's arc
    length from its expected mesiodistal width. Greedy selection of the most
    prominent troughs cannot see the sequence as a whole -- it spent one cut
    splitting a first molar diagonally while leaving two incisors fused. A
    global optimum over the whole arch cannot make that trade, because the
    fused pair and the bisected molar both cost width error.
    """
    n = len(widths)
    B = len(dens)
    scale = dens.max() if dens.max() > 0 else 1.0
    cut = dens / scale                        # 0..1, low = good place to cut
    total_w = float(sum(widths))
    span = float(s_edge[-1])
    exp = [w * span / total_w for w in widths]   # scale the prior to this arch
    INF = 1e18
    # dp[k][b] = best cost with k teeth placed, ending at bin boundary b
    dp = np.full((n + 1, B + 1), INF)
    back = np.zeros((n + 1, B + 1), np.int32)
    dp[0][0] = 0.0
    for k in range(1, n + 1):
        e = exp[k - 1]
        for b in range(1, B + 1):
            s_b = s_edge[b]
            lo = max(0, b - 1)
            best, bestj = INF, 0
            for j in range(0, b):
                if dp[k - 1][j] >= INF:
                    continue
                w = s_b - s_edge[j]
                if w <= 0.15 * e or w > 2.6 * e:
                    continue
                pen = weight * ((w - e) / e) ** 2
                c = dp[k - 1][j] + pen + (cut[b - 1] if k < n else 0.0)
                if c < best:
                    best, bestj = c, j
            dp[k][b] = best
            back[k][b] = bestj
    if dp[n][B] >= INF:
        raise SystemExit("no valid arch partition found; check the arch label")
    bounds, b = [], B
    for k in range(n, 0, -1):
        j = back[k][b]
        bounds.append(j)
        b = j
    return sorted(x for x in bounds if 0 < x < B)


def split_arch(mask, v, arch, n_expected=N_PER_ARCH):
    mask = clean_mask(mask, tuple(v.spacing))
    dens, s_edge, edges, th, centre = _arc_histogram(mask, v)
    widths = WIDTHS[arch]
    if len(widths) != n_expected:
        raise SystemExit("width prior length does not match the expected count")
    cut_bins = _dp_cuts(dens, s_edge, widths)
    bounds = [edges[i] for i in cut_bins]
    zz, yy, xx = np.where(mask)
    seg = np.digitize(th, bounds)
    out = np.zeros(mask.shape, np.int32)
    out[zz, yy, xx] = seg + 1
    return out, len(bounds) + 1, centre


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
        split, n, centre = split_arch(mask, v, arch)
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
