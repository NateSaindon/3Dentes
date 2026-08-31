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
TARGET_TRIS = 3500


# A SINGLE THRESHOLD CANNOT FIND A CANAL THAT NARROWS.
#
# The operator hand-shaded all 14 exported slices of tooth 14. Inside the
# shading the median is 500 HU, matching the independently measured
# pulp_density_hu -- so the density model is right. But the apical canal READS
# 890-1086 HU, because at under three voxels wide every voxel is a mixture and
# partial volume drags it toward dentin. A cut computed from a 500 HU chamber
# therefore never selects the apex, and no single value fixes it: lowering the
# cut until the apex appears floods the crown (318 mm3, precision 0.28).
#
# Measured contrast below the slice's own dentin, down tooth 14:
#     z= 51: 728    z= 83: 261    z=104: 264    z=125: 144    z=146: 298
# against a noise floor near 70 HU. The signal is present at every level; what
# changes is its amplitude. So the CUT has to follow it down.
#
# Dice against the hand shading, best parameters of each family:
#     flat cut (any value)                    0.763
#     hysteresis, seed high / grow low        0.664   (low cut merges everything)
#     per-slice adaptive contrast             0.763
#     coronal->apical taper                   0.804
# The taper is the only one that beats the flat cut, and it wins across a broad
# parameter region rather than at a lucky point.
TAPER_RATIO = 0.17   # apical cut as a fraction of the coronal cut
TAPER_POWER = 0.6    # <1, so the cut falls fastest through the mid-root
MIN_PIECE_VOX = 25   # absolute, NOT a fraction of the largest piece: apical to
                     # the furcation a molar has three separate canals, and each
                     # is tiny beside the chamber it is compared against.

# WHAT THE OPERATOR CALLS PULP IS BIGGER THAN THE LUMEN THE DEFICIT INTEGRAL
# MEASURES, BY A FACTOR MEASURED ON GROUND TRUTH.
#
# Their hand shading of tooth 14 integrates to 56.9 mm3. pulp_all.py measures
# 26.8 mm3 of lumen for the same tooth. Both are right about different things:
# the deficit integral recovers the STRICT radiolucent lumen, while the operator
# shades to the pulp-dentin transition -- predentin and the partial-volume shell
# read denser than pulp but are pulp tissue, and their instruction was that "any
# radiolucency inside dentinal structure should be solid pulp tissue".
#
# So the lumen stays the measurement and this is the one number that converts it
# to the modelled tissue. It is measured, not chosen, but it is measured on ONE
# tooth -- widen the ground truth before trusting it far.
SHADING_SCALE = 56.9 / 26.8


def _apical_fraction(tooth, arch):
    """0 at the crown, 1 at the apex, along z, for this tooth's arch."""
    zs = np.where(tooth.any(axis=(1, 2)))[0]
    if zs.size == 0:
        return None
    z0, z1 = int(zs.min()), int(zs.max())
    f = np.clip((np.arange(tooth.shape[0]) - z0) / max(z1 - z0, 1), 0.0, 1.0)
    # Mandibular roots point DOWN: the apex is at LOW z, so the ramp reverses.
    # Getting this backwards once already put "apices" on occlusal surfaces.
    return f if arch == "upper" else 1.0 - f


def solid_at(roi, tooth, interior, spacing, pulp_hu, frac, arch="upper"):
    """Radiolucency enclosed by dentin, with the cut tapering toward the apex."""
    out = np.zeros_like(tooth)
    af = _apical_fraction(tooth, arch)
    if af is None:
        return out
    for k in range(tooth.shape[0]):
        m = tooth[k]
        if m.sum() < 40:
            continue
        vals = roi[k][m]
        dentin = float(np.percentile(vals, 45))
        if dentin - pulp_hu < 200:
            continue
        # frac sets the coronal cut exactly as before; the taper scales the
        # DEPTH of that cut below dentin as the canal narrows apically.
        depth = frac * (dentin - pulp_hu)
        ramp = 1.0 - (1.0 - TAPER_RATIO) * af[k] ** TAPER_POWER
        cut = dentin - depth * ramp
        dark = interior[k] & (roi[k] < cut)
        if dark.sum() < 3:
            continue
        out[k] = dark
    return out


