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
BRANCH_RADIUS_MM = 0.35
LOWER = set(range(18, 32))


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
    if allv:
        write_binary_stl(os.path.join(outdir, "nerve-ian-trunk.stl"),
                         np.vstack(allv), np.vstack(allf))

    # branches: trunk -> each lower tooth's apical foramen
    bv, bf, boff = [], [], 0
    for key, rec in pulp.items():
        num = int(key)
        if num not in LOWER:
            continue
        for c in rec["canals"]:
            apex = np.array(c["apical_position_lps"], dtype=float)
            side = "right" if apex[0] < 0 else "left"
            cand = [l for l in lines if l["side"] == side] or lines
            if not cand:
                continue
            pts = cand[0]["points"]
            k = int(np.argmin(np.linalg.norm(pts - apex[None, :], axis=1)))
            d = float(np.linalg.norm(pts[k] - apex))
            if d > 25.0:
                continue
            curve = branch_curve(pts[k], apex)
            out = tube(curve, np.full(len(curve), BRANCH_RADIUS_MM))
            if out is None:
                continue
            v, f = out
            bv.append(v); bf.append(f + boff); boff += len(v)
            report["branches"].append(dict(universal=num, fma=rec["fma"],
                                           canal=c["index"],
                                           trunk_to_apex_mm=round(d, 2),
                                           apex_lps=[round(float(x), 2) for x in apex]))
    if bv:
        write_binary_stl(os.path.join(outdir, "nerve-branches.stl"),
                         np.vstack(bv), np.vstack(bf))
    print(f"  branches: {len(report['branches'])} to lower tooth apices")
    with open(os.path.join(outdir, "nerve.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
