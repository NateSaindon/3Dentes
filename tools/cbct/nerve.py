#!/usr/bin/env python3
"""Build the inferior alveolar nerve and its branches to the tooth apices.

Provenance is the whole point of this module, so it is stated up front and
carried into the output filenames and the JSON:

  MEASURED  the bony canal (docs/cbct-canal.json) and the 48 apical foramina
            (docs/cbct-pulp.json) -- both from the CBCT.
  SCHEMATIC the nerve trunk inside the canal. CBCT resolves the canal, not its
            contents; the nerve is drawn as a tube occupying part of the canal's
            lumen because that is where it runs, not because it was seen.
  INFERRED  the branch from the trunk to each apical foramen. Both endpoints are
            measured; the path between them is anatomical convention.

An atlas that renders these three alike is lying by omission, and the intended
audience is a clinician who will notice. Keep them in separate meshes so the UI
can colour them differently.

Only the mandibular arch gets this treatment. There is no maxillary equivalent:
the posterior superior alveolar canals are sometimes visible in CBCT but are not
reliably present, and nothing here should imply otherwise.

Usage: python3 tools/cbct/nerve.py <canal.npy> <pulp.json> <out-dir>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from segment_tooth import write_binary_stl

ORIGIN = np.array([-40.96, -58.074258, -44.520221])
SPACING = 0.16
NERVE_FRACTION = 0.55     # trunk diameter as a share of the canal's
BRANCH_ROOT_R_MM = 0.32   # branch radius where it leaves its parent
BRANCH_TIP_R_MM = 0.12    # ...and at the apical foramen, where it enters pulp
INCISIVE_R_MM = (0.45, 0.18)   # mental foramen -> midline
MENTAL_R_MM = (0.55, 0.22)
MENTAL_RUN_MM = 7.0       # how far the mental nerve is drawn beyond the foramen
INCISIVE_BELOW_MM = 2.6   # the incisive canal runs apical to the anterior apices
LOWER = set(range(18, 32))

# The IAN terminates by dividing into the MENTAL nerve, which leaves the mental
# foramen near the second premolar for the chin and lower lip, and the INCISIVE
# branch, which continues forward inside the mandible to the first premolar,
# canine and incisors. Teeth anterior to the mental foramen therefore hang off
# the incisive nerve, not off the canal: a straight chord from the canal to a
# central incisor is 22-26 mm and runs through bone, which is why the old 25 mm
# cutoff dropped teeth 24 and 25 rather than draw one.
#   -- en.wikipedia.org/wiki/Inferior_alveolar_nerve, /wiki/Mental_nerve


def bone_test(pred_path, origin, spacing):
    """Inside-mandible test plus a nearest-inside snap, in world coordinates.

    Needed because the fused canal sits on a PADDED grid that extends below
    centered.nrrd, so the most anterior centreline point is a spur outside the
    mandible altogether -- it came out at z = -44.7 where the mandible's own
    floor is -43.7. Anything picked off the raw centreline has to be tested
    against bone before it is called a landmark.
    """
    from read_nifti import read_nifti
    lab, _, _ = read_nifti(pred_path)
    # DentalSegmentator is per-class, and the CANAL and the LOWER TEETH are
    # classes of their own -- so they are holes in the mandible label, and a
    # bare `lab == 2` test reports every point of a nerve running inside the
    # canal as OUTSIDE the bone. It read 0 of 209 trunk points inside before
    # this. Fill the mandible and union the classes that sit within it.
    mand = ndi.binary_fill_holes((lab == 2) | (lab == 4) | (lab == 5))
    box = ndi.find_objects(mand.astype(np.uint8))[0]
    sub = mand[box]
    _, idx = ndi.distance_transform_edt(~sub, return_indices=True)
    base = np.array([b.start for b in box])

    def to_idx(w):
        return np.array([(w[2] - origin[2]) / spacing,
                         (w[1] - origin[1]) / spacing,
                         (w[0] - origin[0]) / spacing])

    def inside(w):
        i = np.round(to_idx(w)).astype(int) - base
        if np.any(i < 0) or np.any(i >= np.array(sub.shape)):
            return False
        return bool(sub[tuple(i)])

    def in_vol(w):
        i = np.round(to_idx(w)).astype(int)
        return bool(np.all(i >= 0) and np.all(i < np.array(lab.shape)))

    def snap(w):
        if inside(w):
            return np.asarray(w, float)
        i = np.clip(np.round(to_idx(w)).astype(int) - base, 0,
                    np.array(sub.shape) - 1)
        j = idx[(slice(None),) + tuple(i)] + base
        return np.array([origin[0] + j[2] * spacing,
                         origin[1] + j[1] * spacing,
                         origin[2] + j[0] * spacing])
    return inside, snap, in_vol


ANTERIOR_FRAC = 0.35       # of the canal's length, searched for the foramen


def buccal_foramen(pts, inside, side, max_mm=14.0, step=0.16,
                   frac=ANTERIOR_FRAC):
    """Where a traced canal opens on the BUCCAL plate. Returns (index, mm).

    The foramen is NOT the anterior end of the tracing, and assuming it was is
    why the landmark moved 3-5 mm between two tracings of the same canal. The
    mandibular canal does not stop at the mental foramen: it carries on forward
    as the incisive canal, so an operator tracing the lumen runs straight past
    the exit, and the "anterior end" is wherever the canal became too faint to
    follow. Both tracings show it -- the last few millimetres run MEDIALLY, into
    the symphysis, which is the incisive canal's direction and the opposite of
    the way a nerve leaves the jaw.

    What does mark the foramen is the canal coming to the buccal cortex, and
    that is measurable on the traced course. On the second tracing it picks out
    z -43.5 on the right and -43.6 on the left, 22.0 and 21.1 mm from the dental
    midline, each about 0.55 mm inside the plate -- symmetric to a tenth of a
    millimetre in height, which the anterior end never was.
    """
    # ONLY THE ANTERIOR END IS SEARCHED. "Closest approach to the buccal plate"
    # is the right criterion and a whole canal is the wrong place to apply it:
    # further back the mandibular canal genuinely runs near the buccal cortex
    # under the external oblique ridge, and given a longer tracing that stretch
    # wins. It did -- extending the right canal posteriorly moved the "foramen"
    # 18 mm back, to y -2.8, and threw the two sides' symmetry from 1.9 mm apart
    # to 4.6. The mental foramen is at the front by definition, so only the
    # front is a candidate.
    pts = np.asarray(pts, float)
    n = max(3, int(round(len(pts) * frac)))
    lat = -1.0 if side == "right" else 1.0
    best = (0, 1e9)
    for i, p in enumerate(pts[:n]):
        if not inside(p):
            continue
        d = 0.0
        while d < max_mm:
            d += step
            if not inside(p + np.array([lat * d, 0.0, 0.0])):
                break
        if d < best[1]:
            best = (i, d)
    return best


def taper(n, r0, r1):
    """Radius along a branch. A nerve entering a 0.2 mm foramen cannot be
    0.35 mm wide at its tip; without this the branches read as pegs pushed into
    the root rather than as something continuous with the pulp."""
    return np.linspace(r0, r1, n)


def resample(pts, n):
    pts = np.asarray(pts, float)
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0),
                                                        axis=1))])
    if d[-1] < 1e-6:
        return np.repeat(pts[:1], n, axis=0)
    t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, pts[:, i]) for i in range(3)], axis=1)


def smooth_path(pts, passes=6):
    pts = np.asarray(pts, float).copy()
    for _ in range(passes):
        pts[1:-1] = 0.25 * pts[:-2] + 0.5 * pts[1:-1] + 0.25 * pts[2:]
    return pts


def incisive_path(mental, apices, snap=None):
    """From the mental foramen forward to the midline, apical to the anteriors.

    Built THROUGH the anterior apices rather than as a free curve: the incisive
    canal runs just below them, so they are the only measured evidence of where
    it goes on this patient.
    """
    if not len(apices):
        return None
    a = np.array(sorted(apices, key=lambda p: abs(p[0]), reverse=True), float)
    a = a.copy()
    a[:, 2] -= INCISIVE_BELOW_MM          # apical is -z in the mandible
    end = a[-1].copy()
    end[0] *= 0.15                         # run on to just short of the midline
    path = resample(np.vstack([mental, a, end]), 40)
    if snap is not None:
        # An offset straight down from the apices leaves the bone where the
        # symphysis narrows; pull the strays back in, before AND after
        # smoothing, the same discipline canal_tree.py needs (rule 58).
        path = np.array([snap(w) for w in path])
        path = smooth_path(path)
        return np.array([snap(w) for w in path])
    return smooth_path(path)


def mental_path(mental, side):
    """Out of the mental foramen: buccally, then up and forward to the lip."""
    lat = -1.0 if side == "right" else 1.0     # anatomical right is -x
    d = np.array([lat * 0.72, -0.52, 0.46])
    d /= np.linalg.norm(d)
    t = np.linspace(0, MENTAL_RUN_MM, 20)[:, None]
    return smooth_path(np.asarray(mental, float)[None, :] + d[None, :] * t)


def canal_centrelines(canal, offset):
    """One ordered centreline per side, from the fused canal mask."""
    from skimage.morphology import skeletonize
    lab, n = ndi.label(canal, structure=np.ones((3, 3, 3)))
    sizes = ndi.sum(canal, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    out = []
    for sid in order[:2]:
        m = lab == (sid + 1)
        sk = skeletonize(m)
        pts = np.argwhere(sk).astype(float)
        if len(pts) < 20:
            continue
        world = np.stack([
            ORIGIN[0] + (pts[:, 2] - offset[2]) * SPACING,
            ORIGIN[1] + (pts[:, 1] - offset[1]) * SPACING,
            ORIGIN[2] + (pts[:, 0] - offset[0]) * SPACING], axis=1)
        # order along the canal: it runs mostly anteroposteriorly, so sort by y
        world = world[np.argsort(world[:, 1])]
        # thin out and smooth -- a raw skeleton is jagged at voxel scale
        keep = world[::3]
        sm = np.stack([np.convolve(np.pad(keep[:, i], 4, mode="edge"),
                                   np.ones(9) / 9, mode="valid")
                       for i in range(3)], axis=1)
        # local radius from the distance transform, sampled along the curve
        dist = ndi.distance_transform_edt(m, sampling=(SPACING,) * 3)
        idx = np.stack([(sm[:, 2] - ORIGIN[2]) / SPACING + offset[0],
                        (sm[:, 1] - ORIGIN[1]) / SPACING + offset[1],
                        (sm[:, 0] - ORIGIN[0]) / SPACING + offset[2]], axis=0)
        rad = ndi.map_coordinates(dist, idx, order=1, mode="nearest")
        side = "right" if sm[:, 0].mean() < 0 else "left"
        out.append(dict(side=side, points=sm, radius=np.maximum(rad, 0.3)))
    return out


def tube(points, radii, nseg=14):
    pts = np.asarray(points, dtype=float)
    r = np.asarray(radii, dtype=float)
    if len(pts) < 3:
        return None
    tang = np.gradient(pts, axis=0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
    phi = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    ref = np.array([0.0, 0.0, 1.0])
    rings = []
    for i in range(len(pts)):
        t = tang[i]
        u = np.cross(t, ref)
        if np.linalg.norm(u) < 1e-6:
            u = np.cross(t, np.array([0.0, 1.0, 0.0]))
        u /= np.linalg.norm(u)
        w = np.cross(t, u)
        rings.append(pts[i][None, :] + r[i] * (np.cos(phi)[:, None] * u[None, :]
                                               + np.sin(phi)[:, None] * w[None, :]))
    rings = np.array(rings)
    verts = rings.reshape(-1, 3)
    faces = []
    for i in range(len(rings) - 1):
        for j in range(nseg):
            k = (j + 1) % nseg
            a, b = i * nseg + j, i * nseg + k
            c, d = (i + 1) * nseg + j, (i + 1) * nseg + k
            faces.append([a, c, d]); faces.append([a, d, b])
    ca, cb = len(verts), len(verts) + 1
    verts = np.vstack([verts, rings[0].mean(0)[None, :], rings[-1].mean(0)[None, :]])
    for j in range(nseg):
        k = (j + 1) % nseg
        faces.append([ca, k, j])
        faces.append([cb, (len(rings) - 1) * nseg + j, (len(rings) - 1) * nseg + k])
    return verts, np.array(faces)


def branch_curve(start, end, bulge=0.35, n=24):
    """A gently curved path from the trunk to an apex.

    A straight line would read as a claim about the path. The real branch leaves
    the trunk superiorly and turns toward the apex, so the curve is bowed toward
    the tooth -- schematic, and shaped like the thing it stands for.
    """
    start, end = np.asarray(start, float), np.asarray(end, float)
    mid = 0.5 * (start + end)
    mid[2] += bulge * np.linalg.norm(end - start) * 0.5
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * start + 2 * (1 - t) * t * mid + t ** 2 * end


def main():
    canal_path, pulp_path, outdir = sys.argv[1:4]
    pred_path = sys.argv[4] if len(sys.argv) > 4 else None
    os.makedirs(outdir, exist_ok=True)
    canal = np.load(canal_path)
    pulp = json.load(open(pulp_path))
    # the fused canal lives on a padded grid; recover the offset from its header
    meta = os.path.join(os.path.dirname(canal_path), "canal.json")
    offset = np.array([0, 0, 0])
    if os.path.exists(meta):
        j = json.load(open(meta))
        offset = np.array(j.get("grid_offset", [0, 0, 0]))
    lines = canal_centrelines(canal, offset)
    print(f"canal centrelines: {len(lines)}")
    inside = snap = in_vol = None
    if pred_path:
        inside, snap, in_vol = bone_test(pred_path, ORIGIN, SPACING)
    report = dict(provenance=dict(
        canal="MEASURED (CBCT)", apical_foramina="MEASURED (CBCT)",
        nerve_trunk="SCHEMATIC (canal contents are not resolved by CBCT)",
        branches="INFERRED (endpoints measured, path is convention)"), trunks=[],
        branches=[])

    allv, allf, off = [], [], 0
    for ln in lines:
        out = tube(ln["points"], ln["radius"] * NERVE_FRACTION)
        if out is None:
            continue
        v, f = out
        allv.append(v); allf.append(f + off); off += len(v)
        length = float(np.linalg.norm(np.diff(ln["points"], axis=0), axis=1).sum())
        report["trunks"].append(dict(side=ln["side"], length_mm=round(length, 1),
                                     mean_radius_mm=round(float(ln["radius"].mean()
                                                                * NERVE_FRACTION), 3)))
        print(f"  trunk {ln['side']:5s}: {length:5.1f} mm, "
              f"mean radius {ln['radius'].mean()*NERVE_FRACTION:.2f} mm")
    # branches: trunk -> each lower tooth's apical foramen
    #
    # Anchor on pulp-connect.json's `foramina` when present. Those are the
    # MODELLED FORAMEN EXITS -- where the canal actually leaves the root, placed
    # by extrapolating the measured canal trajectory and checked against the
    # literature (mean 0.58 mm from the anatomical apex, against 0.52 reported).
    # pulp.json's `apical_position_lps` is the end of the deficit-integration
    # tube instead, which is a different and worse point to hang a nerve on.
    teeth = pulp.get("teeth", pulp)

    # The mental foramen is the ANTERIOR end of the measured canal. LPS y grows
    # posteriorly, so it is the minimum-y point of each centreline.
    # The mental foramen is placed at the PREMOLARS, not at the anterior end of
    # the skeleton. That endpoint is not a landmark: the fused canal carries
    # spurs and on the right it dives below centered.nrrd's floor, which put the
    # foramen at z = -44.7 (the mandible's own floor is -43.7) and, once bad
    # points were excluded, at y = -3.0 against the left's -23.9. Wikipedia puts
    # the foramen "near the second lower premolar", and those apices are
    # measured -- so project them onto the canal and take the nearest point.
    PREMOLARS = {"right": (28, 29), "left": (20, 21)}
    apex_of = {}
    for key, rec in teeth.items():
        if rec.get("foramina"):
            apex_of[int(rec["universal"])] = np.mean(
                [f["world_lps"] for f in rec["foramina"]], axis=0)
    mental = {}
    for ln in lines:
        want = [apex_of[u] for u in PREMOLARS[ln["side"]] if u in apex_of]
        pts = ln["points"]
        # Drop only points outside the VOLUME, not outside the bone. The fused
        # canal spans both exposures, so roughly half of it legitimately lies
        # beyond centered.nrrd's FOV; excluding all of that biased the right
        # foramen 21 mm posteriorly, to y = -3.0 against the left's -23.9.
        # What must go is the spur below the mandible's floor (z = -46.9).
        if in_vol is not None:
            keep = np.array([in_vol(w) for w in pts])
            if keep.sum() >= 5:
                pts = pts[keep]
        if want:
            ref = np.mean(want, axis=0)
            mental[ln["side"]] = pts[int(np.argmin(
                np.linalg.norm(pts - ref[None, :], axis=1)))]
        else:
            mental[ln["side"]] = pts[int(np.argmin(pts[:, 1]))]
    # A TRACED mental canal supersedes the projection above.
    #
    # The projection puts the foramen at the point of the measured canal
    # nearest the premolar apices, and that is only ever as good as the canal:
    # on the right it stops 11 mm short of the premolar window, so the rule
    # returns the end of the curve. Once the operator has traced the mental
    # canal itself the foramen is simply its anterior end, and the two modules
    # that hang geometry off it must use the SAME point -- otherwise the trunk
    # leaves the bone at one place and its facial branches at another, 3 mm
    # apart on the right, and the nerve renders in two disconnected pieces.
    traced = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "..", "docs", "cbct-mental.json")
    if os.path.exists(traced):
        d = json.load(open(traced))
        for side, rec in d.get("sides", {}).items():
            pts = np.array([r["p"] for r in rec["points"]], float)
            if len(pts) < 3 or side not in mental:
                continue
            if pts[0][1] > pts[-1][1]:
                pts = pts[::-1]                      # anterior first
            if inside is not None:
                k, gap = buccal_foramen(pts, inside, side)
                where = f"buccal plate {gap:.2f} mm away, sample {k}"
            else:
                k, where = 0, "anterior end (no bone test loaded)"
            moved = float(np.linalg.norm(pts[k] - mental[side]))
            print(f"  mental foramen {side:5s}: TRACED, {where}, "
                  f"{moved:.1f} mm from the projected point")
            mental[side] = pts[k]
            rec["foramen_index"] = int(k)
        report["provenance"]["mental_foramen"] = (
            "MEASURED (anterior end of the hand-traced mental canal)")

    # Recorded, not just printed: nerve_face.py hangs the mental nerve's
    # terminal fan off these, and a landmark that two modules each place by
    # their own copy of the rule is a landmark that will drift.
    report["mental_foramina"] = {
        side: [round(float(x), 2) for x in w] for side, w in mental.items()}
    for side, w in mental.items():
        print(f"  mental foramen {side:5s}: "
              f"[{w[0]:.1f}, {w[1]:.1f}, {w[2]:.1f}]")

    # Collect every lower apical foramen and decide which parent supplies it.
    targets = []
    for key, rec in teeth.items():
        num = int(rec.get("universal", key if str(key).isdigit() else 0))
        if num not in LOWER:
            continue
        if rec.get("foramina"):
            pts = [(i, np.array(f["world_lps"], float))
                   for i, f in enumerate(rec["foramina"])]
        else:
            pts = [(c["index"], np.array(c["apical_position_lps"], float))
                   for c in rec.get("canals", [])]
        for cidx, apex in pts:
            side = "right" if apex[0] < 0 else "left"
            targets.append(dict(num=num, cidx=cidx, apex=apex, side=side,
                                fma=rec.get("fma", key)))

    # Anterior to the mental foramen -> incisive nerve; posterior -> the canal.
    incisive = {}
    tmv, tmf, tmoff = [], [], 0
    for side, m in mental.items():
        ant = [t["apex"] for t in targets if t["side"] == side
               and t["apex"][1] < m[1]]
        path = incisive_path(m, ant, snap=snap)
        if path is None:
            continue
        incisive[side] = path
        v, f = tube(path, taper(len(path), *INCISIVE_R_MM))
        tmv.append(v); tmf.append(f + tmoff); tmoff += len(v)
        report.setdefault("terminal", []).append(dict(
            name="incisive branch", side=side,
            length_mm=round(float(np.linalg.norm(np.diff(path, axis=0),
                                                 axis=1).sum()), 1),
            supplies=sorted({t["num"] for t in targets if t["side"] == side
                             and t["apex"][1] < m[1]}),
            provenance="SCHEMATIC (course inferred from the anterior apices; "
                       "the incisive canal is not resolved at 0.16 mm)"))
        mp = mental_path(m, side)
        v, f = tube(mp, taper(len(mp), *MENTAL_R_MM))
        tmv.append(v); tmf.append(f + tmoff); tmoff += len(v)
        report["terminal"].append(dict(
            name="mental nerve", side=side, length_mm=MENTAL_RUN_MM,
            supplies="chin and lower lip (soft tissue, not modelled)",
            provenance="SCHEMATIC (exits the measured mental foramen; its "
                       "extraosseous course is convention)"))
    if tmv:
        # A SEPARATE mesh from the trunk. The trunk follows a canal this scan
        # resolves; the incisive and mental branches do not, and merging them
        # would let the UI colour a schematic course like a measured one --
        # exactly what this module's docstring forbids.
        write_binary_stl(os.path.join(outdir, "nerve-terminal.stl"),
                         np.vstack(tmv), np.vstack(tmf))
        print(f"  terminal: incisive + mental, {len(incisive)} sides")

    bv, bf, boff = [], [], 0
    for t in targets:
        apex, side = t["apex"], t["side"]
        # parent: the incisive nerve if this tooth lies anterior to the mental
        # foramen, otherwise the inferior dental plexus in the canal
        m = mental.get(side)
        if m is not None and apex[1] < m[1] and side in incisive:
            pts, parent = incisive[side], "incisive"
        else:
            cand = [l for l in lines if l["side"] == side] or lines
            if not cand:
                continue
            pts, parent = cand[0]["points"], "inferior dental plexus"
        k = int(np.argmin(np.linalg.norm(pts - apex[None, :], axis=1)))
        d = float(np.linalg.norm(pts[k] - apex))
        if d > 25.0:
            continue
        curve = branch_curve(pts[k], apex)
        out = tube(curve, taper(len(curve), BRANCH_ROOT_R_MM, BRANCH_TIP_R_MM))
        if out is None:
            continue
        v, f = out
        bv.append(v); bf.append(f + boff); boff += len(v)
        report["branches"].append(dict(universal=t["num"], fma=t["fma"],
                                       canal=t["cidx"], parent=parent,
                                       trunk_to_apex_mm=round(d, 2),
                                       apex_lps=[round(float(x), 2) for x in apex]))
    if allv:
        write_binary_stl(os.path.join(outdir, "nerve-ian-trunk.stl"),
                         np.vstack(allv), np.vstack(allf))
    if bv:
        write_binary_stl(os.path.join(outdir, "nerve-branches.stl"),
                         np.vstack(bv), np.vstack(bf))
    print(f"  branches: {len(report['branches'])} to lower tooth apices")
    with open(os.path.join(outdir, "nerve.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
