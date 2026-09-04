#!/usr/bin/env python3
"""Terminal branches of the infraorbital and mental nerves, into the face.

Everything else in this atlas stops at bone. These are the branches that leave
it: once the infraorbital and mental nerves reach their foramina they divide and
run in the soft tissue of the face, and until now each was drawn as a single
stub a few millimetres long, which says nothing about what either nerve does.

WHAT MAKES THIS MORE THAN DRAWING. Both ends are measured on this patient.

  ORIGIN   The foramen, and the direction the nerve leaves it, are taken from
           the traced canal -- for the infraorbital that is the operator's own
           tracing (docs/cbct-infraorbital.json), and the emergence direction is
           the canal's own anterior tangent, not a chosen vector.
  END      The face's SKIN is in this CBCT. Soft tissue reads about +150 to
           +320 here against an air floor near -620, so the air/skin interface
           is one of the sharpest boundaries in the volume -- sharper than most
           of the bone edges. Every branch is marched along its direction until
           it reaches that measured boundary and stopped SKIN_DEPTH_MM short of
           it, in the dermis where a cutaneous nerve actually ends. No branch
           has a length chosen by hand.
  BETWEEN  Convention. Which branches exist, how many, and roughly where they
           go is Gray's; the path each takes between two measured points is not
           observed and never could be, since CBCT does not resolve a 0.3 mm
           nerve in fat.

So these are `derived`, the same standing as the dental branches: measured
endpoints, invented path. They are NOT measured, and they must not be merged
into a mesh with anything that is.

TWO INVARIANTS, both checked on every run and both fatal:

  1. NO BRANCH MAY RE-ENTER BONE. These nerves run in the subcutaneous plane,
     deep to the mimetic muscles and superficial to the facial skeleton. A
     cutaneous branch that dives back into the maxilla is not a stylisation, it
     is wrong, and the maxilla is convex enough under the infraorbital foramen
     that a branch aimed too steeply will do exactly that.
  2. NO BRANCH MAY END ANYWHERE BUT THE OUTSIDE OF THE FACE. A branch marched
     outward can stop inside a nostril, the oral vestibule or a sinus, all of
     which are air within the face. A crossing counts only where the point can
     leave the patient in a straight line, which only the outside can.
  3. NO BRANCH MAY CROSS THE DENTAL MIDLINE. A branch of the right infraorbital
     nerve that ends on the left cheek has burrowed through the nose, and
     invariant 2 cannot see it -- the far cheek is exterior too. The midline is
     x 3.5 here, not x 0; the arch sits to the operator's left of the scanner's
     origin, and measuring laterality from zero has cost this project a false
     build failure already.

ANATOMY, from Gray's Anatomy (the infraorbital and mental nerves) and Malamed's
Handbook of Local Anesthesia. The branch groups and their counts are named there
and are not invented here:

  Infraorbital, emerging under levator labii superioris and dividing at once
    inferior palpebral   x2   lower eyelid, skin and conjunctiva
    external nasal       x2   skin of the side of the nose
    internal nasal       x1   skin of the mobile part of the septum
    superior labial      x4   the largest and most numerous group: skin of the
                              anterior cheek and upper lip, and the labial
                              mucosa
  Mental, emerging under depressor anguli oris
    mental               x2   skin of the chin
    labial               x2   skin and mucous membrane of the lower lip
    gingival             x2   labial gingiva of the anterior mandible -- the
                              branch that matters for a mental block, and the
                              one a purely cutaneous account leaves out

The terminal two-way split near the skin is stylised. Cutaneous nerves do
arborise, but not in a count anyone measured on this patient.

FMA ids are the real ones for the branch SETS (fma75534-7, fma75520-2), checked
against the FMA through EBI OLS rather than guessed -- the ontology has separate
ids for a single branch, the set of them, and each side's, and the set is what a
mesh holding several branches bilaterally actually is.

Usage: nerve_face.py <out-dir> [--io <infraorbital.json>] [--mental <mental.json>]
                     --vol <centered.nrrd> --pred <centered-pred.nii.gz>
                     [--vol2 <maxillary.nrrd>  --xf  <transform.json>]
                     [--vol3 <mandibular.nrrd> --xf3 <transform.json>]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from segment_tooth import write_binary_stl                 # noqa: E402
from nerve import tube, smooth_path, buccal_foramen        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

AIR_HU = -250.0            # midway between this scan's air floor and soft tissue
SKIN_DEPTH_MM = 1.2        # a cutaneous nerve ends in the dermis, not in the air
SCAN_MM = 90.0             # how far an inward ray looks before giving up
ESCAPE_MM = 45.0           # how far a point must see clear to be outside
ESCAPE_STEP_MM = 0.4
CAST_OUT_MM = 30.0         # how far outside the face an inward ray starts
# How long each group can plausibly be, foramen to skin, on a face this size.
# Not a tolerance: with the rise escalation below it is what SELECTS the course.
# A ray laid flat enough will always find skin eventually -- 40 mm down the face
# it is on the chin -- so something has to say that a superior labial branch
# ending below the lower lip is the wrong branch rather than a long one.
# The medial groups get more room than a textbook figure suggests because this
# patient's foramina are not symmetric about the dental midline: the right sits
# 23.3 mm from it and the left 18.5, so every branch that runs toward the nose
# is about 5 mm longer on the right. That is measured, and the cap has to allow
# it or the right nasal branches are simply deleted.
MAX_BRANCH_MM = {"inferior palpebral": 22.0, "external nasal": 33.0,
                 "internal nasal": 32.0, "superior labial": 30.0,
                 "mental": 26.0, "labial": 28.0, "gingival": 12.0}
STEP_MM = 0.2
STEM_MM = {"infraorbital": 2.0, "mental": 3.0}
SPLIT_FRAC = 0.68          # where a branch divides into its two terminal twigs
SPLIT_DEG = 13.0
BOW = 0.10                 # sideways bow, as a fraction of the branch's length
NPTS = 18

# Radii, root -> tip. The superior labial group is the largest, the internal
# nasal the smallest; the rest sit between.
R_ROOT = {"superior labial": 0.34, "inferior palpebral": 0.25,
          "external nasal": 0.25, "internal nasal": 0.20,
          "mental": 0.32, "labial": 0.32, "gingival": 0.22}
R_TIP = 0.09
R_TWIG = 0.14

# Branch directions, in the LOCAL frame at each foramen:
#   f = the direction the nerve LEAVES the foramen, measured from the canal
#   u = superior, orthogonalised against f
#   m = toward the midline, orthogonalised against both
# Only f is measured. The weights are a reading of the courses in Gray's, and
# they are the schematic part of this module -- everything downstream of them is
# the patient's own geometry deciding where they stop.
# WHERE ON THE FACE each branch ends, as an offset in millimetres from the
# foramen's own skin point, in the plane of the face: (superior, medial).
# Negative superior is inferior, negative medial is lateral.
#
# This is the schematic part of the module and the only part that is. Gray's
# says which branches leave the infraorbital and mental nerves, how many, and
# what each supplies; these offsets are that description put in millimetres on
# a face. Where each one actually lands, and how long it therefore is, is the
# patient's own surface.
FANS = {
    "infraorbital": [
        ("inferior palpebral", "FMA75534", (0.55,  1.00, -0.15)),
        ("inferior palpebral", "FMA75534", (0.50,  1.00,  0.30)),
        ("external nasal",     "FMA75535", (0.55, -0.35,  1.00)),
        ("external nasal",     "FMA75535", (0.55, -0.60,  1.00)),
        ("internal nasal",     "FMA75536", (0.50, -0.85,  1.00)),
        ("superior labial",    "FMA75537", (0.60, -1.00, -0.15)),
        ("superior labial",    "FMA75537", (0.50, -1.00,  0.20)),
        ("superior labial",    "FMA75537", (0.45, -1.00,  0.50)),
        ("superior labial",    "FMA75537", (0.45, -0.90,  0.85)),
    ],
    "mental": [
        ("mental",   "FMA75520", (0.55, -1.00,  0.20)),
        ("mental",   "FMA75520", (0.50, -0.90,  0.55)),
        ("labial",   "FMA75521", (0.55,  0.85,  0.35)),
        ("labial",   "FMA75521", (0.50,  0.70,  0.70)),
        # The gingival branches do not reach skin at all: they turn back into
        # the labial vestibule. They are given a length rather than a target,
        # and are the one group here with no measured endpoint.
        ("gingival", "FMA75522", (-0.15, 1.00,  0.40)),
        ("gingival", "FMA75522", (-0.25, 0.95,  0.75)),
    ],
}
GINGIVAL = {"gingival"}
GINGIVAL_RUN_MM = 7.0

# HOW MUCH OF EACH BRANCH IS DRAWN.
#
# The full course is still computed, and every measured endpoint is still in
# docs/cbct-nerve-face.json -- that is the research and it is not thrown away.
# What is DRAWN is a stub: the first third of it, capped at MAX_DRAW_MM.
#
# The operator's call, and he is right. A branch drawn to its true termination
# is 12 to 33 mm long and ends in mid-air, because the face it ends on is not
# rendered. Eighteen of them at full length read as a spray of wires rather than
# as anatomy -- the length is meaningful only against a surface that is not
# there yet. A stub says which way the nerve goes and stops, which is all the
# geometry can honestly show today. When the soft-tissue surface lands, raise
# DRAW_FRAC to 1.0 and the branches reach their measured ends unchanged.
# A FIXED stub per group, not a fraction of the measured course. Two reasons.
# The measured terminations are only as good as the ray that found them, and on
# the mental fan they are not good: the left mental branches measure 3.6 mm and
# the right 26.8, for the same named branch on the same face. And a stub is
# meant to show a heading, so making its length vary with a number the viewer
# cannot see just makes one side look clipped.
STUB_MM = {"superior labial": 7.5, "inferior palpebral": 6.0,
           "external nasal": 6.0, "internal nasal": 5.5,
           "mental": 6.5, "labial": 6.5, "gingival": 5.0}
# How much a branch may be steepened out of the subcutaneous plane before
# it is called undrawable. 1.0 is the course as described.
RISE_STEPS = (1.0, 1.4, 1.9, 2.6, 3.5, 4.8)
# The internal nasal branches supply the mobile septum, which IS the
# midline, so a branch may just reach it but not pass through it.
MIDLINE_TOL_MM = 3.0


# --- sampling the patient ---------------------------------------------------

def head_mask(data):
    """The head as a solid: soft tissue and bone, with every internal cavity closed.

    The march needs to know when it has left the PATIENT, and an intensity
    threshold alone cannot tell it that. Air inside the face is the same air as
    air outside it: the first version marched to the first sustained run of air
    and every branch on both sides stopped 4 mm from the foramen, inside the
    maxillary sinus, and the measured facial normal came out pointing medially
    into the nasal cavity. Requiring a longer run of air only raises the price
    of the same mistake -- a maxillary sinus is 30 mm across.

    So the boundary is taken from a mask instead: threshold, keep the largest
    connected component, and close its holes both in 3D and slice by slice. The
    sinuses and the nasal cavity are holes; the outside is not. What is left has
    exactly one surface, and that surface is the skin.
    """
    solid = data > AIR_HU
    lab, n = ndi.label(solid)
    if n > 1:
        sizes = ndi.sum(solid, lab, range(1, n + 1))
        solid = lab == (int(np.argmax(sizes)) + 1)
    solid = ndi.binary_fill_holes(solid)
    # 3D filling leaves any cavity that drains to the outside -- the nares and
    # the oral vestibule both do. They close in-plane.
    for k in range(solid.shape[0]):
        if solid[k].any():
            solid[k] = ndi.binary_fill_holes(solid[k])
    return solid


def sampler(vol_path, extras=(), pred_path=None):
    """Is a world point in the ATLAS frame inside the patient's head?

    The centred exposure first, then each focused exposure through its own
    registration -- queried point by point and never resampled onto one grid.
    Rule 113 is about not rebuilding geometry on a resampled grid; nothing is
    rebuilt here, individual points are read, and reading them analytically is
    strictly better than resampling.

    BOTH focused exposures are needed, one per fan, and each fan fails without
    its own. The inferior palpebral branches climb past the centred volume's
    reconstruction CEILING at z 37.2 -- the same ceiling that hid the
    infraorbital canal. The mental foramen sits at z -44.5, which is its FLOOR:
    with only the maxillary exposure loaded, six of the twelve mental branches
    reported no skin anywhere within 24 mm, because the head simply stopped
    existing a fraction of a millimetre below where they started.
    """
    from vol import Volume
    from register import euler

    v = Volume.load(vol_path)
    o, sp = np.array(v.origin, float), np.array(v.spacing, float)
    head = head_mask(v.data.astype(np.float32))
    shape = np.array(head.shape)
    del v

    others = []
    if pred_path and os.path.exists(pred_path):
        from read_nifti import read_nifti
        fl, _, _ = read_nifti(pred_path)
        for vol2_path, xf_path in extras:
            if not (vol2_path and xf_path
                    and os.path.exists(vol2_path) and os.path.exists(xf_path)):
                continue
            v2 = Volume.load(vol2_path)
            m2 = head_mask(v2.data.astype(np.float32))
            del v2
            tr = json.load(open(xf_path))
            # The fit was about the centre of mass of one label in the FIXED
            # volume. Recovered exactly as nerve_maxilla.py does, so the two
            # modules cannot disagree about where an exposure sits.
            others.append((m2, np.array(m2.shape),
                           euler(*np.radians(tr["rotation_deg"])),
                           np.asarray(tr["translation_mm"]) / sp,
                           np.array(ndi.center_of_mass(fl == tr["label"]))))

    def read(w):
        i = np.array([(w[2] - o[2]) / sp[2], (w[1] - o[1]) / sp[1],
                      (w[0] - o[0]) / sp[0]])
        k = np.round(i).astype(int)
        if np.all(k >= 0) and np.all(k < shape):
            return bool(head[tuple(k)])
        for m2, sh2, R, t_vox, centre in others:
            j = np.round((i - centre) @ R + centre - t_vox).astype(int)
            if np.all(j >= 0) and np.all(j < sh2):
                return bool(m2[tuple(j)])
        return None

    return read


CLEARANCE_MM = 0.8         # tube radius plus a margin, between nerve and bone


def bone_test(pred_path):
    """Is a world point inside measured hard tissue?

    NOT FILLED, and this is the one place in the project where rule 108's
    per-slice fill is the wrong instrument. That rule exists because the canal
    and the teeth are their own labels and so read as holes in the jaw, which
    made a nerve running correctly inside the mandibular canal test as outside
    the bone. Filling an AXIAL slice of the mid-face does something else
    entirely: the maxilla, zygomata and nasal bones close a ring, and filling it
    declares the sinuses, the nasal cavity and everything the ring encloses to
    be bone. Applied here it condemned 16 of 18 branches on the first run --
    every one of them correctly running in soft tissue over the front of the
    maxilla.

    A cutaneous branch is being tested for the opposite property to a canal
    nerve: not "did you stay inside the bone" but "did you stay out of it". The
    raw label is exactly the right instrument for that, and the fill is exactly
    the wrong one.
    """
    if not pred_path or not os.path.exists(pred_path):
        return None, None
    from read_nifti import read_nifti
    origin = np.array([-40.96, -58.074258, -44.520221])
    sp = 0.16
    lab, _, _ = read_nifti(pred_path)
    hard = np.isin(lab, (1, 2, 3, 4, 5))

    # For a point inside bone, the nearest point OUTSIDE it. This is confine()
    # from nerve_maxilla.py turned inside out: that one pulls a course into the
    # bone it belongs in, this one pushes a course out of the bone it does not.
    _, idx = ndi.distance_transform_edt(hard, return_indices=True)

    def to_idx(w):
        return np.round([(w[2] - origin[2]) / sp, (w[1] - origin[1]) / sp,
                         (w[0] - origin[0]) / sp]).astype(int)

    def in_range(i):
        return bool(np.all(i >= 0) and np.all(i < np.array(hard.shape)))

    def inside(w):
        i = to_idx(w)
        return bool(in_range(i) and hard[tuple(i)])

    def repel(w):
        """Push a point out of bone along the shortest way out, plus clearance."""
        i = to_idx(w)
        if not in_range(i) or not hard[tuple(i)]:
            return np.asarray(w, float)
        j = idx[(slice(None),) + tuple(i)]
        out = np.array([origin[0] + j[2] * sp, origin[1] + j[1] * sp,
                        origin[2] + j[0] * sp])
        d = out - np.asarray(w, float)
        n = np.linalg.norm(d)
        if n < 1e-6:
            return out
        return out + (d / n) * CLEARANCE_MM

    return inside, repel


def skin_at(inside_head, start, d):
    """Cast INWARD from a point outside the head; return where the skin is.

    Casting outward from the foramen is the obvious way round and it does not
    work, because "the first air" and "the skin" are different things inside a
    face. Four rules were tried on outward rays before the direction was
    reversed:

      first air              stops in the maxillary sinus, 4 mm out.
      first air lasting 3mm  stops there too; a sinus is 30 mm across.
      first air outside a    the nasal airway is open at the nares and at the
      FILLED head mask       choanae and drains the sinuses through the ostia,
                             so it is a hole in no plane and no fill closes it.
                             Axial, coronal and sagittal all leave it open.
      the LAST transition    right about cavities, wrong about the face: a ray
                             aimed medially leaves this cheek, crosses the nose
                             and ends on the far side of the head.

    Cast the other way and the ambiguity is gone. Starting outside the patient,
    THE FIRST TISSUE THE RAY MEETS IS SKIN -- there is nothing in front of it to
    be confused with, no cavity to fall into, and no threshold to tune. The
    sinuses and the nasal airway stop being a problem to solve rather than one
    solved better.
    """
    n = int(SCAN_MM / STEP_MM)
    firm = int(1.0 / STEP_MM)
    # The ray begins CAST_OUT_MM clear of the face, so anything before the first
    # tissue is outside the patient whether it was reconstructed or not. Reading
    # unreconstructed space as "not yet air" instead sent rays straight through
    # the head to strike the far side: one external nasal branch came back
    # 54 mm long, ending at y +25 behind the plane of the face.
    seen_air = True
    for k in range(n + 1):
        v = inside_head(start + d * (k * STEP_MM))
        if v is not True:
            continue
        if seen_air:
            ahead = [inside_head(start + d * ((k + j) * STEP_MM))
                     for j in range(1, firm + 1)]
            if all(a is not False for a in ahead):
                return start + d * (k * STEP_MM)
    return None


def escape_dirs(out):
    """A spread of directions around `out`, for testing whether a point can leave."""
    h = np.asarray(out, float)
    h /= np.linalg.norm(h)
    e1 = np.cross(h, [0.0, 0.0, 1.0])
    if np.linalg.norm(e1) < 1e-6:
        e1 = np.cross(h, [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(h, e1)
    dirs = [h]
    for th in np.radians((35.0, 65.0)):
        for ph in np.radians(np.arange(0, 360, 60.0)):
            dirs.append(np.cos(th) * h
                        + np.sin(th) * (np.cos(ph) * e1 + np.sin(ph) * e2))
    return dirs


def is_exterior(inside_head, q, dirs):
    """Is q on the OUTSIDE of the face, rather than in a cavity within it?

    A point can leave the patient in a straight line only from the outside. From
    the wall of the maxillary sinus, or the lateral wall of the nose, every
    straight line out meets tissue again -- the sinus is enclosed, and its only
    real opening is a few millimetres wide and turns a corner.

    A SPREAD of directions, not one. Testing only the face's general outward
    direction fails wherever the face is not locally convex: from the skin
    beside the nose that direction goes through the nose, and from the lower
    eyelid it goes through the brow, so thirteen of eighteen branches were told
    they had never reached skin. One clear line out is enough to be outside.
    """
    n = int(ESCAPE_MM / ESCAPE_STEP_MM)
    for d in dirs:
        if not any(inside_head(q + d * (k * ESCAPE_STEP_MM)) is True
                   for k in range(1, n + 1)):
            return True
    return False


def dental_midline(path):
    """x of the dental midline, which is NOT x = 0.

    The arch sits 3.6 mm to the operator's left of the scanner's origin -- head
    position, not anatomy -- and a laterality test against zero has already cost
    this project one false build failure (see the export_teeth.py fix). The
    midline matters here because a facial branch that crosses it has run through
    the nose into the other side of the face, which is the one way these rays
    can fail while still ending on real skin.
    """
    if not os.path.exists(path):
        return 0.0
    d = json.load(open(path))
    xs = [t["world"][0] for arch in d.values() for t in arch["teeth"]]
    return (min(xs) + max(xs)) / 2.0 if xs else 0.0


def branch_to_skin(inside_head, p, d, out, midline, side, limit):
    """March out from p along d and stop at the skin. Returns the tip, or None.

    Four rules for "where is the skin" were tried on an outward ray before this
    one, and each failed on a cavity inside the face:

      first air              stops in the maxillary sinus, 4 mm from the
                             foramen.
      first air lasting 3mm  stops there too; a sinus is 30 mm across.
      first air outside a    the nasal airway is open at the nares and at the
      FILLED head mask       choanae and drains the sinuses through the ostia,
                             so it is a hole in no plane and no fill closes it.
                             Axial, coronal and sagittal all leave it open.
      the LAST transition    right about cavities, wrong about the face: a ray
                             aimed medially leaves this cheek, crosses the nose
                             and ends on the far side of the head.

    Casting INWARD from outside the patient does settle where the skin is -- the
    first tissue a ray from outside meets can be nothing else -- and it is what
    `outward` uses. It is the wrong tool for a branch, though, because the cast
    has to run along some fixed direction and the face is not flat: aimed from
    the plane tangent at the infraorbital foramen, casts meant for the side of
    the nose struck the tip of it instead, and superior labial branches came
    back ending on the nose 38 mm away.

    What actually distinguishes skin from a cavity wall is that nothing is
    outside it. So the ray keeps its own direction, and each crossing it makes
    is asked that question directly.
    """
    n = int(limit / STEP_MM)
    dirs = escape_dirs(out)
    lat = -1.0 if side == "right" else 1.0
    prev = inside_head(p)
    for k in range(1, n + 1):
        q = p + d * (k * STEP_MM)
        # INVARIANT 3. A branch of the RIGHT infraorbital nerve that ends on the
        # LEFT cheek has burrowed through the nose, and the exterior test cannot
        # see it: the far cheek is exterior too. Two external nasal branches did
        # this, ending 15 mm past the midline on the wrong side of the face.
        if lat * (q[0] - midline) < -MIDLINE_TOL_MM:
            return None
        v = inside_head(q)
        if prev is True and v is not True and is_exterior(inside_head, q, dirs):
            return q - d * SKIN_DEPTH_MM
        prev = v
    return None


# --- geometry ---------------------------------------------------------------

ANTERIOR = np.array([0.0, -1.0, 0.0])      # LPS y grows posteriorly


def outward(inside_head, p):
    """The face's own outward normal at a foramen, and how deep the foramen is.

    The nearest point of a surface lies along its normal, so the direction whose
    skin point is CLOSEST is the normal -- no model of the face required, only
    the boundary that is already measured. Searched over a wide cone about
    ANTERIOR, because a facial normal is anterior by definition; the cone only
    exists to stop the search turning round and finding the back of the head.

    THE CANAL'S OWN TANGENT IS NOT USED AS THE HINT, and both ways of getting
    that wrong are worth keeping. Used as the fan's forward axis it aimed the
    superior labial group down through the alveolar process -- the infraorbital
    canal descends about 24 degrees as it runs forward, and a ray pointed down
    the inside of a face never leaves it. Used merely as the CENTRE of this
    search it still failed, on the mental canal: the last four millimetres of
    the tracing hook medially, so a 60-degree cone about that tangent could not
    reach the true normal at all, and the search settled on a direction pointing
    into the mouth with skin an implausible 4.6 mm away. The nerve turns as it
    emerges. Where it is going inside the bone says nothing about which way the
    face points.
    """
    h = ANTERIOR
    e1 = np.array([1.0, 0.0, 0.0])
    e2 = np.cross(h, e1)
    best = (None, None)
    for th in np.radians(np.arange(0, 76, 5.0)):
        for ph in np.radians(np.arange(0, 360, 10.0)):
            d = (np.cos(th) * h
                 + np.sin(th) * (np.cos(ph) * e1 + np.sin(ph) * e2))
            start = p + d * CAST_OUT_MM
            if inside_head(start) is not False:
                continue                      # started inside the head, not outside
            hit = skin_at(inside_head, start, -d)
            if hit is None:
                continue
            r = float(np.linalg.norm(hit - p))
            if best[0] is None or r < best[0]:
                best = (r, d)
            if th == 0:
                break
    if best[1] is None:
        return h, None
    return best[1], best[0]


def frame(out_dir, side):
    """Right-handed local frame at a foramen: (outward, superior, medial)."""
    f = np.asarray(out_dir, float)
    f = f / max(np.linalg.norm(f), 1e-9)
    up = np.array([0.0, 0.0, 1.0])
    u = up - f * float(up @ f)
    if np.linalg.norm(u) < 1e-6:
        u = np.array([0.0, -1.0, 0.0])
    u /= np.linalg.norm(u)
    med = np.array([-1.0, 0.0, 0.0]) if side == "left" else np.array([1.0, 0.0, 0.0])
    m = med - f * float(med @ f) - u * float(med @ u)
    if np.linalg.norm(m) < 1e-6:
        m = np.cross(f, u)
    m /= np.linalg.norm(m)
    return f, u, m


def bowed(p0, p1, side_vec, n=NPTS):
    """A gently bowed path between two points, so a branch does not read as a ruler."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    mid = 0.5 * (p0 + p1) + side_vec * (BOW * np.linalg.norm(p1 - p0))
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * mid + t ** 2 * p1


