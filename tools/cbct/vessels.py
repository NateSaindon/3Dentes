#!/usr/bin/env python3
"""The arterial supply and venous drainage of both arches.

WHAT IS MEASURED HERE IS THE CANAL, and it was already measured -- this module
adds no new observation. It draws the artery that shares each canal with the
nerve the atlas already renders, on the SAME centreline, offset within the SAME
lumen. CBCT resolves the canal; it does not resolve its contents, at any
calibre, so every radius and every offset below is a choice.

  MEASURED   the canal centreline and its local radius. The mandibular canal
             comes from the fused segmentation, through nerve.canal_centrelines
             so the artery rides the identical curve as the inferior alveolar
             nerve rather than a re-derivation of it. The infraorbital and
             mental canals come from the operator's own tracings.
  DERIVED    the artery, as a tube of chosen calibre at a chosen offset inside
             that measured lumen.

THE ARRANGEMENT IS SOURCED, AND ONLY FOR THE MANDIBULAR CANAL:
  Kim et al., 3D reconstruction of 10 canals -- in 80% the vessels lie SUPERIOR
  to the nerve, with the artery LINGUAL to the vein; in 20% they lie buccal.
  Pogrel et al., 8 cadaveric mandibles at the third molar region -- the vein
  lies superior to the nerve, and the artery is solitary, on the lingual side,
  slightly above the horizontal.
  Both via Juodzbalys, Wang & Sabalys, J Oral Maxillofac Res 2010;1(1):e2.
  A histomorphometric series (Surg Radiol Anat, doi 10.1007/s00276-015-1540-6)
  adds that the position is SITE-DEPENDENT -- buccal in the pterygomandibular
  space, buccal-inferior at the mandibular foramen, superior in the molar
  region, lingual in the premolar region, in 77.4%.
  That variation is NOT modelled: one constant offset is drawn down the whole
  canal. The review's own summary is that there is "no consistent pattern for
  the entire canal length", so a course that rotated would be asserting a
  particular patient's variant rather than the convention.

FOR THE INFRAORBITAL CANAL NOTHING COMPARABLE WAS FOUND, so the artery is put
superior to the nerve by analogy and the provenance says analogy, not source.

THE VEINS ARE NAMED BY TAH, NOT FMA. The FMA has 3,741 vein terms -- facial,
lingual, maxillary, the pterygoid plexus -- and NO inferior alveolar vein, no
infraorbital vein, no alveolar or dental vein of any kind. The IFAA's
Terminologia Anatomica Humana does name all three, and cross-references FMA
where FMA has a term (TAH:U3863, the inferior alveolar artery, carries
FMA:49695), so the two namespaces sit together without either being invented:
  TAH:U15802  vena alveolaris inferior (par)     inferior alveolar vein
  TAH:U15803  venae dentales (par)               dental veins, a child of U15802
  TAH:U15485  vena infraorbitalis (par)          infraorbital vein
Operator's find, verified against the IFAA unit pages.

A CANAL IS NOT ROUND, AND THAT IS WHY THE FIRST ATTEMPT HAD NOWHERE TO PUT THE
INFRAORBITAL ARTERY. `canal_r_mm` is an equivalent-circle radius -- sqrt(area/pi),
the geometric mean of the two semi-axes -- and the infraorbital canal measures
2.0:1 and 2.4:1 on this patient, semi-major 1.60 and 1.95 mm against semi-minor
0.85 and 0.90. The nerve is drawn at 1.05 mm, which exceeds the SHORT axis and
leaves half a millimetre of the long one unused. Packing against the equivalent
circle therefore buried the artery inside the nerve, 100% and 89% of its length.
Packing along the MEASURED major axis is what this module does now, and
io_centreline.py records that axis per sample so it is measured rather than
assumed.

NOTHING MAY TRAVEL THROUGH DENTIN. A dental branch ENDS at an apical foramen,
which is on the root, so its last fraction of a millimetre is inside hard tissue
by design -- that is the connection. What must not happen is a vessel crossing
dentin on the way, and a straight chord from a trunk to an apex does exactly
that in a crowded arch. Every branch is routed against the SPLIT LABELS (not the
decimated meshes, or a vessel could sit in the gap between the two), pushed out
by its own tube radius plus a margin and re-smoothed with the push getting the
last word. The check at the end of a run measures contact against DISTANCE FROM
THE ENDPOINTS, because "percent of the mesh inside a tooth" cannot tell a
correct apical connection from a vessel through a neighbour -- it read 7-12% on
branches that were right.

Usage: vessels.py <canal.npy> <out-dir> [--io docs/cbct-infraorbital.json]
                  [--mental docs/cbct-mental.json] [--pulp pulp-connect.json]
                  [--split <split-dir>] [--vol centered.nrrd]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from segment_tooth import write_binary_stl                  # noqa: E402
import nerve as N                                           # noqa: E402
import nerve_maxilla as NM                                  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# tools/cbct -> tools -> repo root

# All as fractions of the LOCAL measured canal radius, so the bundle scales with
# the lumen instead of overflowing where the canal narrows. The nerve already
# occupies N.NERVE_FRACTION (0.55) centred on the axis, so the artery has to sit
# in the annulus outside it and inside the wall:
#     offset - radius > NERVE_FRACTION   (clear of the nerve)
#     offset + radius < 1.0              (inside the canal)
# 0.80 +/- 0.13 leaves 0.12 r of clearance inside and 0.07 r outside. Both are
# checked per point at the end of the run rather than assumed.
ART_OFFSET = 0.80
ART_RADIUS = 0.13
# Toward the LINGUAL side of superior (Kim, Pogrel). Small, because what the
# sources agree on is "superior, and the artery is the lingual one of the two";
# a large angle would be asserting the vein's position by drawing around it.
ART_LINGUAL_DEG = 14.0
# The infraorbital and mental canals are traced, not segmented, and their radius
# is the traced lumen. Same packing rule, stated separately because the
# arrangement behind it is analogy rather than a source.
# Along the MEASURED major axis, as a fraction of the local semi-major, with the
# artery and vein at opposite ends of it. Both are pushed out only as far as
# they must be to clear the nerve, then checked.
IO_VESSEL_FRAC = 0.16      # vessel radius as a fraction of the local semi-minor
IO_CLEAR_MM = 0.05         # how far a vessel must stay off the nerve's surface
# What nerve_maxilla.py actually draws the infraorbital nerve at, so the packing
# and its clearance check compare against the mesh that is really there. The
# traced course is ordered ANTERIOR-FIRST, so this is (foramen, posterior) --
# THIN at the foramen, which is where the nerve emerges. It used to be the other
# way round: the constant is written posterior-first and was applied down the
# anterior-first course, putting the thick end at the foramen. Corrected in
# nerve_maxilla 2026-09-04, and this pair follows that fix rather than restating
# it -- if the ramp is ever reversed again these two must move together.
IO_NERVE_R_MM = (0.80, 1.05)
# The vein is the larger of the two and sits buccal of the artery in the
# mandibular canal (Kim: "artery lingual to vein").
VEIN_RADIUS = 0.15
VEIN_LINGUAL_DEG = -14.0
# Dental veins, branching off the inferior alveolar vein to the tooth apices --
# the venous counterpart of the nerve's dental branches, and drawn to the same
# MEASURED apical foramina.
DENTAL_ROOT_R_MM = 0.20
DENTAL_TIP_R_MM = 0.09
DENTAL_MAX_MM = 25.0
# How close to an endpoint contact with a tooth counts as the CONNECTION rather
# than as travel through it. A dental branch ends at an apical foramen, which is
# on the root, so its last fraction of a millimetre is inside hard tissue by
# design. Measuring "percent of the mesh inside a tooth" cannot tell that from a
# vessel crossing a neighbouring root, and duly reported 7-12% on branches that
# were correct.
DENTIN_TIP_MM = 1.5
VOXEL_MM = 0.16            # this scan's isotropic voxel: the finest real claim
# The incisive branch is the CONTINUATION of the inferior alveolar vessels past
# the mental foramen, and neither ontology names it: the FMA has no term, and
# the IFAA lists only dental, peridental, mental and mylohyoid branches under
# TAH:U3863. So it takes the repo's derived-mesh suffix off its own parent --
# exactly what the incisive NERVE already does as FMA53243T.
INCISIVE_ART_R_MM = (0.13, 0.06)
INCISIVE_VEIN_R_MM = (0.15, 0.07)
# Maxillary. The plexus arc is built the way nerve_maxilla.py builds it -- a
# smooth curve through points set beyond each measured apex, away from the
# tooth's own centre -- and the vessels are offset off that shared arc so the
# three run together instead of being three independent guesses at one course.
PLEXUS_ABOVE_MM = 2.6           # nerve_maxilla's own figure, reused deliberately
MAX_ART_OFFSET_MM = 0.85        # artery buccal of the nerve plexus
MAX_VEIN_OFFSET_MM = -0.85      # vein lingual of it
MAX_TRUNK_R_MM = 0.30
MAX_BRANCH_R_MM = (0.16, 0.08)
# The greater palatine artery runs FORWARD IN A GROOVE ON THE HARD PALATE,
# under the mucosa, from the greater palatine foramen to the incisive canal --
# so unlike every other vessel here it belongs just OUTSIDE the bone, on its
# inferior surface, not inside it. Its course is found by casting a ray up onto
# the palatal vault at each station, which makes the SHAPE measured even though
# the vessel is not: it follows this patient's own palate.
GP_MEDIAL_FRAC = 0.66      # of the way from the midline out to the palatal wall
GP_BELOW_MM = 0.7          # clear of the bone, in the mucosa
GP_RADIUS_MM = (0.42, 0.20)   # foramen -> incisive canal, tapering forward
# The groove carries a BUNDLE. Nerve, artery and vein run it together, so all
# three are drawn on the one measured course, offset across it. Which of the
# three lies medial is convention -- no source was found for the arrangement in
# this groove, unlike the mandibular canal -- and the provenance says so.
GP_NERVE_R_MM = (0.38, 0.18)
GP_VEIN_R_MM = (0.40, 0.19)
GP_SPREAD_MM = 0.62           # across the groove, between neighbours
# The vein is the LATERAL member, so it is the one that meets the alveolar
# process; at 0.75 mm out and 0.46 mm radius it grazed a root by 0.18 mm. The
# groove is narrow and the bundle has to fit in it, which is a constraint on
# the drawing rather than a fact about the patient -- the arrangement across
# the groove was already convention.
GP_RAY_MM = 14.0           # how far up to look for the palate
PSA_TEETH = {2, 3, 14, 15}
MSA_TEETH = {4, 5, 12, 13}
ASA_TEETH = {6, 7, 8, 9, 10, 11}
MENTAL_RUN_MM = N.MENTAL_RUN_MM
MENTAL_ART_R_MM = (0.22, 0.10)   # chosen: the mental nerve is drawn 0.55 -> 0.22
DENTAL_MIDLINE_X = 3.5           # CLAUDE.md 143: anything sided is measured here


def frame(points):
    """Tangent, superior and lingual unit vectors at every point of a course.

    Superior is world +z projected off the tangent. Lingual is toward the DENTAL
    MIDLINE, not toward x = 0 -- rule 143, and the whole reason the two are
    distinguished is that this patient's midline is at x 3.5.
    """
    p = np.asarray(points, float)
    t = np.gradient(p, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    up = np.tile(np.array([0.0, 0.0, 1.0]), (len(p), 1))
    s = up - t * (up * t).sum(1)[:, None]
    n = np.linalg.norm(s, axis=1, keepdims=True)
    # where the course runs vertically the projection collapses; fall back to
    # any perpendicular rather than emitting a zero vector
    bad = (n < 1e-6).ravel()
    if bad.any():
        alt = np.tile(np.array([0.0, 1.0, 0.0]), (bad.sum(), 1))
        s[bad] = alt - t[bad] * (alt * t[bad]).sum(1)[:, None]
        n = np.linalg.norm(s, axis=1, keepdims=True)
    s /= np.maximum(n, 1e-9)
    lat = np.cross(t, s)
    lat /= np.maximum(np.linalg.norm(lat, axis=1, keepdims=True), 1e-9)
    # ORIENT `lat` AGAINST ITS OWN X COMPONENT, not against a per-side constant.
    # cross(t, s) points whichever way the centreline happens to be ordered, so
    # multiplying by sign(midline - x) -- a constant along each canal -- flips
    # both sides together and is right only as long as the ordering holds. It
    # does hold today, on both canals, which is exactly how this would have
    # survived: rule 125 is the same shape, a traversal order assumed rather
    # than read. Comparing lat's own x to the direction of the midline is true
    # per point whatever the ordering.
    want = np.sign(DENTAL_MIDLINE_X - p[:, 0])
    have = np.sign(lat[:, 0])
    have[have == 0] = 1.0
    flip = np.where(want * have < 0, -1.0, 1.0)[:, None]
    return t, s, lat * flip


def offset_course(points, radius, offset_frac, lingual_deg):
    """Shift a centreline into the lumen: `offset_frac` of r, toward superior."""
    p = np.asarray(points, float)
    r = np.asarray(radius, float)
    _, s, lat = frame(p)
    a = np.radians(lingual_deg)
    d = np.cos(a) * s + np.sin(a) * lat
    return p + d * (offset_frac * r)[:, None]


def check(points, centre, radius, vessel_r, nerve_r, label):
    """Does the drawn vessel stay inside the canal and clear of the nerve?

    Both are analytic here because both are tubes on a common centreline: the
    vessel's far wall is |offset| + vessel_r from the axis and its near wall is
    |offset| - vessel_r, against the canal radius and the nerve's.

    `nerve_r` MUST be the nerve's actual drawn radius in millimetres, per point.
    Passing a fraction derived from this vessel's own offset makes the second
    line evaluate to zero by construction -- which is what the first version of
    this function did for the infraorbital canal, and it duly reported a nerve
    clearance of -0.000 mm on every point. That is enamel detector (c) again:
    a check whose answer is fixed by its own arithmetic.
    """
    off = np.linalg.norm(np.asarray(centre) - np.asarray(points), axis=1)
    r = np.asarray(radius, float)
    nerve_r = np.broadcast_to(np.asarray(nerve_r, float), off.shape)
    outside = off + vessel_r - r                     # >0 means out of the canal
    into = nerve_r - (off - vessel_r)                # >0 means into the nerve
    print(f"    {label}: wall clearance {-outside.max():+.3f} mm worst "
          f"({100*(outside > 0).mean():.0f}% of points outside the canal), "
          f"nerve clearance {-into.max():+.3f} mm worst "
          f"({100*(into > 0).mean():.0f}% intersecting the nerve)")
    return dict(points=int(len(off)),
                worst_wall_clearance_mm=round(float(-outside.max()), 3),
                pct_outside_canal=round(float(100 * (outside > 0).mean()), 1),
                worst_nerve_clearance_mm=round(float(-into.max()), 3),
                pct_into_nerve=round(float(100 * (into > 0).mean()), 1))


def smooth1d(a, k=5):
    """Smooth a per-sample scalar along the course. A single slab that catches a
    marrow space reads a 5.40 mm semi-major on the left mental canal against a
    1.83 mm mean; letting that one sample place a vessel would put it outside the
    bone. Smoothing along the course is the same treatment the centreline gets."""
    a = np.asarray(a, float)
    if len(a) < k:
        return a
    pad = np.pad(a, k // 2, mode="edge")
    return np.convolve(pad, np.ones(k) / k, mode="valid")


def elliptical_offsets(points, semi_major, semi_minor, major_axis, nerve_r,
                       vessel_frac=IO_VESSEL_FRAC, clear_mm=IO_CLEAR_MM):
    """Place two vessels at opposite ends of a canal's MEASURED long axis.

    Returns (centres_a, centres_b, radii, report). The vessel radius is a
    fraction of the SHORT semi-axis, because that is what limits it; the offset
    is just far enough to clear the nerve, because pushing further only risks
    the wall. Both conditions are then measured rather than trusted.

    The major axis' SIGN is arbitrary -- it comes out of an eigenvector, which
    is defined up to negation and can flip between adjacent samples. It is
    oriented here so its z component is positive, i.e. so "end A" means the same
    end all the way down the canal. Without that the artery and vein would swap
    sides wherever the eigen-solver changed its mind, which is rule 158 in a new
    place: never let an axis' sign come from how a routine happened to order it.
    """
    p = np.asarray(points, float)
    a = smooth1d(semi_major)
    b = smooth1d(semi_minor)
    nr = np.asarray(nerve_r, float)
    m = np.asarray(major_axis, float)
    m = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
    flip = np.where(m[:, 2] < 0, -1.0, 1.0)[:, None]
    m = m * flip
    r_v = np.minimum(vessel_frac * b, np.maximum((a - nr) * 0.45, 1e-3))
    off = nr + r_v + clear_mm
    # never past the wall: the far edge has to stay inside the major semi-axis
    # Leave the same margin at the wall as at the nerve. Clamping to exactly
    # a - r_v puts the vessel's far edge ON the ellipse, and float noise then
    # reports a few percent of samples a hair outside it.
    off = np.minimum(off, np.maximum(a - r_v - clear_mm, 0.0))
    return p + m * off[:, None], p - m * off[:, None], r_v, dict(
        semi_major_mm=round(float(a.mean()), 3),
        semi_minor_mm=round(float(b.mean()), 3),
        aspect=round(float(np.mean(a / np.maximum(b, 1e-6))), 2))


def check_ellipse(points, centre, semi_major, semi_minor, major_axis,
                  vessel_r, nerve_r, label):
    """Inside the measured ellipse, and clear of the drawn nerve?"""
    p = np.asarray(points, float)
    d = np.asarray(centre, float) - p
    off = np.linalg.norm(d, axis=1)
    a, b = smooth1d(semi_major), smooth1d(semi_minor)
    vr = np.asarray(vessel_r, float)
    nr = np.asarray(nerve_r, float)
    outside = off + vr - a                  # >0 past the long axis' end
    # room across the short axis at that distance along the long one
    frac = np.clip(off / np.maximum(a, 1e-9), 0, 1)
    across = b * np.sqrt(np.maximum(1.0 - frac ** 2, 0.0))
    narrow = vr - across                    # >0 too fat for the ellipse there
    into = nr - (off - vr)                  # >0 inside the nerve
    print(f"    {label}: wall {-outside.max():+.3f} mm worst "
          f"({100*(outside > 0).mean():.0f}% past it), across {-narrow.max():+.3f} mm "
          f"({100*(narrow > 0).mean():.0f}% too fat), nerve {-into.max():+.3f} mm "
          f"({100*(into > 0).mean():.0f}% inside it)")
    return dict(points=int(len(off)),
                worst_wall_clearance_mm=round(float(-outside.max()), 3),
                pct_outside_canal=round(float(100 * (outside > 0).mean()), 1),
                worst_across_clearance_mm=round(float(-narrow.max()), 3),
                worst_nerve_clearance_mm=round(float(-into.max()), 3),
                pct_into_nerve=round(float(100 * (into > 0).mean()), 1),
                mean_radius_mm=round(float(vr.mean()), 3))


def tooth_field(split_dir, vol):
    """Distance out of the teeth, and where the nearest way out points.

    A vessel may END at an apical foramen -- that is the whole point of a dental
    branch -- but it must not TRAVEL through dentin on the way, and a straight
    chord from a trunk to an apex crosses whatever lies between, which in a
    crowded arch is usually the neighbouring root. Returns

        depth(world)  how deep inside tooth hard tissue a point is, in mm
        escape(pts)   the same points moved to just outside the nearest surface

    Built from the SPLIT labels rather than the meshes: the labels are the thing
    the meshes were made from, and testing against a decimated surface would let
    a vessel sit in the gap between the two.
    """
    import numpy as _np
    occ = None
    for arch in ("upper", "lower"):
        f = os.path.join(split_dir, f"{arch}_labels.npy")
        if not os.path.exists(f):
            continue
        a = _np.load(f) > 0
        occ = a if occ is None else (occ | a)
    if occ is None:
        return None, None
    sp = _np.array(vol.spacing, float)
    o = _np.array(vol.origin, float)
    # distance INSIDE the teeth, and the nearest outside voxel for each
    dist, ind = ndi.distance_transform_edt(occ, sampling=(sp[2], sp[1], sp[0]),
                                           return_indices=True)
    # SIGNED: positive inside a tooth, negative outside. Without the outside
    # half, "far enough clear" cannot be asked -- only "inside or not" -- and a
    # tube sitting flush against a root passes that test while half its surface
    # is in dentin.
    outside = ndi.distance_transform_edt(~occ, sampling=(sp[2], sp[1], sp[0]))
    signed = dist - outside
    shape = _np.array(occ.shape)

    def to_idx(w):
        w = _np.atleast_2d(_np.asarray(w, float))
        return _np.stack([(w[:, 2] - o[2]) / sp[2],
                          (w[:, 1] - o[1]) / sp[1],
                          (w[:, 0] - o[0]) / sp[0]], 1)

    def depth(w):
        """Signed depth, sampled TRILINEARLY.

        Nearest-neighbour sampling quantises this field to the voxel grid, so a
        point 0.08 mm clear of a root rounds into the voxel inside it and reads
        as 0.16 mm deep -- exactly one voxel, which is what two branches
        reported no matter how many clearing passes they were given. The
        clearances being asked about here are smaller than a voxel, so the field
        has to be interpolated rather than looked up.
        """
        idx = to_idx(w)
        ok = _np.all((idx >= 0) & (idx < (shape - 1)[None, :]), axis=1)
        d = _np.zeros(len(idx))
        if ok.any():
            d[ok] = ndi.map_coordinates(signed, idx[ok].T, order=1,
                                        mode="nearest")
        return d

    def escape(w, margin_mm=0.25):
        """Move any point inside a tooth to just outside the nearest surface."""
        w = _np.array(_np.atleast_2d(_np.asarray(w, float)), float)
        i = _np.round(to_idx(w)).astype(int)
        ok = _np.all((i >= 0) & (i < shape[None, :]), axis=1)
        out = w.copy()
        for n in _np.nonzero(ok)[0]:
            z, y, x = i[n]
            if signed[z, y, x] <= -margin_mm:
                continue
            nz, ny, nx = ind[0][z, y, x], ind[1][z, y, x], ind[2][z, y, x]
            near = _np.array([o[0] + nx * sp[0], o[1] + ny * sp[1],
                              o[2] + nz * sp[2]])
            d = near - w[n]
            L = float(_np.linalg.norm(d))
            out[n] = near + (d / L) * margin_mm if L > 1e-6 else near
        return out

    return depth, escape


def palatal_surface(points, bone_at, tooth_at=None,
                    up=np.array([0.0, 0.0, 1.0]),
                    reach_mm=GP_RAY_MM, step=0.15, below=GP_BELOW_MM):
    """Cast UP onto the hard palate and sit just under it.

    A ray that starts below the palate in the oral cavity meets the palatal
    plate first and can meet nothing else, which is rule 139's argument for
    casting inward to find skin, used on a different surface. Taking the lowest
    bone voxel in each column instead is what a first attempt did, and it picks
    up the alveolar process, the nasal floor and the incisive canal wherever
    those are lower than the palate -- the readings jumped 10 mm between
    adjacent stations.
    """
    out = []
    n = int(reach_mm / step)
    for p0 in np.asarray(points, float):
        hit = None
        for k in range(n):
            q = p0 + up * (k * step)
            # A COLUMN THROUGH A PALATAL ROOT IS NOT PALATE. The upper teeth are
            # their own labels, so they are holes in the bone mask and a ray
            # fired under a palatal root passes straight through it and stops on
            # the bone ABOVE -- which puts the artery inside the root. It did,
            # 2.35 mm deep. Meeting a tooth first means this station is too
            # lateral; the caller steps it medially and tries again.
            if tooth_at is not None and tooth_at(q):
                hit = None
                break
            if bone_at(q):
                hit = q
                break
        out.append((hit - up * below) if hit is not None else None)
    return out


def route(curve, depth, escape, snap=None, keep_tail=2, radii=None, passes=3):
    """Into BONE, then out of DENTIN, and dentin gets the last word.

    The maxillary vessels run in bony canals through the alveolar process and
    across the palate; a course laid on an arc between apices floats out of the
    bone wherever the arch is concave, which is nerve_maxilla's own finding
    about its nerves -- 72% of that mesh was outside bone, a median of 3.5 mm
    and up to 10.1 mm, floating in the sinus, until it was confined.

    The two constraints FIGHT, and the order is not arbitrary. maxilla_bone
    fills each slice, so the teeth are part of the bone mask and snapping to
    "nearest bone" can land a point inside a root. Confining first and clearing
    second means the tooth push is what survives, which is rule 137's
    discipline: whichever constraint must hold absolutely goes last.
    """
    c = np.array(curve, float)
    for _ in range(passes):
        if snap is not None:
            c = NM.confine(c, snap, passes=1)
            c[-keep_tail:] = np.array(curve, float)[-keep_tail:]
        c = clear_of_teeth(c, depth, escape, keep_tail=keep_tail, radii=radii,
                           passes=4)
    # THE LAST WORD, and it has to be a long one. Both bone masks FILL the
    # teeth -- nerve.bone_test unions the lower-tooth class into the mandible
    # and maxilla_bone fills each slice -- so "snap to the nearest bone" can
    # land a point inside a root, and a single confine pass after the clearing
    # loop put two branches back a voxel deep. A final clearing with no
    # confinement behind it is what actually holds.
    return clear_of_teeth(c, depth, escape, keep_tail=keep_tail, radii=radii,
                          passes=12)


def clear_of_teeth(curve, depth, escape, keep_tail=2, passes=8, radii=None):
    """Re-route a branch so only its TIP is in the tooth.

    The last `keep_tail` samples are left alone: a dental branch ends at the
    apical foramen, which is on the root, and pulling that out would disconnect
    the vessel from the tooth it supplies. Everything before it is pushed out
    and re-smoothed, and the push gets the last word -- smoothing between pushes
    can drag a point back through a thin root, which is nerve_face.ride()'s
    lesson (rule 137) applied to a different obstacle.

    `radii` MATTERS AND WAS MISSING AT FIRST. What gets rendered is a TUBE, so a
    centreline pushed exactly to the tooth surface still buries half the vessel:
    the first version cleared every centreline and the meshes still had 7-10% of
    their vertices inside dentin. The clearance a point needs is its own radius
    plus a margin, not zero.
    """
    if depth is None:
        return curve
    c = np.array(curve, float)
    n = len(c)
    body = slice(0, max(n - keep_tail, 1))
    r = (np.full(n, 0.0) if radii is None
         else np.asarray(radii, float) * np.ones(n))
    want = r[body] + 0.06
    for _ in range(passes):
        d = depth(c[body])
        bad = d > -want            # inside, or not far enough outside
        if not bad.any():
            break
        moved = c.copy()
        moved[body] = np.where(bad[:, None],
                               escape(c[body], margin_mm=want.max()), c[body])
        moved = N.smooth_path(moved, passes=2)
        moved[-keep_tail:] = c[-keep_tail:]
        moved[0] = c[0]
        c = moved
    d = depth(c[body])
    bad = d > 0
    if bad.any():
        c[body] = np.where(bad[:, None],
                           escape(c[body], margin_mm=want.max()), c[body])
    return c


def main():
    args = sys.argv[1:]
    canal_path, outdir = args[0], args[1]
    opt = {}
    i = 2
    while i < len(args) - 1:
        opt[args[i].lstrip("-")] = args[i + 1]
        i += 2
    os.makedirs(outdir, exist_ok=True)

    # WHAT THIS WAS BUILT FROM. See nerve_maxilla.py for why.
    report = dict(inputs={k: os.path.abspath(v) for k, v in
                          sorted(opt.items()) if v},
                  canal=os.path.abspath(canal_path),
                  provenance=dict(
        canal="MEASURED (CBCT; the mandibular canal segmented and fused, the "
              "infraorbital and mental canals hand-traced by the operator)",
        artery="DERIVED (a tube of chosen calibre at a chosen offset inside the "
               "measured lumen; CBCT does not resolve the canal's contents)",
        arrangement="Superior to the nerve and lingual of the vein, from Kim "
                    "and Pogrel via J Oral Maxillofac Res 2010;1(1):e2. The "
                    "site-dependent rotation those series also report is NOT "
                    "modelled -- one constant offset runs the whole canal.",
        veins="TAH ids, because the FMA names none of these veins.",
        branches="INFERRED (both ends measured -- a trunk on a measured canal "
                 "and a measured apical foramen -- and the path between them "
                 "is convention, re-routed where it would cross dentin)"),
        vessels=[])

    # THE TOOTH FIELD, loaded before anything is drawn. Every dental branch is
    # routed against it: a vessel may END at an apical foramen but must not
    # TRAVEL through hard tissue to get there.
    depth = escape = None
    if opt.get("split"):
        from vol import Volume
        _v = Volume.load(opt["vol"]) if opt.get("vol") else None
        if _v is not None:
            depth, escape = tooth_field(opt["split"], _v)
            print("tooth field loaded — branches will be routed out of dentin")
    if depth is None:
        print("NO TOOTH FIELD (--split/--vol not given): branches are NOT "
              "checked against dentin")

    # BONE. Both tests come from the nerve modules rather than being rebuilt:
    # nerve.bone_test fills the mandible (the canal and the lower teeth are
    # separate classes, so a bare `lab == 2` calls every point inside the canal
    # OUTSIDE the bone -- it read 0 of 209 trunk points before that fill), and
    # nerve_maxilla.maxilla_bone unions the centred volume's hard tissue with
    # the maxillary exposure's upper skull.
    mand_snap = max_snap = max_frac = None
    if opt.get("pred") and os.path.exists(opt["pred"]):
        _, mand_snap, _ = N.bone_test(opt["pred"], N.ORIGIN, N.SPACING)
        max_snap, max_frac = NM.maxilla_bone(
            opt["pred"], opt.get("pred_max"), opt.get("xf"), opt["vol"])
        print("bone tests loaded — courses will be confined to measured bone")
    else:
        print("NO BONE TEST (--pred not given): courses are NOT confined")

    drawn_curves = []          # (mesh, curve, tube radius) for the dentin check

    def track(name, curve, radius):
        drawn_curves.append((name, np.asarray(curve, float), float(radius)))

    def emit(name, chunks):
        if not chunks:
            return
        v = np.vstack([c[0] for c in chunks])
        f, off = [], 0
        for cv, cf in chunks:
            f.append(cf + off); off += len(cv)
        write_binary_stl(os.path.join(outdir, name), v, np.vstack(f))

    # --- mandibular canal: artery and vein share it with the nerve -----------
    # Measured aspect here is 1.17, i.e. very nearly round, so the equivalent
    # circle IS the lumen and the superior-annulus rule holds. That is a
    # measurement, not an assumption -- the infraorbital canal next door is
    # 2.0:1 and needs the other treatment entirely.
    canal = np.load(canal_path)
    meta = os.path.join(os.path.dirname(canal_path), "canal.json")
    off0 = np.array(json.load(open(meta)).get("grid_offset", [0, 0, 0])
                    if os.path.exists(meta) else [0, 0, 0])
    lines = N.canal_centrelines(canal, off0)
    print(f"mandibular canal — {len(lines)} measured centrelines")
    art, vein = [], []
    art_course, vein_course = {}, {}
    for ln in lines:
        p, r = np.asarray(ln["points"], float), np.asarray(ln["radius"], float)
        ca = offset_course(p, r, ART_OFFSET, ART_LINGUAL_DEG)
        cv = offset_course(p, r, ART_OFFSET, VEIN_LINGUAL_DEG)
        art_course[ln["side"]] = ca
        vein_course[ln["side"]] = cv
        for tag, c, rad, fma, bag in (
                ("artery", ca, ART_RADIUS * r, "FMA49695", art),
                ("vein  ", cv, VEIN_RADIUS * r, "TAHU15802", vein)):
            out = N.tube(c, rad)
            if out is None:
                continue
            bag.append(out)
            st = check(p, c, r, rad, N.NERVE_FRACTION * r,
                       f"{ln['side']:5s} {tag}")
            st.update(side=ln["side"], canal="mandibular",
                      mean_radius_mm=round(float(rad.mean()), 3))
            report["vessels"].append(dict(fma=fma, **st))
    # the two vessels must also clear EACH OTHER
    for ln in lines:
        p, r = np.asarray(ln["points"], float), np.asarray(ln["radius"], float)
        d = np.linalg.norm(offset_course(p, r, ART_OFFSET, ART_LINGUAL_DEG)
                           - offset_course(p, r, ART_OFFSET, VEIN_LINGUAL_DEG),
                           axis=1)
        gap = d - (ART_RADIUS + VEIN_RADIUS) * r
        print(f"    {ln['side']:5s} artery-vein gap: {gap.min():+.3f} mm worst "
              f"({100*(gap < 0).mean():.0f}% touching)")
    emit("artery-inferior-alveolar.stl", art)
    emit("vein-inferior-alveolar.stl", vein)

    # The apices and the mental foramina both come from the shipped
    # docs/cbct-nerve.json, so the vessels hang off exactly the landmarks
    # the nerve already uses and cannot disagree with it about where a
    # tooth is.
    nerve_json = os.path.join(ROOT, "docs", "cbct-nerve.json")
    fora = (json.load(open(nerve_json)).get("mental_foramina", {})
            if os.path.exists(nerve_json) else {})

    # --- infraorbital canal: along its MEASURED major axis -------------------
    if opt.get("io") and os.path.exists(opt["io"]):
        d = json.load(open(opt["io"]))
        print("infraorbital canal — packed along the measured major axis")
        ioa, iov = [], []
        for side, srec in d["sides"].items():
            q = srec["points"]
            if "semi_major_mm" not in q[0]:
                print(f"    {side}: no cross-section measured — "
                      "re-run io_centreline.py"); continue
            p = np.array([x["p"] for x in q], float)
            a = np.array([x["semi_major_mm"] for x in q], float)
            b = np.array([x["semi_minor_mm"] for x in q], float)
            mj = np.array([x["major_axis_lps"] for x in q], float)
            # the nerve's own drawn ramp, in this file's anterior-first order
            nr = np.linspace(IO_NERVE_R_MM[0], IO_NERVE_R_MM[1], len(p))
            # HOW MUCH OF THE DRAWN NERVE IS ALREADY OUTSIDE ITS OWN CANAL?
            # Everything below is packing around that mesh, so its own fit is
            # the honest context for any residual overlap: where the nerve is
            # wider than the lumen, nothing can be placed beside it.
            aa, bb = smooth1d(a), smooth1d(b)
            print(f"    {side:5s} nerve vs measured lumen: exceeds the SHORT "
                  f"semi-axis at {100*(nr > bb).mean():.0f}% of samples "
                  f"(by up to {float((nr - bb).max()):.2f} mm), the LONG one at "
                  f"{100*(nr > aa).mean():.0f}%")
            report.setdefault("infraorbital_nerve_fit", []).append(dict(
                side=side,
                pct_wider_than_semi_minor=round(float(100*(nr > bb).mean()), 1),
                worst_mm_over_semi_minor=round(float((nr - bb).max()), 3),
                pct_wider_than_semi_major=round(float(100*(nr > aa).mean()), 1)))
            ca, cv, rv, geom = elliptical_offsets(p, a, b, mj, nr)
            for tag, c, fma, bag in (("artery", ca, "FMA49767", ioa),
                                     ("vein  ", cv, "TAHU15485", iov)):
                out = N.tube(c, rv)
                if out is None:
                    continue
                bag.append(out)
                st = check_ellipse(p, c, a, b, mj, rv, nr, f"{side:5s} {tag}")
                st.update(side=side, canal="infraorbital", **geom)
                st["held"] = st["pct_into_nerve"] > 50.0
                report["vessels"].append(dict(fma=fma, **st))
        emit("artery-infraorbital.stl", ioa)
        emit("vein-infraorbital.stl", iov)

    # --- incisive artery and vein, and the lower dental branches -------------
    #
    # The incisive vessels are the CONTINUATION of the inferior alveolar ones
    # past the mental foramen, and they are what supplies teeth 22-27: a chord
    # from the canal to a central incisor is 22-26 mm and runs through bone,
    # which is why nerve.py hangs the anterior teeth off the incisive nerve
    # rather than off the trunk. The vessels have to do the same or the anterior
    # teeth simply have no blood supply drawn.
    apex_of = {}
    if os.path.exists(nerve_json):
        for b in json.load(open(nerve_json)).get("branches", []):
            if b.get("apex_lps"):
                apex_of[int(b["universal"])] = np.array(b["apex_lps"], float)
    inc_art, inc_vein, inc_course = [], [], {}
    if fora and apex_of:
        for side, f0 in fora.items():
            m = np.array(f0, float)
            ant = [a for u, a in apex_of.items()
                   if a[1] < m[1] and (a[0] < DENTAL_MIDLINE_X) == (side == "right")]
            if len(ant) < 2:
                continue
            path = N.incisive_path(m, ant, snap=mand_snap)
            if path is None:
                continue
            path = route(path, depth, escape, snap=mand_snap, keep_tail=1,
                         radii=INCISIVE_VEIN_R_MM[0])
            inc_course[side] = path
            for bag, r in ((inc_art, INCISIVE_ART_R_MM),
                           (inc_vein, INCISIVE_VEIN_R_MM)):
                o = N.tube(path, N.taper(len(path), *r))
                if o:
                    bag.append(o)
        print(f"incisive vessels — {len(inc_course)} sides")
        emit("artery-incisive.stl", inc_art)
        emit("vein-incisive.stl", inc_vein)

    def dental(courses, r_mm, label):
        """One branch per measured apex, from whichever parent is nearest."""
        out, drawn = [], []
        for u, apex in sorted(apex_of.items()):
            side = "right" if apex[0] < DENTAL_MIDLINE_X else "left"
            cands = [c for c in (courses.get(("inc", side)),
                                 courses.get(("trunk", side))) if c is not None]
            if not cands:
                continue
            best, bk, bd = None, 0, 1e9
            for c in cands:
                k = int(np.argmin(np.linalg.norm(c - apex[None, :], axis=1)))
                d = float(np.linalg.norm(c[k] - apex))
                if d < bd:
                    best, bk, bd = c, k, d
            if bd > DENTAL_MAX_MM:
                continue
            curve = route(N.branch_curve(best[bk], apex), depth, escape,
                          snap=mand_snap, radii=r_mm[0])
            o = N.tube(curve, N.taper(len(curve), *r_mm))
            if o:
                out.append(o); drawn.append(u)
                track(label, curve, r_mm[0])
        missed = sorted(set(apex_of) - set(drawn))
        print(f"{label} — {len(drawn)} of {len(apex_of)} measured apices"
              + (f", not drawn {missed}" if missed else ""))
        return out, drawn, missed

    courses_a = {("trunk", s_): c for s_, c in art_course.items()}
    courses_a.update({("inc", s_): c for s_, c in inc_course.items()})
    courses_v = {("trunk", s_): c for s_, c in vein_course.items()}
    courses_v.update({("inc", s_): c for s_, c in inc_course.items()})
    da, drawn_a, miss_a = dental(courses_a, (DENTAL_ROOT_R_MM, DENTAL_TIP_R_MM),
                                 "lower dental arteries")
    dv, drawn_v, miss_v = dental(courses_v, (DENTAL_ROOT_R_MM, DENTAL_TIP_R_MM),
                                 "lower dental veins")
    emit("artery-dental-lower.stl", da)
    emit("vein-dental.stl", dv)
    report["vessels"].append(dict(fma="FMA49699", canal="mandibular",
                                  branches=len(drawn_a), teeth=drawn_a,
                                  not_drawn=miss_a))
    report["vessels"].append(dict(fma="TAHU15803", canal="mandibular",
                                  branches=len(drawn_v), teeth=drawn_v,
                                  not_drawn=miss_v))

    # --- mental artery, out of the measured foramen -------------------------
    if opt.get("mental") and os.path.exists(opt["mental"]):
        if fora:
            print("mental artery — from the measured mental foramen")
            ma, mv = [], []
            for side, f0 in fora.items():
                path = N.mental_path(np.array(f0, float), side)
                out = N.tube(path, N.taper(len(path), *MENTAL_ART_R_MM))
                if out is None:
                    continue
                ma.append(out)
                # THE VEIN GOES WITH IT. Same foramen, same course, drawn a
                # little larger and offset buccally.
                vpath = path + np.array([0.0, 0.0, -0.45])
                ov = N.tube(vpath, N.taper(len(vpath), MENTAL_ART_R_MM[0] * 1.15,
                                           MENTAL_ART_R_MM[1] * 1.15))
                if ov:
                    mv.append(ov)
                print(f"    {side:5s}: {MENTAL_RUN_MM:.1f} mm run, "
                      f"r {MENTAL_ART_R_MM[0]:.2f} -> {MENTAL_ART_R_MM[1]:.2f} mm "
                      "(artery and vein)")
                report["vessels"].append(dict(
                    fma="FMA49701", side=side, canal="mental",
                    points=int(len(path)), run_mm=MENTAL_RUN_MM,
                    note="drawn on the mental nerve's own course out of the "
                         "foramen; the two run together"))
            emit("artery-mental.stl", ma)
            emit("vein-mental.stl", mv)

    # --- maxillary: the superior alveolar vessels ---------------------------
    #
    # Built on the SAME arc nerve_maxilla.py builds its plexus on -- a smooth
    # curve through points set PLEXUS_ABOVE_MM beyond each measured apex, away
    # from that tooth's own centre -- with the artery offset buccally and the
    # vein lingually off it. Sharing the construction is the point: three
    # independent guesses at one course would drift apart, and the arch is the
    # only thing here that is anchored to measured foramina.
    #
    # PSA and ASA are separate meshes with exact ids of their own rather than
    # one "superior alveolar" mesh, because the FMA names them separately and
    # they arise separately -- PSA from the maxillary artery in the
    # pterygopalatine fossa, ASA from the infraorbital artery inside its canal.
    # The premolars are MSA territory, which is present in perhaps half of
    # people and has no separate artery in the FMA; they are drawn on the PSA
    # here and the provenance says so.
    if opt.get("pulp") and os.path.exists(opt["pulp"]) and opt.get("split"):
        pulp = json.load(open(opt["pulp"]))["teeth"]
        sp_j = json.load(open(os.path.join(opt["split"], "split.json")))
        centre = {t["universal"]: np.array(t["world"], float)
                  for t in sp_j["upper"]["teeth"]}
        nodes, targets, owners = [], [], []
        for rec in pulp.values():
            if rec.get("arch") != "upper":
                continue
            u = int(rec["universal"])
            c = centre.get(u)
            for f in rec.get("foramina", []):
                w = np.array(f["world_lps"], float)
                d = w - c if c is not None else np.array([0.0, 0.0, 1.0])
                n = float(np.linalg.norm(d))
                d = d / n if n > 1e-6 else np.array([0.0, 0.0, 1.0])
                nodes.append(w + d * PLEXUS_ABOVE_MM)
                targets.append(w)
                owners.append(u)
        if nodes:
            nodes = np.array(nodes); targets = np.array(targets)
            owners = np.array(owners)
            order = np.argsort(np.arctan2(nodes[:, 1] - nodes[:, 1].mean(),
                                          nodes[:, 0] - nodes[:, 0].mean()))
            arc = N.smooth_path(nodes[order], passes=4)
            # buccal is away from the arch's own centre in the occlusal plane
            mid = arc.mean(0)
            rad = arc - mid; rad[:, 2] = 0.0
            rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
            a_arc = route(arc + rad * MAX_ART_OFFSET_MM, depth, escape,
                          snap=max_snap, keep_tail=1, radii=MAX_TRUNK_R_MM)
            v_arc = route(arc + rad * MAX_VEIN_OFFSET_MM, depth, escape,
                          snap=max_snap, keep_tail=1, radii=MAX_TRUNK_R_MM)
            if max_frac is not None:
                print(f"    arc confined to bone: artery "
                      f"{100*max_frac(a_arc):.0f}%, vein "
                      f"{100*max_frac(v_arc):.0f}% of samples inside measured "
                      f"bone (was {100*max_frac(arc):.0f}% unconfined)")
            post = np.isin(owners[order], sorted(PSA_TEETH | MSA_TEETH))
            def run(curve, sel):
                seg = curve[sel]
                return seg if len(seg) >= 3 else None
            for tag, curve, sel, fma, fn in (
                    ("PSA artery", a_arc, post, "FMA49757",
                     "artery-psa.stl"),
                    ("ASA artery", a_arc, ~post, "FMA49771",
                     "artery-asa.stl"),
                    ("PSA veins ", v_arc, post, "TAHU15800",
                     "vein-psa.stl")):
                seg = run(curve, sel)
                if seg is None:
                    continue
                o = N.tube(seg, np.full(len(seg), MAX_TRUNK_R_MM))
                if o:
                    emit(fn, [o])
                    print(f"maxillary {tag}: {len(seg)} samples, "
                          f"{float(np.linalg.norm(np.diff(seg,axis=0),axis=1).sum()):.1f} mm")
                    report["vessels"].append(dict(fma=fma, canal="maxillary",
                                                  samples=int(len(seg))))
            # Dental branches, SPLIT BY TERRITORY so each carries its exact
            # id. One "upper dental" mesh would have to be filed under either
            # the anterior or the posterior superior alveolar artery, and would
            # then be wrong about half its own branches -- the same class of
            # mislabel invariant 7 exists to catch, self-inflicted.
            post_t = PSA_TEETH | MSA_TEETH
            for tag, curve, fma, fn, sel_post in (
                    ("upper dental arteries, post", a_arc, "FMA49761",
                     "artery-dental-upper-post.stl", True),
                    ("upper dental arteries, ant", a_arc, "FMA49775",
                     "artery-dental-upper-ant.stl", False),
                    ("upper dental veins, post", v_arc, "TAHU15800B",
                     "vein-dental-upper-post.stl", True),
                    ("upper dental veins, ant", v_arc, "TAHU15485B",
                     "vein-dental-upper-ant.stl", False)):
                bag, drawn = [], []
                for i in range(len(targets)):
                    if (int(owners[i]) in post_t) != sel_post:
                        continue
                    apex = targets[i]
                    k = int(np.argmin(np.linalg.norm(curve - apex[None, :],
                                                     axis=1)))
                    cu = route(N.branch_curve(curve[k], apex, bulge=0.2),
                               depth, escape, snap=max_snap,
                               radii=MAX_BRANCH_R_MM[0])
                    o = N.tube(cu, N.taper(len(cu), *MAX_BRANCH_R_MM))
                    if o:
                        bag.append(o); drawn.append(int(owners[i]))
                        track(tag, cu, MAX_BRANCH_R_MM[0])
                emit(fn, bag)
                print(f"{tag:30s}: {len(bag)} branches to "
                      f"{len(set(drawn))} teeth {sorted(set(drawn))}")
                report["vessels"].append(dict(fma=fma, canal="maxillary",
                                              branches=len(bag),
                                              teeth=sorted(set(drawn))))

    # --- greater palatine artery, on the palate itself ----------------------
    if opt.get("pred") and opt.get("split") and depth is not None:
        from read_nifti import read_nifti as _rn
        _lab, _, _ = _rn(opt["pred"])
        _up = np.load(os.path.join(opt["split"], "upper_labels.npy")) > 0
        _pal = ndi.binary_closing((_lab == 1) & ~_up, np.ones((3, 3, 3)))
        _o = np.array(_v.origin, float); _sp = np.array(_v.spacing, float)
        _sh = np.array(_pal.shape)

        def bone_at(w):
            i = np.round([(w[2] - _o[2]) / _sp[2], (w[1] - _o[1]) / _sp[1],
                          (w[0] - _o[0]) / _sp[0]]).astype(int)
            if np.any(i < 0) or np.any(i >= _sh):
                return False
            return bool(_pal[tuple(i)])

        sj = json.load(open(os.path.join(opt["split"], "split.json")))
        gp, gpn, gpv = [], [], []
        for side in ("right", "left"):
            sign = -1.0 if side == "right" else 1.0
            # stations along this side's arch, posterior -> anterior, taken
            # from the MEASURED tooth centroids and stepped toward the midline
            tt = sorted([t for t in sj["upper"]["teeth"]
                         if (t["world"][0] < DENTAL_MIDLINE_X) == (side == "right")],
                        key=lambda t: -t["world"][1])
            if len(tt) < 4:
                continue
            def tooth_at(w):
                return bool(depth(np.atleast_2d(w))[0] > 0)

            # FIND THE GUTTER, do not guess a fraction of the way to the
            # midline. The palate is a vault, so at any coronal station its
            # LOWEST point on each side is the lateral gutter between the
            # midline ridge and the alveolar process -- which is where the
            # greater palatine groove runs. Stepping medially from each tooth
            # centroid instead found 5 of 7 stations on the right and 3 of 7 on
            # the left, because near the front the column above that offset is
            # the incisive canal and the nasal floor, not palate.
            ys = [t["world"][1] for t in tt]
            zref = float(np.mean([t["world"][2] for t in tt]))
            # THE SCAN IS BOUNDED BY THE MEASURED PALATAL WALL, and then
            # takes the LOWEST palatal surface inside that bound.
            #
            # Three definitions were tried and only this one both covers the
            # palate and sits in the groove. Stepping medially from each tooth
            # CENTROID found 5 of 7 stations on one side and 3 of 7 on the
            # other, because near the front the column above that offset is the
            # incisive canal and the nasal floor. Taking the lowest bone with no
            # bound put the artery at z -8 in the oral cavity, because the
            # ALVEOLAR PROCESS hangs lower than the vault does. Placing it at a
            # fixed fraction of the way out to the wall sits correctly but only
            # reaches 11 and 13 stations, losing the anterior third.
            #
            # Bounding the scan by the wall and then taking the lowest surface
            # inside it gets 20 and 17 stations over the full 44 and 39 mm, and
            # the sections show it under the vault at every level. The bound is
            # measured: the most medial upper-tooth voxel at that level.
            _o2 = np.array(_v.origin, float); _sp2 = np.array(_v.spacing, float)
            pts = []
            for y0 in np.arange(min(ys) - 1.0, max(ys) + 1.0, 2.0):
                jy = int(round((y0 - _o2[1]) / _sp2[1]))
                if not (0 <= jy < _up.shape[1]):
                    continue
                cols = np.nonzero(_up[:, jy, :].any(axis=0))[0]
                if not cols.size:
                    continue
                xs = _o2[0] + cols * _sp2[0]
                same = xs[(xs < DENTAL_MIDLINE_X) == (side == "right")]
                if not same.size:
                    continue
                wall = float(np.min(np.abs(same - DENTAL_MIDLINE_X)))
                hi = max(wall - 1.5, 3.5)
                best = None
                for d in np.arange(2.5, hi, 0.5):
                    cand = np.array([DENTAL_MIDLINE_X + sign * d, y0,
                                     zref - 6.0])
                    r = palatal_surface([cand], bone_at, tooth_at)[0]
                    if r is None:
                        continue
                    if best is None or r[2] < best[2]:
                        best = r
                if best is not None:
                    pts.append(best)
            print(f"    {side:5s}: {len(pts)} coronal stations found a palatal "
                  "gutter")
            if len(pts) < 5:
                print(f"    {side:5s}: too few — not drawn")
                continue
            pts = sorted(pts, key=lambda q: -q[1])      # posterior -> anterior
            course = N.smooth_path(np.array(pts, float), passes=3)
            # SMOOTHING PULLS A COURSE INTO A CONCAVE SURFACE. The palate is a
            # vault, so a curve smoothed across stations that hug it moves
            # toward the chord, which is up into the bone -- it came out 67%
            # inside. Drop each point back out along -z after the smoothing.
            def drop_below_bone(c):
                out = []
                for q in np.asarray(c, float):
                    q = np.array(q, float)
                    for _ in range(int(GP_RAY_MM / 0.1)):
                        if not bone_at(q):
                            break
                        q = q - np.array([0.0, 0.0, 0.1])
                    out.append(q - np.array([0.0, 0.0, GP_BELOW_MM]))
                return np.array(out)

            # The two pushes FIGHT here as well, and the other way round from
            # everywhere else: clearing a palatal root moves a point sideways
            # and can put it back under the vault, while dropping out of the
            # vault can slide it under a root. Alternate, and let the tooth
            # clearance be last -- dentin is the constraint that must hold.
            for _ in range(3):
                course = drop_below_bone(course)
                course = clear_of_teeth(course, depth, escape, keep_tail=1,
                                        radii=GP_RADIUS_MM[0], passes=6)
            # across the groove: medial-lateral, in the occlusal plane
            tang = np.gradient(course, axis=0)
            tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
            across = np.cross(tang, np.array([0.0, 0.0, 1.0]))
            across /= np.maximum(np.linalg.norm(across, axis=1, keepdims=True), 1e-9)
            # orient it toward the midline, per point (rule 158)
            want = np.sign(DENTAL_MIDLINE_X - course[:, 0])
            have = np.sign(across[:, 0]); have[have == 0] = 1.0
            across *= np.where(want * have < 0, -1.0, 1.0)[:, None]
            for nm, off_mm, rr, bag in (
                    ("greater palatine nerve", +GP_SPREAD_MM, GP_NERVE_R_MM, gpn),
                    ("greater palatine artery", 0.0, GP_RADIUS_MM, gp),
                    ("greater palatine vein", -GP_SPREAD_MM, GP_VEIN_R_MM, gpv)):
                c2 = course + across * off_mm
                c2 = clear_of_teeth(c2, depth, escape, keep_tail=1, radii=rr[0])
                o_ = N.tube(c2, N.taper(len(c2), *rr))
                if o_:
                    bag.append(o_)
                    track(nm, c2, rr[0])
            if True:
                inb = float(np.mean([bone_at(w) for w in course]))
                print(f"greater palatine artery {side:5s}: {len(course)} stations, "
                      f"{float(np.linalg.norm(np.diff(course,axis=0),axis=1).sum()):.1f} mm, "
                      f"{100*inb:.0f}% inside bone (should be ~0 — it runs ON the palate)")
                report["vessels"].append(dict(
                    fma="FMA49795", side=side, canal="palate",
                    samples=int(len(course)),
                    pct_inside_bone=round(100 * inb, 1)))
        emit("artery-greater-palatine.stl", gp)
        emit("nerve-greater-palatine.stl", gpn)
        emit("vein-greater-palatine.stl", gpv)

    # --- VERIFY: nothing TRAVELS through dentin -----------------------------
    #
    # A dental branch ENDS at an apical foramen, which is on the root, so its
    # last fraction of a millimetre is inside hard tissue by design -- that is
    # the connection, not a defect, and a raw "percent of the mesh inside a
    # tooth" cannot tell the two apart. It reported 7-12% on branches that were
    # correct. What must not happen is a vessel crossing dentin ON THE WAY:
    # through a neighbouring root, or in one side of a root and out the other.
    # So contact is measured against DISTANCE FROM THE ENDPOINTS.
    if depth is not None and drawn_curves:
        print("\ndentin check — does any vessel TRAVEL through hard tissue?")
        rows, offenders, total = {}, 0, 0
        for name, cu, r in drawn_curves:
            u_ = np.concatenate([[0.0], np.cumsum(
                np.linalg.norm(np.diff(cu, axis=0), axis=1))])
            if u_[-1] < 1e-6:
                continue
            dense = np.stack([np.interp(np.linspace(0, u_[-1], 200), u_, cu[:, k])
                              for k in range(3)], 1)
            d = np.maximum(depth(dense), 0.0)
            from_end = np.minimum(
                np.linalg.norm(dense - dense[-1][None, :], axis=1),
                np.linalg.norm(dense - dense[0][None, :], axis=1))
            # A graze SHALLOWER THAN ONE VOXEL is not a resolvable claim: the
            # tooth boundary itself is only known to 0.16 mm. Counted and named
            # separately rather than folded into the tolerance, because moving
            # the threshold until the number reads zero is how a check stops
            # meaning anything.
            travel = (d > VOXEL_MM) & (from_end > DENTIN_TIP_MM)
            graze = (d > 0) & (d <= VOXEL_MM) & (from_end > DENTIN_TIP_MM)
            rec = rows.setdefault(name, dict(n=0, travelling=0, grazing=0,
                                             worst_mm=0.0,
                                             worst_from_end_mm=0.0))
            rec["n"] += 1; total += 1
            if graze.any() and not travel.any():
                rec["grazing"] += 1
                rec["worst_mm"] = round(max(rec["worst_mm"],
                                            float(d[graze].max())), 3)
            if travel.any():
                rec["travelling"] += 1
                offenders += 1
                rec["worst_mm"] = round(max(rec["worst_mm"],
                                            float(d[travel].max())), 3)
                rec["worst_from_end_mm"] = round(max(
                    rec["worst_from_end_mm"], float(from_end[travel].max())), 2)
        for name, rec in sorted(rows.items()):
            tag = "OK" if not rec["travelling"] else "TRAVELS"
            extra = ("" if not rec["travelling"] else
                     f" (deepest {rec['worst_mm']:.2f} mm, "
                     f"{rec['worst_from_end_mm']:.1f} mm from an end)")
            gz = (f", {rec['grazing']} grazing <= 1 voxel "
                  f"({rec['worst_mm']:.2f} mm)" if rec["grazing"] else "")
            print(f"  {name:24s} {rec['n']:3d} courses, "
                  f"{rec['travelling']:3d} travelling  {tag}{gz}{extra}")
        grazes = sum(r["grazing"] for r in rows.values())
        print(f"  -> {offenders} of {total} courses travel through dentin more "
              f"than {DENTIN_TIP_MM} mm from an endpoint"
              + (f"; {grazes} graze it by less than one voxel ({VOXEL_MM} mm), "
                 "which is finer than the tooth boundary is known"
                 if grazes else ""))
        report["dentin_check"] = dict(tip_allowance_mm=DENTIN_TIP_MM,
                                      by_mesh=rows, travelling=offenders,
                                      courses=total)

    json.dump(report, open(os.path.join(outdir, "vessels.json"), "w"), indent=1)
    print(f"\nwrote {outdir}")


if __name__ == "__main__":
    main()
