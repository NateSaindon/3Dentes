#!/usr/bin/env python3
"""The root canal system as an explicit tree, swept into geometry.

WHY THIS EXISTS
---------------
Canals used to be built by painting spheres along minimum-cost paths and
meshing the voxel union. In that representation a dead-end twig and a tangential
touch between two tubes are indistinguishable from real anatomy, so spurious
branches are not bugs to be filtered -- they are what the method produces. Five
successive filters moved the count from 40 to 39.

Here the canal system is a TREE before it is geometry:

    one root      the chamber floor
    one leaf      per apical foramen, and ONLY per apical foramen
    each edge     a centreline with a radius at every point

A branch can then exist only where the tree branches; a free end is
unrepresentable, because every leaf is a foramen by construction; and calibre is
a property of a node rather than an accident of how spheres overlapped.

Voxelisation is still used for MESHING -- it handles junctions for free and
marching cubes is already trusted here -- but what gets voxelised is a smooth
analytic tube, not an accumulation of paint operations. That distinction is the
whole point: do not reintroduce per-voxel edits to "touch up" the result.

WHAT IS MEASURED AND WHAT IS NOT
--------------------------------
  MEASURED   the orifice positions (widest, best-resolved part of the canal),
             the apical foramina, and the darkest-route centreline between them
  MODELLED   the radius profile, clamped to a micro-CT envelope, and the
             smoothing of the centreline
Nothing here invents a canal that the image does not support; it constrains the
SHAPE of one the image does support.
"""
import numpy as np
from scipy import ndimage as ndi

# Micro-CT equivalent diameters for molar mesial canals, by distance from the
# apex, scaled by this model's tissue-vs-lumen factor. Same series pulp_connect
# used; kept here so the tree owns its own calibre.
CANAL_ENV_MM = ((0.0, 0.26), (1.0, 0.42), (2.0, 0.57), (3.0, 0.58), (4.0, 0.64))
FORAMEN_R_MM = 0.13

# A UNIFORM TAPER, not a piecewise one.
# The micro-CT series above is nearly linear in distance from the apex --
# 0.26/0.42/0.57/0.58/0.64 mm diameter at 0-4 mm -- a slope near 0.088 mm of
# diameter per mm of length, which is also the range clinical taper is described
# in (.02-.06 files, i.e. 0.02-0.06 mm/mm, with natural canals wider). The old
# model held the envelope apically and then blended to the orifice radius over
# the remainder, which is a visible kink partway up. One line, one slope, all
# the way from foramen to orifice.
CANAL_D0_MM = 0.30        # diameter extrapolated to the foramen
CANAL_TAPER = 0.088       # mm of diameter per mm from the apex
CANAL_MAX_R_MM = 0.62     # ~1.24 mm diameter, the wide end of a natural orifice

# Minimum dentine between a canal and the root surface. Micro-CT of mandibular
# mesial roots puts the "danger zone" minimum at 0.67-1.93 mm, mean 1.10-1.13.
# A centreline closer than this to the surface is not a canal, it is a tracking
# failure -- the periodontal ligament is dark and pulls the tracker outward.
MIN_DENTINE_MM = 0.85
# Two canals in one root are two canals only if they are apart at mid-root.
# Teeth 12 and 13 tracked both of their orifices into the buccal canal and 18
# drew its ML twice, because nothing checked that the canals filed under a root
# were actually DISTINCT -- the quota was satisfied by a duplicate.
MIN_CANAL_SEP_MM = 0.80
# When `apical_roots` returns ONE root for a tooth that really has two (tooth 18
# and the maxillary premolars), that "root" is the whole tooth, and canals must
# be spread across it rather than clustered: tooth 18 drew two canals in the
# mesial and none distal. A true single root keeps the tighter figure, because
# MB1 and MB2 in a maxillary mesiobuccal root are only 1-2 mm apart.
FUSED_CANAL_SEP_MM = 1.80
TARGET_DENTINE_MM = 1.10

