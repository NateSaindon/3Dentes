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
BRIDGE_RADII = (7, 6, 5, 4, 3, 2)   # candidate opening radii, voxels
CONTACT_EPS = 0.08
PARTITION_MM = 0.48 # within this of a neighbour the SEGMENTATION alone
                    # decides the surface, so both teeth read the same
                    # boundary and cannot cross it
BRIDGE_CAP = 0.025  # a trim may not take more than this share of a tooth  # a trim may not take more than this share of a tooth
BRIDGE_NEAR_MM = 1.5   # how close to a same-arch neighbour it must be
SMOOTH_BEFORE = 26        # Taubin passes on the raw marching-cubes surface
SMOOTH_AFTER = 10         # settles the decimated triangulation


# A tooth is ONE SOLID, so its surface is ONE SHELL. Anything else the
# isosurface picks up inside the meshing band is not part of this tooth.
MAX_STRAY_FRAC = 0.06     # of mesh volume; above this something else is wrong


def keep_solid(verts, faces):
    """Drop every surface component but the largest. Returns (v, f, dropped).

    23 of 28 teeth shipped in two or more pieces, and nobody had looked, because
    nothing checked. The masks are single connected components -- verified on
    both the old and the new split -- so every one of these was made by the
    MESHER: the grey-level isosurface fires on whatever is dense inside the
    band around the tooth, and on the molars it closes a second shell of about
    25 mm3 around the pulp chamber, which DentalSegmentator does not include in
    the tooth label. On teeth 20 and 29 the restoration-density claiming left
    the surface in 23 and 27 pieces against their crowned neighbours.

    The boundary of a connected solid is one shell, so this is not a
    tolerance -- it is the definition being enforced. Note it discards INTERNAL
    shells too, which are invisible but cost triangles and z-fight through a
    tooth rendered at reduced opacity.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = len(verts)
    r = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]])
    c = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    g = coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n))
    k, lab = connected_components(g, directed=False)
    if k == 1:
        return verts, faces, []
    fl = lab[faces[:, 0]]
    sizes = np.bincount(fl, minlength=k)
    main = int(np.argmax(sizes))
    dropped = []
    for i in range(k):
        if i == main:
            continue
        sub = faces[fl == i]
        if not len(sub):
            continue
        dropped.append(mesh_volume(verts, sub))
    keep = faces[fl == main]
    used = np.unique(keep)
    remap = np.full(n, -1, np.int64)
    remap[used] = np.arange(len(used))
    return verts[used], remap[keep], dropped


def ball(r):
    z, y, x = np.ogrid[-r:r + 1, -r:r + 1, -r:r + 1]
    return (z * z + y * y + x * x) <= r * r + 1e-9


def debridge(arr, spacing, radii=BRIDGE_RADII, near_mm=BRIDGE_NEAR_MM,
             cap=BRIDGE_CAP):
    """Trim the CONTACT BRIDGE off every tooth in one arch's label array.

    DentalSegmentator infers at 0.43 mm. Two enamel surfaces in contact are one
    voxel apart at that scale, so the label bridges them, and the bridge is
    WIDER than either crown. The arch split then divides it, and each tooth ends
    up with a lens about 3 mm across on its proximal surface and a matching
    notch where the neighbour's fattened label was kept out of it. Measured by
    exact voxel intersection over ten contacts, neighbouring crowns overlapped
    by 4.80 mm3 before this and 0.17 mm3 after.

    A bridge is thin and it is beside a neighbour. Both conditions are needed:
      - thin, so a morphological OPENING removes it and leaves the crown;
      - beside a neighbour IN THE SAME ARCH, so cusp tips survive. They are thin
        too, and they sit right against the opposing arch, so a proximity test
        that did not care which arch would shave every cusp in the mouth.

    THE RADIUS IS PER TOOTH, and that is not a refinement. A single 1.1 mm
    opening cleared the molars and ate the anteriors: the lower central incisors
    lost 8.5% and 5.8% of their volume and canine 11 lost 4.0%, because an
    incisor is only 5-6 mm across and its neighbours touch it along the whole
    proximal surface. Each tooth now gets the LARGEST radius that removes no
    more than `cap` of it, so the trim scales with what there is to trim.
    """
    out = arr.copy()
    boxes = ndi.find_objects(arr)
    removed = 0
    chosen = {}
    for i, box in enumerate(boxes, 1):
        if box is None:
            continue
        pad = max(radii) + 12
        sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                   for b, n in zip(box, arr.shape))
        sub = arr[sl]
        m = sub == i
        others = (sub > 0) & ~m
        if not others.any():
            continue
        near = ndi.distance_transform_edt(~others, sampling=spacing) <= near_mm
        # Two operators, because the artefact has two parts.
        #
        # An opening removes what is THIN: the feathered edge of the bridge and
        # the notch's counterpart. It does NOT remove the proximal nub -- see
        # docs/wishlist.md, which records the six things that do not.
        pick = None
        for r in sorted(radii, reverse=True):
            bridge = (m & ~ndi.binary_opening(m, ball(r))) & near
            if bridge.sum() <= cap * m.sum():
                pick = (r, bridge)
                break
        if pick is None:
            continue
        r, bridge = pick
        out[sl][bridge] = 0
        removed += int(bridge.sum())
        chosen[i] = r
    return out, removed, chosen


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
    # De-bridged ONCE, up front, and reused for both this tooth's mask and the
    # neighbour mask it is kept out of. Cleaning only the tooth being meshed
    # would remove its disc and leave the notch its neighbour cuts into it.
    labels = {}
    vox_mm3 = float(np.prod(v.spacing))
    for arch in ("upper", "lower"):
        raw = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        labels[arch], cut, rad = debridge(raw, np.array(v.spacing, float))
        rs = ", ".join(f"r={r}x{sum(1 for x in rad.values() if x == r)}"
                       for r in sorted(set(rad.values()), reverse=True))
        print(f"contact bridge   {arch}: {cut * vox_mm3:.1f} mm3 trimmed "
              f"from {len(rad)} teeth  ({rs})")
    all_teeth = (labels["upper"] > 0) | (labels["lower"] > 0)
    vox = float(np.prod(v.spacing))
    out_report = {}
    x_lo, x_hi = [], []
    print(f"{'Univ':>4s} {'FMA':>9s} {'mask mm3':>9s} {'raw tris':>9s} "
          f"{'final':>7s}  {'side':>5s}")
    for arch in ("upper", "lower"):
        if arch not in rep:
            continue
        arr = labels[arch]
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
            w = np.clip((far - PARTITION_MM / 0.16) / 6.0, 0.0, 1.0)
            shape_field = SURFACE_HU + 900.0 * (occ - 0.5 - CONTACT_EPS * (1.0 - w))
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
            # Stripped BEFORE decimation, so the triangle budget is spent on
            # the tooth rather than shared with an internal shell.
            verts, faces, stray = keep_solid(verts, faces)
            verts, faces = decimate(verts, faces, target)
            verts = taubin(verts, faces, SMOOTH_AFTER)
            v1 = mesh_volume(verts, faces)
            if stray and max(stray) > MAX_STRAY_FRAC * v1:
                raise SystemExit(
                    f"{t['fma']} (Universal {t['universal']}): the mesher "
                    f"returned a stray component of {max(stray):.1f} mm3 "
                    f"against a tooth of {v1:.1f} -- too large to be an "
                    f"artefact. Look at the mask before discarding it.")
            shrink = 100.0 * (1.0 - v1 / v0) if v0 else 0.0
            path = os.path.join(outdir, f"{t['fma']}.stl")
            write_binary_stl(path, verts, faces)
            cx = float(verts[:, 0].mean())
            expect = t.get("side") or ("left" if t["world"][0] > 0 else "right")
            x_lo.append(float(verts[:, 0].min()))
            x_hi.append(float(verts[:, 0].max()))
            out_report[t["fma"]] = dict(universal=t["universal"], arch=arch,
                                        mask_mm3=t["mm3"], raw_triangles=raw,
                                        triangles=int(len(faces)),
                                        mesh_mm3=round(v1, 1),
                                        shrink_pct=round(shrink, 2),
                                        centroid_x=round(cx, 2), expect=expect,
                                        stray_parts=len(stray),
                                        stray_mm3=round(float(sum(stray)), 2))
            note = (f"  stray {len(stray)} ({sum(stray):.1f} mm3 dropped)"
                    if stray else "")
            print(f"{t['universal']:4d} {t['fma']:>9s} {t['mm3']:9.1f} {raw:9,d} "
                  f"{len(faces):7,d}  {expect:>5s}  shrink {shrink:+5.1f}%{note}")
    # Laterality against the DENTAL MIDLINE, not the scanner origin.
    #
    # This used to test cx > 0, which asks whether a tooth is left of the
    # SCANNER's zero -- and the operator's arch sits 3.6 mm to their left of it,
    # head position rather than anatomy. So the lower right central incisor, a
    # tooth that straddles the midline anyway, reported *** SIDE MISMATCH ***
    # while sitting a healthy 3.3 mm on its correct side. build-assets.mjs has
    # always measured against the midline taken from the teeth's own extent, and
    # its comment explains why at length; this now agrees with it, so the two
    # cannot disagree about what laterality means. A warning that cries wolf on
    # a correct tooth is worse than no warning: invariant 1 is the one check
    # that must never be waved through.
    midline = (min(x_lo) + max(x_hi)) / 2 if x_lo else 0.0
    bad = []
    for fma, r in out_report.items():
        rel = r["centroid_x"] - midline
        r["side"] = "left" if rel > 0 else "right"
        r["centroid_x_rel_midline"] = round(rel, 2)
        if r["side"] != r["expect"]:
            bad.append(f"{fma} (Universal {r['universal']}): expected "
                       f"{r['expect']}, centroid sits {rel:+.2f} mm from the "
                       f"dental midline at x={midline:+.2f}")
    print(f"\nlaterality      dental midline x={midline:+.2f} mm")
    if bad:
        print("*** SIDE MISMATCH ***")
        for b in bad:
            print("  " + b)
        raise SystemExit("laterality check failed -- see invariant 1")
    print(f"                OK -- all {len(out_report)} teeth on the expected side")

    with open(os.path.join(outdir, "teeth.json"), "w") as f:
        json.dump(out_report, f, indent=2)
    tot = sum(r["triangles"] for r in out_report.values())
    print(f"\n{len(out_report)} teeth, {tot:,} triangles "
          f"(BodyParts3D equivalent: 198,846)")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