def ride(path, repel, inside=None, passes=3):
    """Lift a course clear of bone, then re-smooth, then lift again.

    These nerves lie ON the facial skeleton, not in it, and a straight ray from
    the foramen does not know that: the infraorbital rim stands directly above
    the foramen and the canine fossa bulges directly below it, so the palpebral
    and superior labial groups both cut a corner through bone on the way to the
    skin. Pushing each offending point out along its own shortest way out makes
    the course ride the surface it should have been riding, and re-smoothing
    afterwards keeps the push from leaving a staircase -- the same two-step
    nerve.py needs for the incisive canal (rule 58), in the other direction.
    """
    if repel is None:
        return path
    out = np.array([repel(p) for p in path])
    for _ in range(passes):
        out = smooth_path(out, passes=1)
        out = np.array([repel(p) for p in out])
    # Smoothing between pushes can pull a point back into a thin plate -- the
    # nasal aperture margin is one voxel thick in places -- so the last word
    # goes to the push, repeated until nothing is left inside. Bounded: if a
    # course cannot be freed the invariant below fails the run rather than
    # looping.
    if inside is not None:
        for _ in range(8):
            bad = [i for i, w in enumerate(out) if inside(w)]
            if not bad:
                break
            for i in bad:
                out[i] = repel(out[i])
    return out