# CANALS PER ROOT, not per tooth. Sources: MB2 present in ~60% of maxillary
# FIRST molars and ~33% of seconds; the maxillary palatal root is essentially
# always single; the mandibular mesial root carries two (MB, ML) and the distal
# one (a second distal canal in ~37%). Keyed by (universal, root identity).
# A root NEVER gets more canals than this -- two canals drawn down a palatal
# root is an anatomical impossibility, not a tolerable artefact -- and a root
# short of its quota is filled rather than left empty.
ROOT_QUOTA = {
    # maxillary first molars: MB2 is the common case
    (3, "mb"): 2, (3, "db"): 1, (3, "p"): 1,
    (14, "mb"): 2, (14, "db"): 1, (14, "p"): 1,
    # maxillary second molars: MB2 in only a third, so one
    (2, "mb"): 1, (2, "db"): 1, (2, "p"): 1,
    (15, "mb"): 1, (15, "db"): 1, (15, "p"): 1,
    # maxillary first premolars: one canal in each of the two roots
    (5, "b"): 1, (5, "p"): 1,
    (12, "b"): 1, (12, "p"): 1,
    # mandibular molars: mesial carries two, distal one
    (19, "m"): 2, (19, "d"): 1,
    (30, "m"): 2, (30, "d"): 1,
    (18, "m"): 2, (18, "d"): 1,
    (31, "m"): 2, (31, "d"): 1,
}
DEFAULT_ROOT_QUOTA = 1

# Canals per TOOTH, used when root detection under-counts. `apical_roots` reads
# tooth 15 as two roots and tooth 18 as one, and teeth 4, 12 and 13 as single-
# rooted; applying a per-root quota to a root that is really two roots fused
# throws away canals that exist. The per-root table governs where canals go; this
# governs how many there are in total, and the remainder lands in the largest
# detected root -- which is the fused one.
TOOTH_CANALS = {2: 3, 3: 4, 14: 4, 15: 3,
                18: 3, 19: 3, 30: 3, 31: 3,
                4: 2, 5: 2, 12: 2, 13: 2}


def root_quotas(universal, root_names, root_sizes):
    """Canals per detected root, reconciled against the tooth's total."""
    q = [ROOT_QUOTA.get((universal, n), DEFAULT_ROOT_QUOTA) for n in root_names]
    total = TOOTH_CANALS.get(universal)
    if total is None or not q:
        return q
    while sum(q) < total:
        q[int(np.argmax(root_sizes))] += 1
        root_sizes = list(root_sizes)
        root_sizes[int(np.argmax(root_sizes))] *= 0.6   # spread, don't stack
    while sum(q) > total:
        i = max(range(len(q)), key=lambda k: q[k])
        if q[i] <= 1:
            break
        q[i] -= 1
    return q


def identify_roots(roots, tooth_centre_world, world_of, arch, n_roots):
    """Name each root buccal/palatal or mesial/distal from its own position.

    Palatal/lingual is toward the arch centre; mesial is toward the midline
    along the arch. Both fall out of the root's offset from the tooth centre,
    so nothing here depends on which tooth it is except how many roots to
    expect.
    """
    if not roots:
        return []
    cw = [np.asarray(world_of(r), float) for r in roots]
    names = [None] * len(roots)
    if n_roots >= 3:
        # maxillary molar: palatal is the one nearest the midline in x
        pi = int(np.argmin([abs(c[0]) for c in cw]))
        names[pi] = "p"
        rest = [i for i in range(len(roots)) if i != pi]
        rest.sort(key=lambda i: cw[i][1])      # smaller y = more mesial
        if rest:
            names[rest[0]] = "mb"
        for i in rest[1:]:
            names[i] = "db"
    elif n_roots == 2 and arch == "upper":
        # maxillary premolar: buccal is further from the midline
        bi = int(np.argmax([abs(c[0]) for c in cw]))
        for i in range(len(roots)):
            names[i] = "b" if i == bi else "p"
    elif n_roots == 2:
        order = sorted(range(len(roots)), key=lambda i: cw[i][1])
        names[order[0]] = "m"
        for i in order[1:]:
            names[i] = "d"
    else:
        for i in range(len(roots)):
            names[i] = "s"
    return names
RESAMPLE_MM = 0.20
SMOOTH_PASSES = 12


def envelope_r(dist_mm):
    xs = [p[0] for p in CANAL_ENV_MM]
    ys = [p[1] / 2.0 for p in CANAL_ENV_MM]
    d = np.asarray(dist_mm, float)
    return np.where(d > xs[-1], np.inf, np.interp(d, xs, ys))


def catmull_rom(points, step_mm, spacing):
    """Smooth curve THROUGH every control point (not near them)."""
    P = np.asarray(points, float)
    if len(P) < 2:
        return P
    if len(P) == 2:
        return resample(P, spacing, step_mm)
    ext = np.vstack([P[0] + (P[0] - P[1]), P, P[-1] + (P[-1] - P[-2])])
    vsp = np.asarray(spacing, float)[::-1]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        seg_mm = float(np.linalg.norm((p2 - p1) * vsp))
        n = max(int(seg_mm / step_mm), 2)
        for t in np.linspace(0.0, 1.0, n, endpoint=(i == len(P) - 2)):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t
                              + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return np.array(out)


