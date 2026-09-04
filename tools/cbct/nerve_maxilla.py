#!/usr/bin/env python3
"""Superior alveolar nerves and the superior dental plexus, maxilla.

THIS IS NOT THE MANDIBULAR CASE AND MUST NOT LOOK LIKE IT.

`nerve.py` hangs the inferior alveolar nerve on a canal this CBCT actually
resolves: the trunk's course is measured, and only its contents are convention.
There is no maxillary equivalent. The posterior, middle and anterior superior
alveolar canals are thin, frequently dehiscent, and not reliably visible at
0.16 mm -- nothing in this volume locates them. So every trunk and every plexus
node here is SCHEMATIC: placed from textbook anatomy relative to structures that
were measured, not observed in the scan.

What IS measured is where each branch ends: the apical foramina, placed by
extrapolating each canal's own trajectory and checked against the literature.
So the honest description of this module is "measured endpoints, invented
path", and the JSON says exactly that. Keep the meshes separate from the
mandibular ones so the UI can render the distinction, and do not let a later
tidy-up merge them into one "nerves" layer -- the whole point is that these two
sets of geometry carry different epistemic weight.

Anatomy modelled:
  PSA  posterior superior alveolar -- enters the posterior maxillary wall and
       supplies the molars (except, classically, the MB root of the first)
  MSA  middle superior alveolar -- premolars and that MB root; INCONSTANT,
       present in roughly a third of people, so it is flagged as optional
  ASA  anterior superior alveolar -- runs forward in the infraorbital canal to
       canine and incisors
All three anastomose in the superior dental plexus above the apices, which is
why the plexus is drawn as a continuous arc rather than three separate trees.

DERIVED AGAINST MALAMED (2026-09-01). docs/wishlist.md's rule for upgrading a
source is that the geometry must be re-derived FIRST and the citation changed
after, because swapping the citation alone credits a book for a course it did
not produce. What changed here, and what did not:

  RE-DERIVED   Every trunk is now CONFINED TO MEASURED BONE. Before this the
      courses were never tested against bone at all, and 73% of this mesh's
      vertices lay outside it -- a median of 3.6 mm and up to 10.6 mm out,
      floating in the sinus. That is the wishlist's "schematic AND floating",
      measured. The bone used is the centred volume's UNION the maxillary
      exposure registered in, which is the first time enough mid-face existed to
      make the test meaningful.
  NOT DERIVED  The courses are still not OBSERVED. They stay `schematic`.

WHAT WAS CHECKED AND CANNOT BE MEASURED, so nobody spends the time again:
  - The infraorbital canal does not resolve. Filling the upper-skull label per
    slice and taking the interior voids returns the sinuses and nasal cavity
    (aspect 1.1-1.7) and no thin tube anywhere.
  - Malamed's mandibular-foramen construction -- 19 mm below the coronoid notch,
    2.75 mm behind the ramus midpoint -- cannot be anchored here. The ramus is
    still cut by the field of view at its posterior border (y 23.7 against a box
    edge of 23.85) even with the mandibular exposure registered in, and the
    condyle was never inside any of the three FOVs. There is no second peak to
    put a notch between.

Usage: nerve_maxilla.py <pulp-connect.json> <split.json> <out-dir>
                        [<centred-pred> <maxillary-pred> <max-transform> <vol>]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from segment_tooth import write_binary_stl
from nerve import tube, branch_curve

PLEXUS_ABOVE_MM = 2.6      # how far beyond the apex the plexus arc sits
PLEXUS_RADIUS_MM = 0.45
BRANCH_RADIUS_MM = 0.30
TRUNK_RADIUS_MM = 0.70
TRUNK_RUN_MM = 12.0        # how far the named trunks run beyond the plexus
BRANCH_TIP_R_MM = 0.12     # at the apical foramen, where the branch meets pulp
IO_RADIUS_MM = (1.05, 0.80)     # infraorbital nerve, posterior -> foramen
IO_ABOVE_MM = 22.0         # the infraorbital canal above the plexus arc
                           # (fallback only; unused where the canal is traced)
ASA_BEHIND_FORAMEN_MM = 7.0   # Malamed: ASA leaves the trunk in the
                           # anterior canal, a few mm short of the foramen

# TOPOLOGY, from the Wikipedia articles on the superior alveolar nerves:
#   V2 trunk, in the pterygopalatine fossa  -> PSA, straight to the tuberosity
#   V2 -> infraorbital nerve, in the infraorbital canal -> MSA (mid-canal) and
#        ASA (about the canal's midpoint, into the canalis sinuosus)
# So MSA and ASA are branches OF the infraorbital nerve and must arise from it,
# not stand free in the sinus. PSA does not: it leaves V2 before the canal.
#   -- /wiki/Posterior_superior_alveolar_nerve, /wiki/Anterior_superior_alveolar_nerve

# Universal numbers, maxillary. Position in the arch drives which trunk supplies
# a tooth; the mapping is the classical one and is stated here rather than
# buried in a conditional.
PSA_TEETH = {2, 3, 15, 14}          # molars
MSA_TEETH = {4, 5, 12, 13}          # premolars (and, classically, 3/14's MB)
ASA_TEETH = {6, 7, 8, 9, 10, 11}    # canine and incisors


def maxilla_bone(pred_c, pred_m, transform, vol_path):
    """Inside-bone test and nearest-inside snap, in world LPS.

    The mask is the centred volume's hard tissue UNION the maxillary exposure's
    upper skull mapped onto the same grid. Filled per slice first: like the
    mandible (rule 108), the teeth are their own class and would otherwise read
    as holes, and a nerve crossing one would be called outside the bone.

    Resampling the maxillary label onto the centred grid loses bone that falls
    outside it -- acceptable here and only here, because this mask is used to
    TEST points that are themselves inside that grid. Do not reuse it to build
    geometry; rule 113 exists for that.
    """
    from scipy import ndimage as ndi
    from read_nifti import read_nifti
    from vol import Volume
    from register import euler

    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    fl, _, _ = read_nifti(pred_c)
    bone = np.isin(fl, (1, 2, 3, 4))
    if pred_m and transform:
        ml, _, _ = read_nifti(pred_m)
        tr = json.load(open(transform))
        R = euler(*np.radians(tr["rotation_deg"]))
        t = np.asarray(tr["translation_mm"]) / sp
        centre = np.array(ndi.center_of_mass(fl == tr["label"]))
        zz, yy, xx = np.indices(bone.shape, dtype=np.float32)
        pts = np.stack([zz - centre[0], yy - centre[1], xx - centre[2]], -1)
        src = pts @ R + centre - t
        extra = ndi.map_coordinates((ml == 1).astype(np.float32),
                                    [src[..., 0], src[..., 1], src[..., 2]],
                                    order=1, mode="constant", cval=0.0) > 0.5
        bone |= extra
    for k in range(bone.shape[0]):
        if bone[k].any():
            bone[k] = ndi.binary_fill_holes(bone[k])
    _, idx = ndi.distance_transform_edt(~bone, return_indices=True)

    def to_idx(w):
        return np.array([(w[2] - v.origin[2]) / sp[2],
                         (w[1] - v.origin[1]) / sp[1],
                         (w[0] - v.origin[0]) / sp[0]])

    def snap(w):
        i = np.round(to_idx(w)).astype(int)
        if np.any(i < 0) or np.any(i >= np.array(bone.shape)):
            return np.asarray(w, float)
        if bone[tuple(i)]:
            return np.asarray(w, float)
        j = idx[(slice(None),) + tuple(i)]
        return np.array([v.origin[0] + j[2] * sp[0],
                         v.origin[1] + j[1] * sp[1],
                         v.origin[2] + j[0] * sp[2]])

    def frac_inside(pts):
        n = ok = 0
        for w in np.atleast_2d(pts):
            i = np.round(to_idx(w)).astype(int)
            n += 1
            if (np.all(i >= 0) and np.all(i < np.array(bone.shape))
                    and bone[tuple(i)]):
                ok += 1
        return ok / max(n, 1)

    return snap, frac_inside


def confine(pts, snap, passes=2):
    """Pull a course into bone, then re-smooth so snapping leaves no staircase.

    Snapping moves only the points that were outside, so a course already in
    bone is untouched and one that was floating is brought to the nearest bone
    rather than redrawn -- the shape it was given from the anatomy survives.
    """
    out = np.array([snap(p) for p in pts])
    for _ in range(passes):
        out[1:-1] = 0.25 * out[:-2] + 0.5 * out[1:-1] + 0.25 * out[2:]
        out = np.array([snap(p) for p in out])
    return out


def arch_order(points):
    """Sort plexus nodes along the arch, right posterior -> anterior -> left.

    Plain atan2 about the centroid puts its branch cut at -x, which for a dental
    arch falls INSIDE the horseshoe: the ordering then jumps from one posterior
    end to the other, and smoothing averages across that jump and drags nodes
    toward the arch centre. It produced a "plexus node" at x = 0.0 sitting in
    the middle of the palate. The arch opens POSTERIORLY, so the angle is
    measured from the anterior direction instead, which places the cut in the
    opening where there is no anatomy to break.
    """
    c = points[:, :2].mean(0)
    ang = np.arctan2(points[:, 0] - c[0], -(points[:, 1] - c[1]))
    return np.argsort(ang)


def smooth(points, passes=4):
    """Chaikin-ish smoothing so the arc reads as a nerve, not a polyline."""
    p = points.copy()
    for _ in range(passes):
        if len(p) < 3:
            break
        q = p.copy()
        q[1:-1] = 0.25 * p[:-2] + 0.5 * p[1:-1] + 0.25 * p[2:]
        p = q
    return p


MEASURED_IO = {}


def measured_io(path):
    """The traced infraorbital canal centrelines, atlas frame, per side.

    Returns {} when the file is absent, so the constructed arc below stays the
    fallback and this module still runs on a tree without the tracing.
    """
    if not path or not os.path.exists(path):
        return {}
    d = json.load(open(path))
    out = {}
    for side, rec in d.get("sides", {}).items():
        pts = np.array([r["p"] for r in rec["points"]], float)
        if len(pts) >= 3:
            out[side] = pts
    return out


def main():
    global MEASURED_IO
    pulp_path, split_path, outdir = sys.argv[1:4]
    # optional 9th argument: the traced infraorbital centrelines
    MEASURED_IO = measured_io(sys.argv[8] if len(sys.argv) >= 9 else
                              os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", "..", "docs", "cbct-infraorbital.json"))
    if MEASURED_IO:
        print(f"infraorbital canal: MEASURED centreline for "
              f"{sorted(MEASURED_IO)} ({len(next(iter(MEASURED_IO.values())))} samples)")
    else:
        print("infraorbital canal: no tracing found, using the constructed arc")
    snap = frac_inside = None
    if len(sys.argv) >= 8:
        snap, frac_inside = maxilla_bone(*sys.argv[4:8])
    os.makedirs(outdir, exist_ok=True)
    teeth = json.load(open(pulp_path))["teeth"]
    split = json.load(open(split_path))
    centre = {t["universal"]: np.array(t["world"], float)
              for t in split["upper"]["teeth"]}

    nodes, targets, owners = [], [], []
    for rec in teeth.values():
        if rec["arch"] != "upper":
            continue
        u = rec["universal"]
        c = centre.get(u)
        for f in rec.get("foramina", []):
            w = np.array(f["world_lps"], float)
            # Beyond the apex, away from the tooth's own centre. Using the
            # tooth axis rather than a global +z keeps the plexus above tilted
            # teeth too, and the maxillary arch is tilted throughout.
            d = w - c if c is not None else np.array([0.0, 0.0, 1.0])
            n = np.linalg.norm(d)
            d = d / n if n > 1e-6 else np.array([0.0, 0.0, 1.0])
            nodes.append(w + d * PLEXUS_ABOVE_MM)
            targets.append(w)
            owners.append(u)
    if not nodes:
        print("no maxillary foramina found")
        return
    nodes = np.array(nodes)
    targets = np.array(targets)
    owners = np.array(owners)

    order = arch_order(nodes)
    arc = smooth(nodes[order])

    allv, allf, off = [], [], 0

    def add(v, f):
        nonlocal off
        allv.append(v)
        allf.append(f + off)
        off += len(v)

    out = tube(arc, np.full(len(arc), PLEXUS_RADIUS_MM))
    if out:
        add(*out)
    if allv:
        write_binary_stl(os.path.join(outdir, "nerve-superior-plexus.stl"),
                         np.vstack(allv), np.vstack(allf))

    # branches: plexus -> each measured foramen
    bv, bf, boff = [], [], 0
    branches = []
    for i in range(len(nodes)):
        k = int(np.argmin(np.linalg.norm(arc - nodes[i][None, :], axis=1)))
        curve = branch_curve(arc[k], targets[i], bulge=0.2)
        o = tube(curve, np.linspace(BRANCH_RADIUS_MM, BRANCH_TIP_R_MM,
                                    len(curve)))
        if not o:
            continue
        v, f = o
        bv.append(v)
        bf.append(f + boff)
        boff += len(v)
        u = int(owners[i])
        branches.append(dict(
            universal=u,
            supply=("PSA" if u in PSA_TEETH else
                    "MSA" if u in MSA_TEETH else
                    "ASA" if u in ASA_TEETH else "unassigned"),
            foramen_lps=[round(float(x), 2) for x in targets[i]],
            length_mm=round(float(np.linalg.norm(arc[k] - targets[i])), 2)))
    if bv:
        write_binary_stl(os.path.join(outdir, "nerve-superior-branches.stl"),
                         np.vstack(bv), np.vstack(bf))

    # THE TRUNKS ARE BILATERAL, AND THE ARC IS A HORSESHOE.
    # Sorting the plexus by angle makes arc[0] and arc[-1] the two POSTERIOR
    # ends -- one per side -- and the middle the anterior midline. Reading them
    # as "one end, middle, other end" put ASA on a molar and MSA across the
    # midline. The arc is split at x = 0 and each side gets its own PSA, MSA and
    # ASA, which is what the anatomy is. Anatomical right is NEGATIVE x
    # (CLAUDE.md invariant 1).
    tv, tf, toff = [], [], 0
    iv, if_, ioff = [], [], 0
    trunks = []
    up = np.array([0.0, 0.0, 1.0])
    for side, keep in (("right", arc[:, 0] < 0), ("left", arc[:, 0] >= 0)):
        half = arc[keep]
        if len(half) < 4:
            continue
        # order this half from anterior (near the midline) to posterior
        half = half[np.argsort(-np.abs(half[:, 0]))][::-1]
        post, mid, ant = half[-1], half[len(half) // 2], half[0]
        lateral = np.array([-1.0, 0, 0]) if side == "right" else np.array([1.0, 0, 0])
        back = half[-1] - half[-3]
        back = back / max(np.linalg.norm(back), 1e-6)
        fwd = half[0] - half[2]
        fwd = fwd / max(np.linalg.norm(fwd), 1e-6)
        # The infraorbital nerve: from the pterygopalatine fossa forward above
        # the tooth apices to the infraorbital foramen. MSA and ASA are hung off
        # it, so the tree reads V2 -> infraorbital -> MSA/ASA, which is the
        # anatomy.
        #
        # The canal IS resolved, and this used to say it was not -- see
        # CLAUDE.md 119 and its correction. Where a tracing exists the course
        # follows it and the nerve becomes `derived`; where none does, the
        # constructed arc below is the fallback and stays `schematic`.
        traced = MEASURED_IO.get(side)
        if traced is not None:
            # MEASURED. The canal was hand-traced on cross-sections cut
            # perpendicular to its own axis in the maxillary exposure, which is
            # the exposure that saw it -- its posterior end reaches z 37.8 and
            # the centred volume's skull stops at 37.2, so part of this canal
            # was never in that reconstruction at all. Resampled to a fixed
            # count so the tube's radius ramp is unchanged, and NOT confined:
            # confine() pushes a course into bone, and this one was measured
            # inside it.
            u = np.concatenate([[0.0], np.cumsum(
                np.linalg.norm(np.diff(traced, axis=0), axis=1))])
            io = np.stack([np.interp(np.linspace(0, u[-1], 30), u, traced[:, k])
                           for k in range(3)], axis=1)
            io_post, io_ant = io[-1], io[0]
        else:
            io_post = post + back * 4.0 + up * (IO_ABOVE_MM * 0.72)
            io_ant = ant + fwd * 2.0 + up * IO_ABOVE_MM
            io_mid = 0.5 * (io_post + io_ant) + up * 1.6
            t = np.linspace(0, 1, 30)[:, None]
            io = ((1 - t) ** 2 * io_post + 2 * (1 - t) * t * io_mid
                  + t ** 2 * io_ant)
            if snap is not None:
                io = confine(io, snap)
        o = tube(io, np.linspace(*IO_RADIUS_MM, len(io)))
        if o:
            v, f = o
            # Its OWN mesh, not merged with PSA/MSA/ASA. Once the canal is
            # measured the infraorbital nerve is `derived` while those three
            # remain `schematic`, and one mesh can only carry one tier --
            # merging them would either overclaim the others or hide this.
            iv.append(v); if_.append(f + ioff); ioff += len(v)
            trunks.append(dict(name="infraorbital", side=side,
                               measured_canal=traced is not None,
                               length_mm=round(float(np.linalg.norm(
                                   np.diff(io, axis=0), axis=1).sum()), 1),
                               inconstant=False,
                               parent="maxillary nerve (V2)",
                               origin_lps=[round(float(x), 2) for x in io_post]))

        # PSA leaves V2 itself; MSA and ASA leave the infraorbital nerve, so
        # each starts ON it -- at the point nearest the plexus node it serves.
        def on_io(p):
            return io[int(np.argmin(np.linalg.norm(io - p[None, :], axis=1)))]

        def at_arc(poly, where):
            """A point along the trunk: a fraction of its length, or mm from
            the anterior (foramen) end when `where` is 1 or more."""
            d = np.concatenate([[0.0], np.cumsum(
                np.linalg.norm(np.diff(poly, axis=0), axis=1))])
            target = where * d[-1] if where < 1.0 else min(float(where), d[-1])
            return poly[int(np.argmin(np.abs(d - target)))]

        spec = (
            ("PSA", post, io_post + back * 3.0 + 0.6 * lateral,
             "maxillary nerve (V2)", False),
            # Where MSA and ASA leave the trunk.
            #
            # Against the old CONSTRUCTED arc the rule was "nearest point on the
            # trunk to the plexus node you serve", with the node lifted by
            # IO_ABOVE_MM to reach it. That rule cannot survive the canal being
            # measured: the real canal climbs to z 29-38 while every plexus node
            # sits at the alveolus, so the nearest point to ALL of them is the
            # anterior end and both branches collapsed onto the foramen.
            #
            # Malamed places them ALONG the canal instead -- ASA in its anterior
            # part, a few millimetres behind the foramen, MSA about midway. So
            # they are placed by arc length now. The position along the canal is
            # literature; the canal it is measured along is not. That keeps the
            # branches `schematic` while their origin sits on measured geometry,
            # which is exactly what the tier is meant to distinguish.
            ("MSA", mid, at_arc(io, 0.50), "infraorbital", True),
            ("ASA", ant, at_arc(io, ASA_BEHIND_FORAMEN_MM), "infraorbital", False),
        )
        for name, foot, head, parent, inconstant in spec:
            pts = np.array([(1 - q) * head + q * foot
                            for q in np.linspace(0, 1, 20)])
            pts = pts + up * (np.sin(np.linspace(0, np.pi, 20))[:, None] * 0.9)
            if snap is not None:
                pts = confine(pts, snap)
            o = tube(pts, np.linspace(TRUNK_RADIUS_MM, PLEXUS_RADIUS_MM, len(pts)))
            if not o:
                continue
            v, f = o
            tv.append(v)
            tf.append(f + toff)
            toff += len(v)
            trunks.append(dict(name=name, side=side, parent=parent,
                               length_mm=round(float(np.linalg.norm(
                                   np.diff(pts, axis=0), axis=1).sum()), 1),
                               inconstant=inconstant,
                               origin_lps=[round(float(x), 2) for x in head]))
    if tv:
        if iv:
            write_binary_stl(os.path.join(outdir, "nerve-infraorbital.stl"),
                             np.concatenate(iv), np.concatenate(if_))
        write_binary_stl(os.path.join(outdir, "nerve-superior-trunks.stl"),
                         np.vstack(tv), np.vstack(tf))

    rep = dict(
        provenance=dict(
            apical_foramina="MEASURED (CBCT, trajectory-extrapolated)",
            superior_dental_plexus="SCHEMATIC (not resolved by this CBCT)",
            trunks="SCHEMATIC (PSA/MSA/ASA courses are textbook, not observed)",
            branches="INFERRED (distal endpoint measured, path is convention)"),
        note="The maxillary superior alveolar canals are thin and frequently "
             "dehiscent and are NOT reliably visible at 0.16 mm. Nothing in "
             "this file was seen in the scan except the foramina.",
        msa_note="The middle superior alveolar nerve is absent in roughly "
                 "two thirds of people; it is drawn here and flagged.",
        plexus_nodes=len(arc), trunks=trunks, branches=branches)
    with open(os.path.join(outdir, "nerve-maxilla.json"), "w") as fh:
        json.dump(rep, fh, indent=2)
    print(f"plexus nodes {len(arc)}, branches {len(branches)}, "
          f"trunks {[t['name'] for t in trunks]}")
    for t in trunks:
        tag = " (inconstant)" if t["inconstant"] else ""
        print(f"  {t['side']:5s} {t['name']}{tag:14s} from {t['origin_lps']}")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
