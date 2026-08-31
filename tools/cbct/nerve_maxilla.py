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

Usage: nerve_maxilla.py <pulp-connect.json> <split.json> <out-dir>
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


def main():
    pulp_path, split_path, outdir = sys.argv[1:4]
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
        # anatomy. Placed relative to the MEASURED apices and flagged SCHEMATIC:
        # nothing of this canal is resolved at 0.16 mm.
        io_post = post + back * 4.0 + up * (IO_ABOVE_MM * 0.72)
        io_ant = ant + fwd * 2.0 + up * IO_ABOVE_MM
        io_mid = 0.5 * (io_post + io_ant) + up * 1.6
        t = np.linspace(0, 1, 30)[:, None]
        io = ((1 - t) ** 2 * io_post + 2 * (1 - t) * t * io_mid
              + t ** 2 * io_ant)
        o = tube(io, np.linspace(*IO_RADIUS_MM, len(io)))
        if o:
            v, f = o
            tv.append(v); tf.append(f + toff); toff += len(v)
            trunks.append(dict(name="infraorbital", side=side,
                               length_mm=round(float(np.linalg.norm(
                                   np.diff(io, axis=0), axis=1).sum()), 1),
                               inconstant=False,
                               parent="maxillary nerve (V2)",
                               origin_lps=[round(float(x), 2) for x in io_post]))

        # PSA leaves V2 itself; MSA and ASA leave the infraorbital nerve, so
        # each starts ON it -- at the point nearest the plexus node it serves.
        def on_io(p):
            return io[int(np.argmin(np.linalg.norm(io - p[None, :], axis=1)))]

        spec = (
            ("PSA", post, io_post + back * 3.0 + 0.6 * lateral,
             "maxillary nerve (V2)", False),
            ("MSA", mid, on_io(mid + up * IO_ABOVE_MM), "infraorbital", True),
            ("ASA", ant, on_io(ant + up * IO_ABOVE_MM), "infraorbital", False),
        )
        for name, foot, head, parent, inconstant in spec:
            pts = np.array([(1 - q) * head + q * foot
                            for q in np.linspace(0, 1, 20)])
            pts = pts + up * (np.sin(np.linspace(0, np.pi, 20))[:, None] * 0.9)
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