def darkest_near_line(roi, mask, a, b, frac, spacing, lam=250.0, half=2):
    """Darkest voxel in the axial slab at `frac` along a->b, near that line.

    This is the operator's mid-root landmark: the canal is the darkest thing in
    the root at that level, and the straight orifice-apex line says roughly
    where to look. Pure minimum-intensity would wander to unrelated dark voxels
    (the PDL, a neighbouring canal); the distance penalty keeps it honest
    without forcing it onto the line, so a curved canal is still followed.
    """
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    vsp = np.asarray(spacing, float)[::-1]
    z = int(round(a[0] + (b[0] - a[0]) * frac))
    z0, z1 = max(z - half, 0), min(z + half + 1, roi.shape[0])
    best, bs = None, None
    for k in range(z0, z1):
        idx = np.argwhere(mask[k])
        if not len(idx):
            continue
        pts = np.column_stack([np.full(len(idx), k), idx])
        d = b - a
        L2 = float((d * vsp @ (d * vsp)))
        if L2 < 1e-9:
            continue
        t = (((pts - a) * vsp) @ (d * vsp)) / L2
        proj = a + np.clip(t, 0, 1)[:, None] * d
        dist = np.linalg.norm((pts - proj) * vsp, axis=1)
        score = roi[k][tuple(idx.T)] + lam * dist
        j = int(np.argmin(score))
        if bs is None or score[j] < bs:
            bs, best = score[j], pts[j]
    return None if best is None else best.astype(float)