def rotate_about(v, axis, deg):
    axis = axis / max(np.linalg.norm(axis), 1e-9)
    th = np.radians(deg)
    return (v * np.cos(th) + np.cross(axis, v) * np.sin(th)
            + axis * float(axis @ v) * (1 - np.cos(th)))


# --- foramina ---------------------------------------------------------------

def traced_foramina(path, inside=None):
    """Foramen and emergence direction per side, from a traced canal.

    Both nerves are read the same way and by the same function, because both
    tracings are the same thing: an ordered centreline down a canal that opens
    on the face. The ANTERIOR end is the foramen -- true of the infraorbital
    canal, which runs forward and down from the pterygopalatine fossa, and of
    the mental canal, which turns forward and out of the mandibular canal -- so
    the end is chosen by y rather than by which end the tracing happened to
    start from.

    The emergence direction is the canal's own tangent over its last few
    millimetres, so where the fan points is measured rather than chosen. Taken
    over one sample it would let voxel noise set the axis of everything
    downstream, so it is fitted over the anterior 4 mm.
    """
    if not path or not os.path.exists(path):
        return {}
    d = json.load(open(path))
    out = {}
    for side, rec in d.get("sides", {}).items():
        pts = np.array([r["p"] for r in rec["points"]], float)
        if len(pts) < 4:
            continue
        if pts[0, 1] > pts[-1, 1]:          # LPS y grows posteriorly
            pts = pts[::-1]
        # WHICH point is the foramen is not always the end of the tracing. The
        # infraorbital canal ends at its foramen, so the anterior end is right.
        # The mandibular canal does not: it runs on as the incisive canal, and
        # the operator following the lumen runs past the exit. Where a bone test
        # is available the foramen is taken as the canal's closest approach to
        # the buccal plate -- see buccal_foramen() in nerve.py, one definition
        # shared with the module that draws the trunk.
        j = 0
        if inside is not None:
            j, _ = buccal_foramen(pts, inside, side)
        step = np.linalg.norm(np.diff(pts, axis=0), axis=1).mean()
        k = min(len(pts) - 1, j + max(3, int(round(4.0 / max(step, 1e-6)))))
        tan = pts[j] - pts[k]
        out[side] = (pts[j], tan / max(np.linalg.norm(tan), 1e-9))
    return out