def solid_pulp(roi, tooth, spacing, pulp_hu, target_mm3=None, arch="upper",
               frac=None):
    """Radiolucency enclosed by dentin, calibrated to the measured lumen volume.

    The shape comes from the radiolucency and the SIZE comes from the deficit
    integral, because each method is good at one of them. Thresholding at the
    half-maximum returned 1567 mm3 across 28 teeth against a measured 704 -- the
    excess is the partial-volume shell around each lumen, which is a large
    fraction of a structure this small. Published pulp volumes for a full
    dentition come to roughly 760 mm3, so the measurement is the trustworthy
    number and the threshold is what should bend to it.
    """
    # THE MASK HAS THE PULP CUT OUT OF IT.
    #
    # DentalSegmentator's tooth label excludes the chamber -- it is a hole, not
    # part of the mask -- so `tooth & dist>0.3` excludes the very thing being
    # looked for, and the threshold could only ever find the speckle AROUND the
    # chamber. That is why molar pulp rendered as a cloud of fragments and why an
    # obvious dark chamber on an incisor slice came back unselected.
    #
    # CLAUDE.md records this exact trap from the pilot -- "the watershed basin
    # has the pulp cut out of it, fill per axial slice" -- and it applies to
    # these masks too. Filling per slice both fixes the search domain and hands
    # over the answer: the filled region minus the mask IS the enclosed void,
    # which is the operator's definition of pulp.
    solid_tooth = tooth.copy()
    for k in range(tooth.shape[0]):
        if tooth[k].any():
            solid_tooth[k] = ndi.binary_fill_holes(tooth[k])
    # An occlusal fissure is an enclosed hole IN PLANE -- an axial cut through
    # the fissure pattern looks exactly like a chamber -- so per-slice filling
    # counts fissures as pulp. They sit AT the surface and the chamber is deep,
    # so requiring depth separates them. It was 30% of tooth 12's void and put
    # "pulp" on the occlusal surface of a premolar.
    enclosed_void = solid_tooth & ~tooth
    surf_depth = ndi.distance_transform_edt(solid_tooth, sampling=spacing)
    enclosed_void &= surf_depth >= 0.5
    tooth = solid_tooth
    dist = ndi.distance_transform_edt(tooth, sampling=spacing)
    interior = tooth & (dist > 0.30)
    vox = float(np.prod(spacing))
    # Calibrate the UNION with the modelled tube, not the solid alone. The tube
    # exists to carry the canal apically past the point where nothing is
    # radiolucent enough to threshold; adding it on top of an already-calibrated
    # solid double-counts, which is what took the total to 1329 mm3 against a
    # measured 704.
    def finish(frac):
        out = (solid_at(roi, tooth, interior, spacing, pulp_hu, frac, arch)
               | enclosed_void)
        out = ndi.binary_closing(out, np.ones((3, 3, 3)))
        for k in range(out.shape[0]):
            if out[k].any():
                out[k] = ndi.binary_fill_holes(out[k])
        return out

    # CALIBRATE WHAT IS SHIPPED, not an intermediate. The search used to match
    # the raw threshold and the closing plus per-slice fill AFTERWARDS inflated
    # it; the delivered volume then missed the target it had just been fitted to.
    #
    # The upper bound has to exceed 1.0. frac scales the cut depth against
    # (dentin - pulp_hu), and the taper's fitted coronal cut on tooth 14 is about
    # 700 HU against a gap near 650 -- frac 1.08. With hi pinned at 0.99 the
    # search saturated, the apical ramp then admitted everything, and 28 teeth
    # came to 1784 mm3 against a measured 704.
    if frac is None:
        if target_mm3:
            lo, hi = 0.25, 1.80
            for _ in range(14):
                mid = 0.5 * (lo + hi)
                if finish(mid).sum() * vox > target_mm3:
                    lo = mid
                else:
                    hi = mid
            frac = 0.5 * (lo + hi)
        else:
            frac = 0.5
    out = finish(frac)
    lab, n = ndi.label(out, structure=np.ones((3, 3, 3)))
    if n == 0:
        return out
    # An ABSOLUTE floor, not a fraction of the largest piece. Apical to the
    # furcation a molar's canals are separate components, each a few hundred
    # voxels against a chamber of thousands; a relative filter deletes exactly
    # the canals this whole exercise is about. On tooth 14 that alone moved
    # Dice 0.790 -> 0.802.
    sz = ndi.sum(out, lab, range(1, n + 1))
    keep = [i + 1 for i in range(n) if sz[i] >= MIN_PIECE_VOX]
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
            tub_all = tube_voxels(rec, v, m.shape, origin_idx) & m
            m_solid = m.copy()
            for k in range(m.shape[0]):
                if m[k].any():
                    m_solid[k] = ndi.binary_fill_holes(m[k])

            # CALIBRATE THE COMPLETE CHAIN. Fitting solid_pulp alone and then
            # unioning the tube and closing again put tooth 14 at 87.7 mm3
            # against the 56.9 mm3 it had just been fitted to -- the steps after
            # the fit added 56%. Whatever is measured has to be the thing that
            # gets meshed, so the search runs over the whole assembly.
            # NO SECOND CLOSING, AND NO TUBE. Both were measured against the
            # operator's shading of tooth 14, over four cut depths and every
            # combination; the ranking never changed:
            #     closing iterations=2   -0.05 to -0.12 Dice
            #     union with the tube    -0.03 to -0.06 Dice
            #     per-slice fill          neutral
            # The tube existed to carry the canal apically past the point where
            # nothing is radiolucent enough to threshold. With the taper the
            # threshold now reaches FURTHER apically than the tube does, so the
            # tube only contributes volume in the wrong place. It stays measured
            # in pulp.json -- it is just no longer part of the shipped geometry.
            def assemble(frac, _m=m, _sub=sub, _ms=m_solid):
                sol = solid_pulp(_sub, _m, sp, pulp_hu, None, arch, frac=frac)
                return (sol & _ms), sol, np.zeros_like(sol)

            if target:
                want = target * SHADING_SCALE
                lo, hi = 0.25, 1.80
                for _ in range(12):
                    mid = 0.5 * (lo + hi)
                    if assemble(mid)[0].sum() * vox > want:
                        lo = mid
                    else:
                        hi = mid
                frac_fit = 0.5 * (lo + hi)
            else:
                frac_fit = 0.5
            both, sol, tub = assemble(frac_fit)
            # Close hard enough to join the chamber to its canals, then keep
            # only what belongs to the main pulp body. Radiolucency thresholding
            # scatters small dark specks through the coronal dentin of the
            # molars, and shipping them renders the chamber as a cloud of
            # fragments rather than one cavity.
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