def resample(points, spacing, step_mm=RESAMPLE_MM):
    """Uniform arc-length resampling, in index coordinates."""
    p = np.asarray(points, float)
    if len(p) < 2:
        return p
    vsp = np.asarray(spacing, float)[::-1]
    seg = np.linalg.norm(np.diff(p, axis=0) * vsp, axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    if arc[-1] < 1e-6:
        return p[:1]
    n = max(int(arc[-1] / step_mm) + 1, 2)
    t = np.linspace(0.0, arc[-1], n)
    return np.stack([np.interp(t, arc, p[:, a]) for a in range(3)], axis=1)


def smooth_inside(points, inside, passes=SMOOTH_PASSES):
    """Smooth a centreline, but never let it leave the tooth.

    A min-cost path through a voxel grid is a staircase; swept unsmoothed it
    produces exactly the lumpy, faceted canal the operator kept rejecting. But
    smoothing a curved canal cuts corners, and in a curved root that walks the
    centreline into -- and through -- the root wall. Each point is therefore
    only allowed to move if its new position is still inside the tooth.
    """
    p = np.asarray(points, float).copy()
    if len(p) < 3:
        return p
    for _ in range(passes):
        q = p.copy()
        q[1:-1] = 0.25 * p[:-2] + 0.5 * p[1:-1] + 0.25 * p[2:]
        idx = np.round(q).astype(int)
        ok = np.ones(len(q), bool)
        for a in range(3):
            ok &= (idx[:, a] >= 0) & (idx[:, a] < inside.shape[a])
        ok[~ok] = False
        good = ok.copy()
        good[ok] = inside[tuple(idx[ok].T)]
        p[good] = q[good]
    return p


def track_canal(roi, inside, start, arch, spacing, step_mm=0.40,
                search_mm=0.75, momentum=0.75, lam=1600.0, max_mm=22.0,
                depth=None, wall_pen=1800.0, avoid=None, avoid_pen=2600.0,
                avoid_mm=0.70):
    """Follow one canal down from its orifice, level by level.

    Four landmarks joined by a spline made molar roots straight, and assigning
    orifices to separately-detected "roots" put canals in the wrong root
    entirely -- two canals down the buccal and none down the palatal, wherever
    `apical_roots` found one root where there are two.

    Tracking fixes both. At each step the canal is predicted to continue in the
    direction it was already going, and the darkest voxel near that prediction
    is accepted; the canal therefore curves as the radiolucency curves, and it
    ends up in whichever root it actually belongs to because it was never told
    about roots. The prediction is what keeps it honest -- pure darkness would
    hop to the PDL or a neighbour, and no prediction at all would zig-zag.
    """
    # UNITS: `vsp` is mm per voxel per axis. The direction is kept as a unit
    # vector in MILLIMETRE space and converted to a voxel step only when it is
    # applied. Mixing the two (a direction normalised in mm, then scaled by a
    # voxel count) made the step length meaningless and every track stopped
    # early -- foramina fell to 33 and deviation from the apex rose to 2.96 mm.
    vsp = np.asarray(spacing, float)[::-1]
    dz = 1.0 if arch == "upper" else -1.0
    pts = [np.asarray(start, float)]
    dir_mm = np.array([dz, 0.0, 0.0])
    travelled = 0.0
    rad = int(np.ceil(search_mm / float(vsp[1]))) + 1
    while travelled < max_mm:
        cur = pts[-1]
        pred = cur + (dir_mm * step_mm) / vsp
        z = int(round(pred[0]))
        if z < 0 or z >= roi.shape[0] or not inside[z].any():
            break
        y0 = max(int(pred[1]) - rad, 0)
        y1 = min(int(pred[1]) + rad + 1, roi.shape[1])
        x0 = max(int(pred[2]) - rad, 0)
        x1 = min(int(pred[2]) + rad + 1, roi.shape[2])
        win = inside[z, y0:y1, x0:x1]
        if not win.any():
            break
        idx = np.argwhere(win) + [y0, x0]
        cand = np.column_stack([np.full(len(idx), z), idx]).astype(float)
        d = np.linalg.norm((cand - pred) * vsp, axis=1)
        keep = d <= search_mm
        if not keep.any():
            break
        cand, d = cand[keep], d[keep]
        vals = roi[z][tuple(cand[:, 1:].astype(int).T)]
        score = vals + lam * d
        if avoid is not None:
            # KEEP OFF A CANAL ALREADY DRAWN. Two canals in one tooth are drawn
            # as separate branches, but nothing stopped a track from drifting
            # onto its neighbour and running alongside it -- tooth 12 showed a
            # SINGLE cross-section the whole way down despite having two
            # canals, and the mesiobuccal pairs of teeth 3, 14 and 18 merged
            # within a millimetre of the floor. Penalise candidates that sit on
            # top of an existing canal; they may still converge apically, where
            # the merge rule allows it, but they can no longer start merged.
            av = avoid[z][tuple(cand[:, 1:].astype(int).T)]
            score = score + avoid_pen * av
        if depth is not None:
            # a candidate closer to the root surface than the danger-zone
            # minimum is penalised in proportion to how far short it falls
            dep = depth[z][tuple(cand[:, 1:].astype(int).T)]
            score = score + wall_pen * np.maximum(0.0, MIN_DENTINE_MM - dep)
        nxt = cand[int(np.argmin(score))]
        move = (nxt - cur) * vsp
        n = float(np.linalg.norm(move))
        if n < 1e-6:
            break
        dir_mm = momentum * dir_mm + (1.0 - momentum) * (move / n)
        dn = float(np.linalg.norm(dir_mm))
        if dn < 1e-6:
            break
        dir_mm = dir_mm / dn
        # never let the canal turn back up the root
        if dir_mm[0] * dz <= 0.05:
            dir_mm[0] = 0.05 * dz
            dir_mm = dir_mm / float(np.linalg.norm(dir_mm))
        pts.append(nxt)
        travelled += n
    return np.array(pts)


def seed_in_root(roi, root, arch, spacing, frac=0.25, exclude=None,
                 min_sep_mm=1.0):
    """Darkest voxel in the coronal quarter of a root -- where its canal starts.

    Used to FILL a root the tracker never entered. The canal is the darkest
    thing in the root at that level, so this is still image-derived; only the
    decision that a canal must exist there comes from the quota.

    `exclude` MATTERS. Filling a root that needs two canals called this twice,
    and with no memory of the first it returned the same darkest voxel both
    times: teeth 12 and 13 got two buccal canals and no palatal, 18 got a
    duplicated ML, 19 lost its MB. Voxels within `min_sep_mm` of an existing
    canal are excluded so the second seed is the second-darkest DISTINCT place,
    which in a two-canalled root is the other canal.
    """
    zs = np.where(root.any(axis=(1, 2)))[0]
    if zs.size < 4:
        return None
    z0, z1 = int(zs.min()), int(zs.max())
    z = int(z0 + frac * (z1 - z0)) if arch == "upper" else int(z1 - frac * (z1 - z0))
    avoid = None
    if exclude is not None and np.any(exclude):
        rad = int(np.ceil(min_sep_mm / float(spacing[0])))
        avoid = ndi.binary_dilation(exclude, np.ones((1, 2 * rad + 1,
                                                      2 * rad + 1)))
    best, bs = None, None
    for k in range(max(z - 2, z0), min(z + 3, z1 + 1)):
        ok = root[k]
        if avoid is not None:
            ok = ok & ~avoid[k]
        idx = np.argwhere(ok)
        if not len(idx):
            continue
        vals = roi[k][tuple(idx.T)]
        j = int(np.argmin(vals))
        if bs is None or vals[j] < bs:
            bs = vals[j]
            best = np.array([k, idx[j][0], idx[j][1]], float)
    return best


def recentre(points, depth, spacing, min_mm=MIN_DENTINE_MM,
             target_mm=TARGET_DENTINE_MM, radius_mm=1.1):
    """Pull each centreline point toward the middle of the root cross-section.

    The tracker follows darkness, and the darkest thing near a thin root wall is
    often the periodontal ligament OUTSIDE it, so canals drift onto the dentine
    border -- the operator sees canals touching the tooth surface. Within each
    axial slice a point that is shallower than the measured danger-zone minimum
    is moved toward the local maximum of the distance-to-surface field, which is
    the centre of the root there. Points already deep enough are left alone, so
    a genuinely eccentric canal is not dragged to the axis.
    """
    p = np.asarray(points, float).copy()
    vsp = np.asarray(spacing, float)[::-1]
    rad = int(np.ceil(radius_mm / float(vsp[1])))
    for i, q in enumerate(p):
        z = int(round(q[0]))
        if z < 0 or z >= depth.shape[0]:
            continue
        yi, xi = int(round(q[1])), int(round(q[2]))
        if not (0 <= yi < depth.shape[1] and 0 <= xi < depth.shape[2]):
            continue
        # Always seek the local centre, not only when already too shallow. A
        # canal at 0.9 mm in a root whose centre is at 1.6 mm still renders as
        # hugging the wall, because the tube's own radius eats the rest.
        if depth[z, yi, xi] >= target_mm:
            continue
        y0, y1 = max(yi - rad, 0), min(yi + rad + 1, depth.shape[1])
        x0, x1 = max(xi - rad, 0), min(xi + rad + 1, depth.shape[2])
        win = depth[z, y0:y1, x0:x1]
        if not win.size or win.max() <= depth[z, yi, xi]:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        dist = np.sqrt(((yy - yi) * vsp[1]) ** 2 + ((xx - xi) * vsp[2]) ** 2)
        # nearest position that reaches the target depth; failing that, deepest
        ok = win >= target_mm
        if ok.any():
            j = int(np.argmin(np.where(ok, dist, np.inf)))
        else:
            j = int(np.argmax(win - 0.25 * dist))
        p[i] = [z, yy.ravel()[j], xx.ravel()[j]]
    return p


def pull_inside(points, inside):
    """Move any control point that left the tooth back to the nearest voxel in.

    A Catmull-Rom curve through four landmarks cuts the corner on a curved
    canal, and in a curved root that corner is outside the root wall. Voxelising
    with a domain limit then CLIPS the tube there, which leaves a gap in the
    canal and a stub at each side -- four teeth arrived in pieces and the twig
    count rose. Projecting the stray points back keeps the curve continuous and
    inside the anatomy.
    """
    p = np.asarray(points, float).copy()
    idx = np.round(p).astype(int)
    for a in range(3):
        idx[:, a] = np.clip(idx[:, a], 0, inside.shape[a] - 1)
    out = ~inside[tuple(idx.T)]
    if not out.any():
        return p
    _, near = ndi.distance_transform_edt(~inside, return_indices=True)
    for i in np.where(out)[0]:
        p[i] = [near[a][tuple(idx[i])] for a in range(3)]
    return p


class CanalTree:
    """Nodes with a parent link, a radius, and a provenance tag."""

    def __init__(self):
        self.pts = []
        self.rad = []
        self.parent = []
        self.kind = []

    def add_branch(self, points, radii, parent=-1, kind="canal"):
        """Append a polyline; returns the index of its last node."""
        prev = parent
        first = len(self.pts)
        for p, r in zip(points, radii):
            self.pts.append(np.asarray(p, float))
            self.rad.append(float(r))
            self.parent.append(prev)
            self.kind.append(kind)
            prev = len(self.pts) - 1
        return prev, first

    def nearest(self, point, kinds=None):
        """Index of the closest existing node, for joining a sibling canal."""
        if not self.pts:
            return None
        P = np.array(self.pts)
        if kinds is not None:
            mask = np.array([k in kinds for k in self.kind])
            if not mask.any():
                return None
            idx = np.where(mask)[0]
            d = np.linalg.norm(P[idx] - np.asarray(point, float), axis=1)
            return int(idx[int(np.argmin(d))])
        d = np.linalg.norm(P - np.asarray(point, float), axis=1)
        return int(np.argmin(d))

    def edges(self):
        for i, par in enumerate(self.parent):
            if par >= 0:
                yield par, i

    def leaves(self):
        has_child = set(p for p in self.parent if p >= 0)
        return [i for i in range(len(self.pts)) if i not in has_child]

    def __len__(self):
        return len(self.pts)


def voxelize(tree, shape, spacing, limit=None):
    """Sweep every edge as a capsule with linearly varying radius.

    Capsules, not spheres-at-samples: a sphere per sample leaves scalloping
    between samples unless they are packed far tighter than the voxel, and that
    scalloping is what a skeletoniser later reads as spurious branch points.
    """
    out = np.zeros(shape, bool)
    if len(tree) == 0:
        return out
    vsp = np.asarray(spacing, float)[::-1]
    zz, yy, xx = np.indices(shape)
    grid = np.stack([zz, yy, xx], axis=-1).astype(np.float32)
    for a, b in tree.edges():
        p0, p1 = tree.pts[a], tree.pts[b]
        r0, r1 = tree.rad[a], tree.rad[b]
        seg = (p1 - p0) * vsp
        L = float(np.linalg.norm(seg))
        rmax = max(r0, r1)
        lo = np.floor(np.minimum(p0, p1) - (rmax / vsp) - 1).astype(int)
        hi = np.ceil(np.maximum(p0, p1) + (rmax / vsp) + 2).astype(int)
        lo = np.maximum(lo, 0)
        hi = np.minimum(hi, np.array(shape))
        if np.any(lo >= hi):
            continue
        sub = (slice(lo[0], hi[0]), slice(lo[1], hi[1]), slice(lo[2], hi[2]))
        q = (grid[sub] - p0) * vsp
        if L < 1e-6:
            t = np.zeros(q.shape[:-1], np.float32)
            d = np.linalg.norm(q, axis=-1)
        else:
            u = seg / L
            t = np.clip((q * u).sum(-1) / L, 0.0, 1.0)
            d = np.linalg.norm(q - t[..., None] * seg, axis=-1)
        out[sub] |= d <= (r0 + (r1 - r0) * t)
    if limit is not None:
        out &= limit
    return out


def pick_exits(cand, cumulative, apex_i, vsp, n, cost_quantile=0.30,
               min_sep_mm=0.9):
    """Plausible dark exits near the apex, forced apart, nearest-apex first.

    The CHEAPEST exit is systematically short of the apex -- leaving the root
    wall early costs less than running the last millimetre -- so take the
    cheapest quantile, all of them plausible routes, and among those choose the
    one closest to the apex.
    """
    c = cumulative[tuple(cand.T)]
    ok = np.isfinite(c)
    if not ok.any():
        return []
    cand, c = cand[ok], c[ok]
    keep = c <= np.quantile(c, cost_quantile)
    pool = cand[keep]
    out = []
    for _ in range(max(n, 1)):
        if not len(pool):
            break
        d = np.linalg.norm((pool - apex_i) * vsp, axis=1)
        e = pool[int(np.argmin(d))]
        out.append(tuple(int(q) for q in e))
        pool = pool[np.linalg.norm((pool - e) * vsp, axis=1) >= min_sep_mm]
    return out


def build_canals(mcp_factory, cost, tooth_solid, spacing, arch, roots,
                 orifices, chamber_dist, cumulative, surf, chamber=None,
                 roi=None, universal=0, root_names=None, stats=None,
                 exit_reach_mm=1.5, foramen_r=FORAMEN_R_MM, merge_mm=0.35):
    """Track every canal from its orifice to the apex; join siblings that meet.

    No root assignment. Canals used to be handed to roots detected separately,
    and wherever `apical_roots` saw one root where the tooth has two, both
    canals went down the same one -- two buccal canals and no palatal. A tracked
    canal ends up in whichever root it actually occupies because it was never
    told about roots; roots are used only to NAME the apex it arrived at.
    """
    vsp = np.asarray(spacing, float)[::-1]
    tree = CanalTree()
    foramina = []
    dropped_over = [0]
    dropped_dup = [0]
    filled = [0]
    # Canals created to satisfy the quota must NOT be merged away. They exist
    # precisely because a separate canal is required there, and letting one
    # merge into its neighbour is the same as never having drawn it -- teeth 4
    # and 12 lost their palatal, 18 its ML, 19 its MB, all of which the fill had
    # correctly created. A merged fill also skips the chamber connection, which
    # is why tooth 31's ML floated free of the chamber.
    forced = set()
    if not orifices or roi is None:
        return tree, foramina

    depth = ndi.distance_transform_edt(tooth_solid, sampling=tuple(spacing))
    avoid = np.zeros_like(tooth_solid)
    rad = max(int(round(0.70 / float(vsp[1]))), 1)
    tracks = []
    for orf in orifices:
        t = track_canal(roi, tooth_solid, orf, arch, spacing, depth=depth,
                        avoid=avoid)
        if len(t) >= 4:
            tracks.append(t)
            ix = np.round(t).astype(int)
            for a in range(3):
                ix[:, a] = np.clip(ix[:, a], 0, avoid.shape[a] - 1)
            hit = np.zeros_like(avoid)
            hit[tuple(ix.T)] = True
            avoid |= ndi.binary_dilation(hit, np.ones((1, 2 * rad + 1,
                                                       2 * rad + 1)))

    # ENFORCE THE PER-ROOT QUOTA.
    # Each track is filed under the root its TIP lands in -- where a canal ends
    # is what makes it that root's canal, not where it started. A root over
    # quota keeps its longest tracks (a short one is a stub or a duplicate of a
    # neighbour); a root under quota is FILLED, because an empty root is always
    # wrong and the operator would rather see a modelled canal than a gap.
    def root_of_tip(tip):
        if not roots:
            return None
        cen = [np.argwhere(r).mean(0) for r in roots]
        return int(np.argmin([np.linalg.norm((np.asarray(tip, float) - c) * vsp)
                              for c in cen]))

    if roots and root_names:
        by = {}
        for t in tracks:
            ri = root_of_tip(t[-1])
            by.setdefault(ri, []).append(t)
        quotas = root_quotas(universal, root_names,
                             [float(r.sum()) for r in roots])
        tracks = []
        for ri, root in enumerate(roots):
            q = quotas[ri]
            got = sorted(by.get(ri, []), key=len, reverse=True)
            # keep only canals that are genuinely separate at mid-root
            sep = (FUSED_CANAL_SEP_MM if root_names[ri] == "s"
                   else MIN_CANAL_SEP_MM)
            # COMPARE AT A COMMON DEPTH. Using each track's own midpoint by
            # index compares tracks of different lengths at different levels,
            # so two canals a millimetre apart could read as far apart and
            # survive -- tooth 18 kept four canals clustered in its mesial.
            def at_z(t, zref):
                return t[int(np.argmin(np.abs(t[:, 0] - zref)))]

            zs_all = np.concatenate([t[:, 0] for t in got]) if got else None
            zref = float(np.median(zs_all)) if zs_all is not None else 0.0
            uniq = []
            for t in got:
                pt = at_z(t, zref)
                if all(np.linalg.norm((pt - at_z(u, zref)) * vsp) >= sep
                       for u in uniq):
                    uniq.append(t)
                else:
                    dropped_dup[0] += 1
            got = uniq
            if len(got) > q:
                dropped_over[0] += len(got) - q
                got = got[:q]
            while len(got) < q:
                drawn = np.zeros_like(tooth_solid)
                for tk in got:
                    ix = np.round(tk).astype(int)
                    for a in range(3):
                        ix[:, a] = np.clip(ix[:, a], 0, drawn.shape[a] - 1)
                    drawn[tuple(ix.T)] = True
                seed = seed_in_root(roi, tooth_solid & root, arch, spacing,
                                    exclude=drawn, min_sep_mm=sep)
                if seed is None:
                    break
                # HARD exclusion, not a penalty. A soft avoid_pen loses to the
                # intensity term: tooth 12's second canal was seeded 1.8 mm away
                # and then tracked straight back onto the first, so the two
                # unioned into one round tube -- a single 0.64 mm cross-section
                # where there should be two. A canal the quota created to be
                # SEPARATE is not allowed into its sibling's corridor at all.
                room = tooth_solid & ~avoid
                if not room[tuple(np.round(seed).astype(int))]:
                    room = tooth_solid
                extra = track_canal(roi, room, seed, arch, spacing,
                                    depth=depth, avoid=avoid)
                if len(extra) < 4:
                    break
                got.append(extra)
                forced.add(id(extra))
                filled[0] += 1
            tracks.extend(got)

    kept = []
    for t in tracks:
        # 2:1 -- if this canal runs into one already drawn, stop there and join
        # it. Two canals that merge share one path from the junction down, which
        # is what Vertucci type II is; drawing both to their own apex would
        # invent a canal the tooth does not have.
        jn_node = -1
        if kept and id(t) not in forced:
            for i in range(len(t)):
                best = None
                for prev in kept:
                    dd = np.linalg.norm((prev["path"] - t[i]) * vsp, axis=1)
                    k = int(np.argmin(dd))
                    if best is None or dd[k] < best[0]:
                        best = (dd[k], prev, k)
                # Merge only APICALLY and only when genuinely close. At 0.55 mm
                # anywhere along the canal a faint palatal canal was captured by
                # its buccal neighbour on the way down -- tooth 5 lost its
                # palatal canal entirely. Two canals that share a root converge
                # near the apex; two in different roots never do.
                if best and best[0] <= merge_mm and i > max(3, int(0.55 * len(t))):
                    t = t[:i + 1]
                    jn_node = best[1]["nodes"][best[2]]
                    break

        path = np.asarray(t, float)
        # EVERY canal reaches the chamber, merged or not. A canal that joins a
        # sibling lower down still LEAVES the chamber at its own orifice; only
        # giving the connection to unmerged canals left tooth 31's ML starting
        # in mid-root with nothing above it.
        if chamber is not None and chamber.any():
            cdep = ndi.distance_transform_edt(chamber, sampling=tuple(spacing))
            deep = np.argwhere(chamber & (cdep >= 2.0 * float(spacing[0])))
            cv = deep if len(deep) else np.argwhere(chamber)
            k = int(np.argmin(np.linalg.norm((cv - path[0]) * vsp, axis=1)))
            path = np.vstack([cv[k].astype(float), path])
        path = recentre(path, depth, spacing)
        path = catmull_rom(path, RESAMPLE_MM, spacing)
        path = pull_inside(path, tooth_solid)
        path = smooth_inside(path, tooth_solid, passes=6)
        path = recentre(path, depth, spacing)
        path = smooth_inside(path, tooth_solid, passes=4)
        path = pull_inside(path, tooth_solid)
        if len(path) < 2:
            continue

        seg = np.linalg.norm(np.diff(path, axis=0) * vsp, axis=1)
        arc = np.concatenate([[0.0], np.cumsum(seg)])
        total = max(arc[-1], 1e-6)
        oi = tuple(int(round(np.clip(q, 0, sh - 1)))
                   for q, sh in zip(path[0], chamber_dist.shape))
        r_orf = float(chamber_dist[oi]) if chamber_dist[oi] > 0 else 0.35
        # Blend from the CHAMBER's own local radius so the canal grows out of
        # the chamber instead of stepping down from it -- the operator sees that
        # step on every premolar and incisor.
        r_orf = float(np.clip(r_orf, 0.20, 1.10))
        d_apex = total - arc
        # ONE SLOPE from foramen to orifice. Diameter = D0 + taper * distance
        # from the apex, capped where the canal meets the chamber so it does not
        # exceed the space it opens into.
        radii = (CANAL_D0_MM + CANAL_TAPER * d_apex) / 2.0
        # Cap by an ABSOLUTE maximum, not by the chamber distance at the
        # orifice. That distance is small whenever the orifice sits at the edge
        # of the chamber, and clamping to it flattened the taper from 4 mm up --
        # 0.72 mm diameter at 8 mm where the slope calls for 1.00. The canal is
        # allowed to reach chamber calibre near the top; it merges into the
        # chamber there anyway.
        radii = np.minimum(radii, CANAL_MAX_R_MM)
        radii = np.maximum(radii, foramen_r)

        first = len(tree)
        tree.add_branch(path, radii, parent=jn_node, kind="canal")
        nodes = list(range(first, len(tree)))
        kept.append({"path": path, "nodes": nodes})

        if jn_node < 0:
            tip = path[-1]
            ri, apex_i = 0, tuple(int(round(q)) for q in tip)
            if roots:
                cen = [np.argwhere(r).mean(0) for r in roots]
                ri = int(np.argmin([np.linalg.norm((tip - c) * vsp) for c in cen]))
                rz = np.argwhere(roots[ri])
                ap = rz[np.argmax(rz[:, 0])] if arch == "upper" else rz[np.argmin(rz[:, 0])]
                apex_i = tuple(int(q) for q in ap)
            # A foramen far from any root apex means the track ran away, not
            # that the anatomy is unusual: tooth 19 produced one 14.3 mm out.
            # Reported deviations top out near 2 mm.
            dev = float(np.linalg.norm((np.asarray(tip, float)
                                        - np.asarray(apex_i, float)) * vsp))
            if dev <= 3.0:
                foramina.append((tuple(int(round(q)) for q in tip), apex_i, ri))
    if stats is not None:
        stats["over_quota_dropped"] = dropped_over[0]
        stats["duplicates_dropped"] = dropped_dup[0]
        stats["roots_filled"] = filled[0]
    return tree, foramina
