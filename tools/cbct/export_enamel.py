#!/usr/bin/env python3
"""Mesh the enamel cap of all 28 teeth, at the atlas's polygon budget.

WHY THIS IS NOT export_teeth.py WITH A DIFFERENT MASK. A tooth is meshed from
the GREY LEVELS, because the tooth borders space and there is a real density
edge to find. The enamel cap has two surfaces and only one of them is like that:

  its OUTER surface IS the crown surface, a real density edge, and
  its INNER surface is the DEJ, which at 0.16 mm is NOT a findable edge --
      enamel and coronal dentin overlap in density badly enough that thresholding
      for it is the failure enamel.py exists to avoid (see that file's header).

So the cap is meshed from its own smoothed OCCUPANCY rather than from the
intensity field. That is the honest choice: the inner boundary is derived from
the published thickness envelope, not measured, and meshing it off grey levels
would dress a derived surface up as a measured one. The outer surface loses a
little sharpness by being treated the same way, which is the price.

PROVENANCE, and it is not uniform across the mesh: the cap's EXTENT is bounded
by the measured CEJ ring and the measured crown surface; its THICKNESS is the
literature envelope with the image choosing within it. It ships as `derived`.
Per-tooth VOLUME and %-of-crown must NOT be quoted as measured quantities -- the
contact re-cut moved them by up to 20% and 14.4 points respectively (open
question 5). The thickness figures at the literature's own sites are robust
(median 0.03 mm under the same re-cut) and those are what enamel_audit.py
reports.

Usage: export_enamel.py <volume.nrrd> <split-dir> <out-dir> [target-tris]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage import measure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from segment_tooth import write_binary_stl                 # noqa: E402
from meshsmooth import taubin, mesh_volume                 # noqa: E402
import enamel as EN                                        # noqa: E402

TARGET_TRIS = 3000        # a cap is simpler than a whole tooth
# SMOOTHING IS TUNED FOR A THIN SHELL, NOT A SOLID, and that is why these are
# far below export_teeth.py's 26 passes. Blurring a feather-edged shell and then
# thresholding at 0.5 ERODES it: measured against the cap mask, sigma 1.1 with
# 20 Taubin passes lost 40.6% of the volume of tooth 25 and 30.7% of tooth 24,
# while barely touching a molar (4.9% on 14). The loss tracked cap thinness
# exactly -- incisors 26.6% median against molars 8.3% -- so it was the mesher
# thinning the tissue, not the tissue being thin. At 0.6/8 the same teeth lose
# 7.5% and 5.0%, and no tooth exceeds 7.5%.
#
# The price is a little marching-cubes terracing, since 0.6 voxels is a 0.096 mm
# blur. That is the right side of the trade for a layer whose entire claim is
# THICKNESS: a visibly stepped surface is honest about the voxel grid, whereas a
# smooth cap 40% thinner than the tissue is not.
SMOOTH_BEFORE = 8
SMOOTH_AFTER = 4
OCC_SIGMA = 0.6           # voxels; see above
MAX_STRAY_FRAC = 0.08     # a cap may legitimately be several cusp islands,
                          # so this is looser than the tooth's 0.06 -- but a
                          # component this large is still reported, never
                          # silently dropped


def decimate(verts, faces, target):
    import fast_simplification
    if len(faces) <= target:
        return verts, faces
    v, f = fast_simplification.simplify(verts.astype(np.float32),
                                        faces.astype(np.int32),
                                        1.0 - target / len(faces))
    return np.asarray(v, np.float64), np.asarray(f, np.int64)


def components(verts, faces):
    """Split a mesh into connected shells, largest first, with volumes."""
    n = len(verts)
    adj = [[] for _ in range(n)]
    for i, f in enumerate(faces):
        for a in f:
            adj[a].append(i)
    seen = np.zeros(len(faces), bool)
    out = []
    for s in range(len(faces)):
        if seen[s]:
            continue
        stack, grp = [s], []
        seen[s] = True
        while stack:
            fi = stack.pop()
            grp.append(fi)
            for a in faces[fi]:
                for nb in adj[a]:
                    if not seen[nb]:
                        seen[nb] = True
                        stack.append(nb)
        idx = np.array(grp)
        used = np.unique(faces[idx])
        remap = -np.ones(n, np.int64)
        remap[used] = np.arange(len(used))
        out.append((verts[used], remap[faces[idx]]))
    out.sort(key=lambda vf: -abs(mesh_volume(vf[0], vf[1])))
    return out


def main():
    vol_path, split_dir, outdir = sys.argv[1:4]
    target = int(sys.argv[4]) if len(sys.argv) > 4 else TARGET_TRIS
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    roi_full = v.data.astype(np.float32)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    vox = float(np.prod(sp))

    report = {}
    skipped = {}
    print(f"{'Univ':>4} {'FMA':>9} {'type':>9} {'cap mm3':>8} {'raw':>7} "
          f"{'final':>6} {'shells':>6} {'scallop':>8}")
    print("-" * 68)
    for arch in ("upper", "lower"):
        if arch not in rep:
            continue
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            tgt = np.array(t["world"][:2])
            best = min(ids, key=lambda s: float(np.hypot(
                v.world(cents[s-1][2], cents[s-1][1], cents[s-1][0])[0] - tgt[0],
                v.world(cents[s-1][2], cents[s-1][1], cents[s-1][0])[1] - tgt[1])))
            box = boxes[best - 1]
            pad = 10
            sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                       for b, n in zip(box, arr.shape))
            m = np.zeros(tuple(x.stop - x.start for x in sl), bool)
            m[tuple(slice(b.start - x.start, b.stop - x.start)
                    for b, x in zip(box, sl))] = arr[box] == best
            solid = m.copy()
            for k in range(m.shape[0]):
                if m[k].any():
                    solid[k] = ndi.binary_fill_holes(m[k])
            nb = (arr[sl] > 0) & (arr[sl] != best)
            uni = t["universal"]
            cap, meta = EN.enamel_mask(roi_full[sl], solid, arch, uni, sp,
                                       neighbours=nb)
            if not cap.any():
                print(f"{uni:4d} {t['fma']:>9} {EN.tooth_type(uni):>9}  no cap")
                continue
            # A CROWNED TOOTH HAS NO NATURAL ENAMEL AND MUST NOT SHIP A CAP.
            # 19 and 30 carry zirconia: their enamel was prepped away before the
            # crown was cemented, so whatever survives the envelope here is
            # residue, not tissue. The numbers are not close -- cap 11.0 and
            # 31.0 mm3 against 215-290 for the other molars, with 344.7 and
            # 276.7 mm3 of restoration against <=0.16 for every natural tooth.
            # Emitting those would assert enamel that is not in the mouth, which
            # is the one thing this atlas may not do. They are omitted from the
            # layer and the manifest, and the omission is the claim.
            if meta.get("obscured"):
                skipped[t["fma"]] = dict(universal=uni, cap_mm3=round(cap.sum()*vox, 2),
                                         restoration_mm3=meta.get("restoration_mm3"))
                print(f"{uni:4d} {t['fma']:>9} {EN.tooth_type(uni):>9} "
                      f"{cap.sum()*vox:8.1f}  CROWNED -- no natural enamel, omitted "
                      f"({meta.get('restoration_mm3')} mm3 restoration)")
                continue

            occ = ndi.gaussian_filter(cap.astype(np.float32), OCC_SIGMA)
            try:
                verts, faces, _, _ = measure.marching_cubes(occ, level=0.5)
            except (ValueError, RuntimeError) as e:
                print(f"{uni:4d} {t['fma']:>9}  mesh failed: {e}")
                continue
            raw = len(faces)
            # index (z,y,x) -> world (x,y,z)
            verts = np.column_stack([
                v.origin[0] + (verts[:, 2] + sl[2].start) * sp[0],
                v.origin[1] + (verts[:, 1] + sl[1].start) * sp[1],
                v.origin[2] + (verts[:, 0] + sl[0].start) * sp[2]])
            verts = taubin(verts, faces, SMOOTH_BEFORE)
            shells = components(verts, faces)
            v_all = abs(mesh_volume(verts, faces))
            dropped = [abs(mesh_volume(a, b)) for a, b in shells[1:]]
            big = [d for d in dropped if d > MAX_STRAY_FRAC * v_all]
            verts, faces = shells[0]
            verts, faces = decimate(verts, faces, target)
            verts = taubin(verts, faces, SMOOTH_AFTER)
            v1 = abs(mesh_volume(verts, faces))
            path = os.path.join(outdir, f"{t['fma']}-enamel.stl")
            write_binary_stl(path, verts, faces)
            report[f"{t['fma']}-enamel"] = dict(
                universal=uni, arch=arch, tooth=t["fma"],
                type=EN.tooth_type(uni), cap_mm3=round(cap.sum() * vox, 2),
                mesh_mm3=round(v1, 2), triangles=int(len(faces)),
                raw_triangles=raw, shells=len(shells),
                dropped_mm3=[round(d, 2) for d in dropped],
                scalloped_cej=meta.get("scalloped_cej"),
                cej_scallop_mm=meta.get("cej_scallop_mm"),
                obscured=meta.get("obscured"),
                restoration_mm3=meta.get("restoration_mm3"))
            note = f"  *** {len(big)} large shell(s) dropped ***" if big else ""
            print(f"{uni:4d} {t['fma']:>9} {EN.tooth_type(uni):>9} "
                  f"{cap.sum()*vox:8.1f} {raw:7,d} {len(faces):6,d} "
                  f"{len(shells):6d} {str(meta.get('cej_scallop_mm')):>8}{note}")

    with open(os.path.join(outdir, "enamel.json"), "w") as f:
        json.dump(dict(caps=report, omitted_crowned=skipped), f, indent=2)
    tot = sum(r["triangles"] for r in report.values())
    print(f"\n{len(report)} caps, {tot:,} triangles -> {outdir}")
    for fma, r in sorted(skipped.items(), key=lambda kv: kv[1]["universal"]):
        print(f"omitted  {fma} (Universal {r['universal']}): crowned, "
              f"{r['restoration_mm3']} mm3 restoration")


if __name__ == "__main__":
    main()