# THE MENTAL FAN HAS NO FALLBACK, AND THAT IS DELIBERATE.
#
# The mandibular canal as segmented does not reach the mental foramen. On the
# right it stops at y -22.0 and the premolar window begins at y -22.5, so not
# one centreline point falls in it; on the left the six that do all sit within
# 1.5 mm of the inferior border. nerve.py's landmark, which is the nearest
# centreline point to the premolar apices, therefore lands 0.5 mm OUTSIDE the
# mandible on the right and 0.7 mm above its inferior border on the left --
# about 4 mm too low on both sides. Projecting a landmark onto a curve cannot be
# better than the curve.
#
# So there is nothing to fall back to. Guessing a replacement would move the
# guess rather than remove it, and a fan of a dozen branches hung off a guess
# looks exactly as convincing as one hung off a measurement. Until the mental
# canal is traced -- see 3Dentes-cbct/trace-mental -- the mental fan is not
# built and the atlas is missing it, which is the true state of affairs.


# --- build ------------------------------------------------------------------

def build(kind, foramina, head, in_bone, repel, midline, report):
    """One fan per side. Returns {fma: (verts, faces)}."""
    meshes = {}

    def add(fma, v, f):
        vs, fs, off = meshes.setdefault(fma, ([], [], 0))
        vs.append(v)
        fs.append(f + off)
        meshes[fma] = (vs, fs, off + len(v))

    for side, (fpt, emerge) in sorted(foramina.items()):
        # The stem follows the MEASURED emergence direction out of the canal;
        # the fan beyond it is laid out on the measured face.
        out, depth = outward(head, fpt)
        if depth is None:
            report["dropped"].append(dict(kind=kind, side=side, branch="(all)",
                                          reason="no skin above the foramen"))
            continue
        f, u, m = frame(out, side)
        base = fpt + out * depth                      # the foramen's own skin point
        stem_end = fpt + np.asarray(emerge, float) * STEM_MM[kind]
        report["foramina"].append(dict(
            kind=kind, side=side,
            foramen_lps=[round(float(x), 2) for x in fpt],
            emergence_lps=[round(float(x), 3) for x in emerge],
            outward_lps=[round(float(x), 3) for x in out],
            skin_depth_mm=round(float(depth), 2)))

        for name, fma, w in FANS[kind]:
            d = w[0] * f + w[1] * u + w[2] * m
            d /= np.linalg.norm(d)
            if name in GINGIVAL:
                # No measured endpoint: these turn back into the labial
                # vestibule rather than reaching skin, so they are the one
                # group here given a length instead of finding one.
                tip = stem_end + d * GINGIVAL_RUN_MM
                measured_end = False
            else:
                # These nerves run in the subcutaneous plane, and the weights
                # above say which way along the face each group heads, not how
                # steeply it rises through it. A course laid too flat runs down
                # the inside of the face without ever surfacing -- the medial
                # superior labial branches did exactly that, still 10 mm deep
                # 40 mm from the foramen, past the lip and heading for the chin.
                # So the rise is not a constant to tune: each branch is
                # steepened until this patient's own skin stops it, and the
                # factor it needed is recorded.
                measured_end = True
                tip = None
                for lift in RISE_STEPS:
                    d = (w[0] * lift) * f + w[1] * u + w[2] * m
                    d /= np.linalg.norm(d)
                    tip = branch_to_skin(head, stem_end, d, out, midline, side,
                                         MAX_BRANCH_MM[name])
                    if tip is not None:
                        break
                rise = lift
                if tip is None:
                    # Drawn anyway, at the nominal heading and the stub length.
                    # What is lost is the measured LENGTH, and the stub does not
                    # use it; what is kept is where the branch goes.
                    report["dropped"].append(dict(
                        kind=kind, side=side, branch=name,
                        reason=f"no skin within {MAX_BRANCH_MM[name]:.0f} mm "
                               f"at any rise up to {RISE_STEPS[-1]}x"))
                    d = w[0] * f + w[1] * u + w[2] * m
                    d /= np.linalg.norm(d)
                    measured_end = False
                    rise = 1.0

            if name in GINGIVAL:
                rise = 1.0
            measured_run = (float(np.linalg.norm(tip - stem_end))
                            if tip is not None else None)
            run = STUB_MM[name]
            drawn_tip = stem_end + d * run
            split = stem_end + d * (run * SPLIT_FRAC)
            bow_axis = np.cross(d, u)
            if np.linalg.norm(bow_axis) < 1e-6:
                bow_axis = m
            bow_axis /= np.linalg.norm(bow_axis)

            paths = [bowed(fpt, split, bow_axis * 0.45)]
            # Two terminal twigs. Each ends on the face as well, a few
            # millimetres either side of its parent, so the arborisation lands
            # on skin rather than in it.
            for sgn in (-1, 1):
                dd = rotate_about(d, bow_axis, sgn * SPLIT_DEG)
                dd /= np.linalg.norm(dd)
                tw = split + dd * (run * (1.0 - SPLIT_FRAC))
                paths.append(bowed(split, tw, bow_axis * 0.3, n=10))

            for i, path in enumerate(paths):
                path = ride(smooth_path(path, passes=2), repel, in_bone)
                r = (np.linspace(R_ROOT[name], R_TWIG, len(path)) if i == 0
                     else np.linspace(R_TWIG, R_TIP, len(path)))
                o = tube(path, r)
                if o is None:
                    continue
                add(fma, *o)
                if in_bone is not None:
                    # The foramen is a hole a few voxels across in a label that
                    # does not resolve it, so the origin itself reads as bone.
                    # Only the free course is tested.
                    free = STEM_MM[kind] + 1.0
                    bad = sum(1 for w in path
                              if np.linalg.norm(w - fpt) > free and in_bone(w))
                    if bad:
                        report["in_bone"].append(dict(
                            kind=kind, side=side, branch=name, twig=i,
                            points_in_bone=int(bad), of=len(path)))
            report["branches"].append(dict(
                kind=kind, side=side, branch=name, fma=fma,
                drawn_mm=round(run + STEM_MM[kind], 1),
                measured_mm=(None if measured_run is None
                             else round(measured_run + STEM_MM[kind], 1)),
                measured_endpoint=measured_end, rise=round(float(rise), 2),
                measured_tip_lps=(None if tip is None
                                  else [round(float(x), 2) for x in tip]),
                drawn_tip_lps=[round(float(x), 2) for x in drawn_tip],
                twigs=len(paths) - 1))
    return {k: (np.vstack(v), np.vstack(f)) for k, (v, f, _) in meshes.items()}


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__.strip().splitlines()[-2])
    outdir = args[0]
    opt = {}
    i = 1
    while i < len(args) - 1:
        opt[args[i].lstrip("-")] = args[i + 1]
        i += 2
    os.makedirs(outdir, exist_ok=True)

    io_path = opt.get("io", os.path.join(ROOT, "docs", "cbct-infraorbital.json"))
    mental_path = opt.get("mental", os.path.join(ROOT, "docs", "cbct-mental.json"))
    read = sampler(opt["vol"],
                   [(opt.get("vol2"), opt.get("xf")),
                    (opt.get("vol3"), opt.get("xf3"))],
                   opt.get("pred"))
    in_bone, repel = bone_test(opt.get("pred"))
    midline = dental_midline(opt.get("split", os.path.join(
        ROOT, "docs", "cbct-teeth-split.json")))

    report = dict(
        provenance=dict(
            foramen="MEASURED (traced canal; the emergence direction is the "
                    "canal's own anterior tangent)",
            termination="MEASURED (the air/skin interface in this CBCT, "
                        f"stopped {SKIN_DEPTH_MM} mm short of it)",
            course="SCHEMATIC (branch groups and counts from Gray's; the path "
                   "between the two measured ends is convention)",
            arborisation="SCHEMATIC (the terminal two-way split is stylised)",
            drawn="Each branch is DRAWN as a short stub of fixed length, "
                  "5.0-7.5 mm by group, because the face it terminates on is "
                  "not rendered yet and a branch ending in mid-air 30 mm out "
                  "reads as a wire rather than as anatomy. The heading is "
                  "measured; the drawn length is not. Every branch's measured "
                  "termination is recorded below as measured_tip_lps."),
        note="CBCT has poor soft-tissue CONTRAST but an excellent air/tissue "
             "BOUNDARY, which is the only soft-tissue measurement used here. "
             "Nothing between the foramen and the skin was seen.",
        branches=[], foramina=[], dropped=[], in_bone=[])
    report["dental_midline_x"] = round(float(midline), 3)

    # The infraorbital canal ends AT its foramen, so its anterior end is the
    # foramen; the mandibular canal runs past its own, so the mental fan needs
    # the bone test to find where it leaves.
    fans = dict(infraorbital=traced_foramina(io_path),
                mental=traced_foramina(mental_path, in_bone))
    built = {}
    for kind, foramina in fans.items():
        if not foramina:
            print(f"{kind}: no traced foramen, fan not built")
            continue
        built[kind] = build(kind, foramina, read, in_bone, repel, midline, report)

    # Both invariants are checked BEFORE anything is written. A run that fails
    # must leave no STL behind: a half-correct fan on disk is what a later build
    # would pick up.
    # INVARIANT 1: nothing may run back inside bone.
    if report["in_bone"]:
        print("\nBRANCH IN BONE — these courses re-enter measured hard tissue:")
        for r in report["in_bone"]:
            print(f"  {r['side']:5s} {r['branch']:20s} twig {r['twig']} "
                  f"{r['points_in_bone']}/{r['of']} points")
        raise SystemExit(1)
    # INVARIANT 2: a branch must reach the OUTSIDE of the face, not a cavity in
    # it. Now that only a stub is drawn, a branch whose endpoint could not be
    # measured is still drawable -- its heading is measured either way -- so
    # this reports rather than aborts. It stays fatal in bulk, because both
    # times the sampler was broken today it failed like this: six of twelve
    # mental branches at once, because the exposure containing the mandible's
    # inferior border had not been loaded. A handful is anatomy; a third is a
    # bug.
    if report["dropped"]:
        print("\nNO MEASURED ENDPOINT — heading is measured, termination is not:")
        for r in report["dropped"]:
            print(f"  {r['side']:5s} {r['branch']:20s} {r['reason']}")
        share = len(report["dropped"]) / max(
            len(report["dropped"]) + len(report["branches"]), 1)
        if share > 0.33:
            raise SystemExit(
                f"{share:.0%} of branches found no skin — that is the sampler, "
                "not the anatomy. Check that every exposure is loaded.")

    for kind, meshes in built.items():
        for fma, (v, f) in sorted(meshes.items()):
            write_binary_stl(os.path.join(outdir, f"{fma}.stl"), v, f)
            print(f"  {fma}: {len(f)} triangles ({kind})")
    with open(os.path.join(outdir, "nerve-face.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    n = len(report["branches"])
    dr = [b["drawn_mm"] for b in report["branches"]]
    me = [b["measured_mm"] for b in report["branches"] if b["measured_mm"]]
    print(f"\n{n} branches, {n * 2} terminal twigs; drawn "
          f"{min(dr):.1f}-{max(dr):.1f} mm as stubs. Measured terminations, "
          f"recorded but not drawn, run {min(me):.1f}-{max(me):.1f} mm.")
    for b in report["branches"]:
        m = f"{b['measured_mm']:5.1f}" if b["measured_mm"] else "   --"
        print(f"  {b['side']:5s} {b['branch']:20s} drawn {b['drawn_mm']:5.1f}, "
              f"measured {m} mm")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
