#!/usr/bin/env python3
"""Build the pulp: a thresholded chamber, plus a canal TREE swept into geometry.

Replaces pulp_connect.py's accumulate-and-filter approach. The architecture is
two claims, kept apart:

  ABOVE THE CHAMBER FLOOR   thresholded radiolucency, opened to drop speckle.
                            The chamber is wide enough to resolve, so the image
                            is allowed to say what shape it is.
  BELOW THE CHAMBER FLOOR   the canal tree and nothing else. A canal is 1-3
                            voxels across; thresholding there returns speckle,
                            not anatomy, and every artefact this module used to
                            emit -- the fragments needing bridges, the
                            crunchiness, the dead-end twigs read as branches --
                            grew from pretending otherwise.

There is deliberately no bridging, no despeckling and no per-voxel repair. If
the output is wrong the tree is wrong; fix it there.

Usage: pulp_build.py <vol.nrrd> <split-dir> <pulp.json> <out-dir>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.graph import MCP_Geometric
from skimage.measure import marching_cubes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from segment_tooth import write_binary_stl                 # noqa: E402
from meshsmooth import taubin                              # noqa: E402
from export_teeth import decimate                          # noqa: E402
import pulp_solid as PS                                    # noqa: E402
import canal_tree as CT                                    # noqa: E402
from pulp_connect import (                                 # noqa: E402
    find_orifices, apical_roots, surface_of, cost_field, mesh_field,
    mesh_components, occlusal_clearance, CHAMBER_MIN_DEPTH_MM,
    OCCLUSAL_BAND_FRAC, PULP_FRACTION_MAX, FLOOR_AREA_FRAC,
    CHAMBER_FLOOR_OVERLAP_MM, TRI_BUDGETS,
)

CHAMBER_OPEN_ITER = 1
# THE CHAMBER FLOOR COMES FROM THE TOOTH, NOT FROM THE PULP'S OWN AREA PROFILE.
# The old rule -- most apical slice where the PULP still has 35% of its maximum
# cross-section -- works on a molar, whose chamber is plainly wider than its
# canals, and fails completely on a single-canal tooth, where chamber and canal
# are barely different in width. On the anteriors it put the "floor" at 74-82%
# of tooth length, so nearly the whole root was thresholded chamber rather than
# a smooth canal tube: the operator sees lumpy ribbons with lateral knobs, and a
# hole through one of them, which is exactly what a thresholded 0.16 mm
# structure looks like.
#
# The cervical narrowing is a property of the TOOTH and is unambiguous on every
# tooth type: walk apically from the crown's widest slice to the first slice
# holding less than CERVICAL_FRAC of that maximum. It lands at 0.46-0.55 of
# tooth length on anteriors and 0.25-0.36 on molars, which is where a CEJ
# belongs. Everything below is canal, and canals are swept tubes.
CERVICAL_FRAC = 0.80
# ...and never deeper than this fraction of the tooth. A canine tapers so
# gradually that the 0.80 area test lands at 55% of its length, giving teeth 22
# and 27 chambers of 28 and 23 mm3 -- larger than most molars', which is plainly
# wrong for a single-rooted tooth. A crown is at most about 45% of a tooth.
MAX_CHAMBER_FRAC = 0.45
# ...BUT ONLY ON A SINGLE-ROOTED TOOTH. A molar's pulp chamber sits BELOW the
# cervical line, between it and the furcation, so cutting at the CEJ deletes the
# chamber outright -- tooth 30 came out with 0.0 mm3 of chamber and 48 mm3 of
# canal. On a multi-rooted tooth the floor is the FURCATION: walking apically,
# the first slice at which the tooth's own cross-section splits into separate
# roots. Both landmarks are read from the tooth mask, not from the pulp.
OPERATOR_CANALS = {4: 2, 13: 2}

# PULP AS A FRACTION OF THE TOOTH -- APPLIED TO THE PULP, NOT TO THE LUMEN.
# `PULP_FRACTION_MAX` capped the LUMEN and the result was then multiplied by
# SHADING_SCALE (2.12), so the effective ceiling on the pulp cavity was 8.3% of
# tooth volume and teeth 3, 5 and 31 came out at 7.0-7.8%. The literature figure
# is for the pulp CAVITY itself: a canine measures 22-29 mm3 of pulp in a 745
# mm3 tooth, i.e. 3.9%. Cap the pulp directly at that, and the whole-dentition
# total lands near the ~760 mm3 published for 28 teeth rather than double it.
PULP_FRACTION_OF_TOOTH = 0.040
RENDER_SIGMA = 0.9
FLOOR = 0.55


def pulp_field(chamber, canal, sigma=RENDER_SIGMA):
    """Smoothed occupancy, with the isolevel floor applied to CANALS ONLY.

    `mesh_field` floors every voxel thinner than about 1.5 voxels so that a
    canal -- which is thinner than that everywhere -- survives smoothing. Applied
    to the whole pulp it also guarantees that every one-voxel spur on the
    thresholded chamber survives into the mesh, which is what the operator sees
    as spikes on the chambers. Chambers are thick and have no need of it: the
    Gaussian is what makes them smooth, and letting it work is the point.
    """
    both = chamber | canal
    # The JUNCTION needs the floor too. Where a canal meets the chamber the
    # voxels belong to the chamber, so flooring the canal alone let smoothing
    # thin that neck away and two teeth arrived in pieces.
    keep = ndi.binary_dilation(canal, ndi.generate_binary_structure(3, 1)) & both
    f = ndi.gaussian_filter(both.astype(np.float32), sigma)
    np.maximum(f, np.where(keep, FLOOR, 0.0).astype(np.float32), out=f)
    return f


def decimate_connected(verts, faces):
    for target in TRI_BUDGETS:
        v, f = decimate(verts, faces, target)
        if mesh_components(v, f) == 1:
            return v, f, target
    return verts, faces, len(faces)


def main():
    vol_path, split_dir, pulp_json, outdir = sys.argv[1:5]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    roi_full = v.data.astype(np.float32)
    vox = float(np.prod(sp))
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    pulp = json.load(open(pulp_json))

    report, devs = {}, []
    n_canals_total = n_joins = 0
    print(f"{'Univ':>4s} {'orf':>3s} {'canals':>6s} {'foram':>5s} "
          f"{'chamber':>7s} {'canal':>6s} {'total mm3':>9s} {'tris':>6s}")
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
            pulp_hu = float(rec.get("pulp_density_hu", PS.PULP_FALLBACK_HU))

            m_solid = m.copy()
            for k in range(m.shape[0]):
                if m[k].any():
                    m_solid[k] = ndi.binary_fill_holes(m[k])

            # --- domain: no pulp near the occlusal surface, none in the
            # coronal shell. Same constraints as before; they were right.
            _d = ndi.distance_transform_edt(m_solid, sampling=tuple(sp))
            _zs = np.where(m_solid.any(axis=(1, 2)))[0]
            _mid = (int(_zs.min()) + int(_zs.max())) // 2
            coronal = np.zeros_like(m_solid)
            if arch == "upper":
                coronal[:_mid] = True
            else:
                coronal[_mid:] = True
            # CLEARANCE IS MEASURED FROM THE CUSP TIP ALONG THE AXIS, not as a
            # 3-D distance to the nearest occlusal surface. The literature
            # figure (5.59 mm on a maxillary first molar) is cusp tip to pulp
            # horn down the tooth. Measuring to the NEAREST surface instead
            # penalises a horn sitting under a fissure, where the surface dips
            # between the cusps and is far closer than the cusp tip -- 69% of
            # the radiolucency the model was failing to cover lay inside this
            # exclusion, and overlaying the model on the CBCT showed pulp horns
            # plainly visible in the scan with no model in them.
            _crown = int(_zs.min()) if arch == "upper" else int(_zs.max())
            _clear = int(round(occlusal_clearance(num) / float(sp[2])))
            deep_enough = np.zeros_like(m_solid)
            if arch == "upper":
                deep_enough[_crown + _clear:] = True
            else:
                deep_enough[:max(_crown - _clear + 1, 0)] = True
            domain = (m_solid
                      & ~(coronal & (_d < CHAMBER_MIN_DEPTH_MM))
                      & deep_enough)

            # --- chamber, calibrated then cut at its own floor
            cross = ndi.generate_binary_structure(3, 1)

            def chamber_at(frac):
                c = ndi.binary_opening(
                    PS.solid_pulp(sub, m, sp, pulp_hu, None, arch, frac=frac)
                    & domain, cross, iterations=CHAMBER_OPEN_ITER)
                # FACE connectivity. A corner touch is one component to
                # ndi.label with a 3x3x3 structure and two to the mesher, and
                # picking the "largest" under 26-connectivity therefore keeps
                # pieces that arrive detached. CLAUDE.md rule 18; walked into
                # again here.
                cl, cn = ndi.label(c, structure=ndi.generate_binary_structure(3, 1))
                if cn > 1:
                    csz = ndi.sum(c, cl, range(1, cn + 1))
                    c = cl == (int(np.argmax(csz)) + 1)
                return c

            target = rec.get("total_lumen_mm3")
            want = target * PS.SHADING_SCALE if target else None
            tooth_mm3 = rec.get("tooth_mm3")
            if want and tooth_mm3:
                want = min(want, PULP_FRACTION_OF_TOOTH * tooth_mm3)
            def cervical_z():
                tz = np.where(m_solid.any(axis=(1, 2)))[0]
                if tz.size < 4:
                    return None
                area = np.array([int(m_solid[k].sum()) for k in tz])
                order = np.arange(len(tz)) if arch == "upper" \
                    else np.arange(len(tz))[::-1]
                a, zz = area[order], tz[order]        # crown -> apex
                imax = int(np.argmax(a))
                cap = int(MAX_CHAMBER_FRAC * len(a))
                for i in range(imax, len(a)):
                    if a[i] < CERVICAL_FRAC * a.max():
                        return int(zz[min(i, cap)])
                return int(zz[cap]) if cap < len(a) else None

            def furcation_z():
                tz = np.where(m_solid.any(axis=(1, 2)))[0]
                if tz.size < 4:
                    return None
                # START BELOW THE CERVICAL LINE. Walking from the crown finds
                # the CUSPS, which are separate components at the occlusal
                # surface, so the "furcation" came out near the crown and the
                # chamber was deleted -- every multi-rooted tooth was skipped
                # for having no chamber left.
                cz = cervical_z()
                order = tz if arch == "upper" else tz[::-1]   # crown -> apex
                if cz is not None:
                    order = [k for k in order
                             if (k >= cz if arch == "upper" else k <= cz)]
                F = ndi.generate_binary_structure(2, 1)
                for k in order:
                    lab, n = ndi.label(m_solid[k], structure=F)
                    if n >= 2:
                        szs = ndi.sum(m_solid[k], lab, range(1, n + 1))
                        if (szs >= 120).sum() >= 2:      # two real roots, not specks
                            return int(k)
                return None

            def cut_floor(ch):
                fz = furcation_z() if len(roots) > 1 else None
                if fz is None:
                    fz = cervical_z()
                if fz is None:
                    return ch
                if arch == "upper":
                    ch[fz + 1:] = False
                else:
                    ch[:fz] = False
                # Cutting can SPLIT the chamber: parts of the coronal pulp are
                # joined only through voxels below the floor. FACE connectivity
                # -- a corner touch is one component to a 3x3x3 structure and
                # two to the mesher (rule 18).
                cl, cn = ndi.label(ch, structure=ndi.generate_binary_structure(3, 1))
                if cn > 1:
                    csz = ndi.sum(ch, cl, range(1, cn + 1))
                    ch = cl == (int(np.argmax(csz)) + 1)
                return ch

            roots = apical_roots(m_solid, arch, sp)

            # CALIBRATE THE CUT CHAMBER, NOT THE UNCUT ONE.
            # The search used to measure chamber_at(mid) and then cut_floor()
            # removed a chunk from the shipped result, so every tooth landed
            # BELOW its target -- teeth 9, 11 and 22 came out at 12.8, 14.7 and
            # 15.0 mm3 against targets of 21.1, 27.0 and 24.8, which is the
            # coronal under-fill the overlay sheets show. The domain was never
            # the limit: at the loosest threshold these chambers could reach
            # 100-300 mm3. Same trap as calibrating before closing and filling.
            if want:
                lo, hi = 0.25, 1.80
                for _ in range(12):
                    mid = 0.5 * (lo + hi)
                    if cut_floor(chamber_at(mid)).sum() * vox > want:
                        lo = mid
                    else:
                        hi = mid
                chamber = cut_floor(chamber_at(0.5 * (lo + hi)))
            else:
                chamber = cut_floor(chamber_at(0.5))


            # --- the canal tree
            # The operator has identified two canals in teeth 4 and 13 --
            # maxillary SECOND premolars, which pulp.json lists as single-canal.
            # Two canals occur in roughly half of them, and a clinician reading
            # their own periapicals is better evidence than the default prior.
            n_canals = int(rec.get("canal_count_prior",
                                   len(rec.get("canals", [])) or 1))
            n_canals = max(n_canals, OPERATOR_CANALS.get(num, 0))
            orf = find_orifices(chamber, domain, sub, sp, arch, n_canals)
            dentin = float(np.percentile(sub[m], 45))
            cost = cost_field(sub, domain, pulp_hu, dentin)
            mcp = MCP_Geometric(cost, sampling=tuple(float(x) for x in sp[::-1]))
            starts = np.argwhere(chamber)
            if not len(starts) or not orf or not roots:
                print(f"{num:4d}   no chamber/orifices/roots -- skipped")
                continue
            cumulative, _ = mcp.find_costs([tuple(p) for p in starts])
            cdist = ndi.distance_transform_edt(chamber, sampling=tuple(sp))
            # Name each root (mb/db/p, b/p, m/d) so the per-root canal quota
            # can be applied. Identity comes from the root's own position
            # relative to the arch, not from a table of tooth numbers.
            def root_world(r):
                c = np.argwhere(r).mean(0)
                return v.world(origin_idx[0] + c[2], origin_idx[1] + c[1],
                               origin_idx[2] + c[0])

            root_names = CT.identify_roots(roots, t["world"], root_world, arch,
                                           len(roots))
            cstats = {}

            def build(ch):
                cd = ndi.distance_transform_edt(ch, sampling=tuple(sp))
                tr, fo = CT.build_canals(
                    lambda c: MCP_Geometric(
                        c, sampling=tuple(float(x) for x in sp[::-1])),
                    cost, domain, sp, arch, roots, orf, cd, cumulative,
                    surface_of(m_solid), chamber=ch, roi=sub,
                    universal=num, root_names=root_names, stats=cstats)
                return tr, fo, CT.voxelize(tr, m_solid.shape, sp, limit=domain)

            tree, foramina, canal = build(chamber)
            # SPLIT THE BUDGET WITH THE CANALS, DON'T GIVE IT ALL TO THE CHAMBER.
            # Calibrating the chamber to the whole pulp volume and then adding
            # canals on top left the chamber holding 85-95% of the total and
            # visibly too big. The canal volume is known after one pass, so the
            # chamber is recalibrated against what remains and the tree rebuilt
            # on the corrected chamber.
            if want:
                cv = canal.sum() * vox
                want_ch = max(want - cv, 0.30 * want)
                lo, hi = 0.25, 1.80
                for _ in range(12):
                    mid = 0.5 * (lo + hi)
                    if cut_floor(chamber_at(mid)).sum() * vox > want_ch:
                        lo = mid
                    else:
                        hi = mid
                chamber = cut_floor(chamber_at(0.5 * (lo + hi)))
                if chamber.any():
                    tree, foramina, canal = build(chamber)

            # HONOUR THE VOLUME CAP EVEN WHEN THE THRESHOLD CANNOT.
            # solid_pulp unions `enclosed_void` -- the hole in the segmentation
            # mask -- which does not depend on the threshold at all, so it is a
            # hard floor: tooth 3 could not go below 55 mm3 of chamber against a
            # 44 mm3 budget and landed at 7.0% of tooth volume, against ~3.9% in
            # the literature. Erode the chamber until the total fits.
            if want:
                guard = 0
                while (chamber | canal).sum() * vox > want and guard < 6:
                    er = ndi.binary_erosion(
                        chamber, ndi.generate_binary_structure(3, 1))
                    if not er.any():
                        break
                    cl, cn = ndi.label(
                        er, structure=ndi.generate_binary_structure(3, 1))
                    if cn > 1:
                        csz = ndi.sum(er, cl, range(1, cn + 1))
                        er = cl == (int(np.argmax(csz)) + 1)
                    chamber = er
                    guard += 1
                if guard:
                    tree, foramina, canal = build(chamber)

            n_canals_total += len(foramina)
            n_joins += sum(1 for i, p in enumerate(tree.parent)
                           if p >= 0 and p != i - 1)

            both = chamber | canal
            # A canal the tree could not actually realise -- clipped by the root
            # confinement, or anchored to a chamber region it never reaches --
            # leaves an orphan fragment. Drop it rather than ship a mesh in
            # pieces, and SAY SO: a silently discarded canal is worse than a
            # visible one, because it looks like the anatomy is simply absent.
            lab_, n_ = ndi.label(both, structure=ndi.generate_binary_structure(3, 1))
            if n_ > 1:
                szs_ = ndi.sum(both, lab_, range(1, n_ + 1))
                keep_ = int(np.argmax(szs_)) + 1
                lost = (both.sum() - szs_[keep_ - 1]) * vox
                both = lab_ == keep_
                canal = canal & both
                print(f"     tooth {num}: dropped {n_ - 1} unrealised canal "
                      f"fragment(s), {lost:.2f} mm3")
            if both.sum() < 40:
                print(f"{num:4d}   too little pulp")
                continue

            # Prefer the canal-only floor, which lets the Gaussian smooth the
            # chamber. If that thins an internal neck below the isolevel and the
            # surface comes apart, fall back to flooring every thin voxel --
            # a slightly spikier chamber beats a mesh in pieces.
            f = pulp_field(chamber, canal)
            verts, faces, _, _ = marching_cubes(f, level=0.5)
            if mesh_components(verts, faces) > 1:
                # A thin neck inside a narrow chamber smooths below the isolevel
                # and the surface parts. Falling straight back to the full floor
                # fixes that but keeps every chamber spur -- it was firing on
                # teeth 4, 9, 23 and 28, which is precisely the scraggly-incisor
                # list. CLOSE the chamber first: that thickens the neck without
                # extending spurs, since a spur is thin in every direction.
                chamber = ndi.binary_closing(
                    chamber, ndi.generate_binary_structure(3, 2), iterations=2)
                chamber &= domain
                both = chamber | canal
                f = pulp_field(chamber, canal)
                verts, faces, _, _ = marching_cubes(f, level=0.5)
                if mesh_components(verts, faces) > 1:
                    print(f"     tooth {num}: full floor (chamber spikier)")
                    f = mesh_field(both)
                    verts, faces, _, _ = marching_cubes(f, level=0.5)
            world = np.empty_like(verts)
            world[:, 0] = v.origin[0] + (origin_idx[0] + verts[:, 2]) * sp[0]
            world[:, 1] = v.origin[1] + (origin_idx[1] + verts[:, 1]) * sp[1]
            world[:, 2] = v.origin[2] + (origin_idx[2] + verts[:, 0]) * sp[2]
            # 10 -> 30 passes. Measured on the dihedral angle between adjacent
            # faces (the only metric here that tracks bumpiness at all --
            # area/volume^(2/3) is dominated by the thin canals hanging off the
            # chamber and was blind to it): mean angle 12.8 -> 11.5 degrees.
            # Taubin is volume-preserving, so the canals do not thin; volume
            # moved +2% at 70 passes. This is a real but MODEST improvement and
            # should not be mistaken for a fix if the chambers still read wrong.
            world = taubin(world, faces, 30)
            world, faces, budget = decimate_connected(world, faces)
            world = taubin(world, faces, 8)
            write_binary_stl(os.path.join(outdir, f"{fma}-pulp.stl"), world, faces)
            np.save(os.path.join(outdir, f"{fma}-pulp.npy"), both)

            recs = []
            for ex, ap, ri in foramina:
                ew = v.world(origin_idx[0] + ex[2], origin_idx[1] + ex[1],
                             origin_idx[2] + ex[0])
                aw = v.world(origin_idx[0] + ap[2], origin_idx[1] + ap[1],
                             origin_idx[2] + ap[0])
                dev = float(np.linalg.norm(np.asarray(ew) - np.asarray(aw)))
                devs.append(dev)
                recs.append(dict(world_lps=[float(q) for q in ew],
                                 root_apex_lps=[float(q) for q in aw],
                                 apex_deviation_mm=round(dev, 3),
                                 radius_mm=CT.FORAMEN_R_MM, root=int(ri),
                                 source="tree", provenance="DERIVED"))
            print(f"{num:4d} {len(orf):3d} {len(foramina):6d} {len(recs):5d} "
                  f"{chamber.sum() * vox:7.1f} {canal.sum() * vox:6.1f} "
                  f"{both.sum() * vox:9.1f} {len(faces):6d}")
            if any(cstats.get(k) for k in ("roots_filled", "over_quota_dropped",
                                           "duplicates_dropped")):
                print(f"     tooth {num}: filled {cstats.get('roots_filled', 0)}, "
                      f"dropped {cstats.get('over_quota_dropped', 0)} over-quota"
                      f" + {cstats.get('duplicates_dropped', 0)} duplicate  "
                      f"roots={root_names}")
            report[fma] = dict(universal=num, arch=arch, roots=root_names,
                               quota_filled=cstats.get("roots_filled", 0),
                               quota_dropped=cstats.get("over_quota_dropped", 0),
                               pulp_mm3=round(both.sum() * vox, 2),
                               chamber_mm3=round(chamber.sum() * vox, 2),
                               canal_mm3=round(canal.sum() * vox, 2),
                               orifices=len(orf), tree_nodes=len(tree),
                               foramina=recs)

    if devs:
        d = np.array(devs)
        print(f"\n{len(d)} foramina  deviation from anatomical apex: "
              f"mean {d.mean():.2f} mm, median {np.median(d):.2f}, "
              f"range {d.min():.2f}-{d.max():.2f}")
        print("  literature: mean 0.52 mm, range 0.2-2.0")
    tot = sum(r["pulp_mm3"] for r in report.values())
    print(f"{len(report)} teeth, {tot:.1f} mm3 of pulp")
    json.dump(dict(provenance="chamber MEASURED (thresholded); canals DERIVED "
                              "(orifice and foramen measured, centreline from "
                              "the darkest route, calibre modelled)",
                   teeth=report),
              open(os.path.join(outdir, "pulp-connect.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
