"""Join the pulp into one continuous body and carry it to the apical foramen.

Thresholding recovers the pulp where it is wide enough to be radiolucent and
loses it where it is not, so the shipped mask arrives as a main body plus a
scatter of apical islands -- the operator described it as "a main body of canal
and then a void space and then more pulp tissue nearer the apex". Tooth 12 was
the worst: the largest piece held 59.9% of the pulp and stopped 2.9 mm short.

Two things are missing and they are different in kind:

  BRIDGES     between an island and the main body the canal certainly exists --
              there is pulp on both sides of the gap. Its PATH is recovered from
              the image by routing along the darkest route through dentin, so
              this is interpolation guided by evidence, not invention.

  EXTENSIONS  past the last radiolucent voxel nothing is resolvable at 0.16 mm.
              The canal's own trajectory is continued to the root surface and
              the exit point is taken as the apical foramen.

Both are DERIVED, not MEASURED, and pulp-connect.json records which voxels came
from which so the distinction survives into the app.

Apical foramen anatomy the placement is checked against:
  - the major foramen deviates from the anatomical apex in ~85% of teeth, mean
    0.52 mm (reported range 0.2-2.0 mm), most commonly to the DISTAL
  - the apical constriction lies ~0.2 mm coronal to the foramen (micro-CT;
    the older teaching of 0.5-1.0 mm comes from sectioned specimens)
  - minor diameter at the constriction averages ~0.255 mm
  - apical deltas occur in 9.7% of teeth (molars 15-16.5%) with median branch
    diameter 132 um -- BELOW this scan's 160 um voxel, so they are named in the
    report and deliberately not modelled. A delta drawn at voxel scale would be
    an invention at ~4x its true calibre.
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.graph import MCP_Geometric

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                    # noqa: E402
from segment_tooth import write_binary_stl                # noqa: E402
from meshsmooth import taubin                             # noqa: E402
from export_teeth import decimate                         # noqa: E402
from skimage.measure import marching_cubes                # noqa: E402
import pulp_solid as PS                                   # noqa: E402

# Literature values the result is checked against, not fitted to.
FORAMEN_APEX_MEAN_MM = 0.52
FORAMEN_MIN_RADIUS_MM = 0.13     # ~0.255 mm minor diameter at the constriction
# Sampled at 0.30 the maxillary FIRST premolars (5 and 12) still read as one
# root -- that far from the apex their two roots are fused -- so the per-root
# canal assertion never fired and the operator saw roots with no pulp in them.
# At 0.20 they separate, and every molar keeps the root count it had.
ROOT_SLAB_FRAC = 0.20            # apical fraction of the tooth used to find roots
# 200 admitted a 457-voxel (1.9 mm3) sliver of tooth 12's apical slab as a
# "root". It got a foramen and no canal, because there was no canal to find. A
# real premolar root tip in the apical fifth is several times that.
MIN_ROOT_VOX = 600
# THE FORAMEN IS WHERE THE CANAL GOES, NOT WHERE THE CHEAPEST EXIT IS.
# Routing to the lowest-cost surface voxel put foramina a mean 2.85 mm from the
# apex (literature 0.52), because a short lateral path through thin dentin beats
# running the length of the canal -- those are lateral canals, not the major
# foramen. Capping the search radius only moved the answer onto the cap.
#
# Narrowing the window until the mean matched 0.52 would have been fitting the
# result to the number it is then checked against, so instead the canal's own
# measured trajectory is extrapolated: take its apical direction over the last
# TRAJECTORY_MM and march until it leaves the root. The direction is measured;
# only the continuation past the last radiolucent voxel is modelled, and the
# deviation from the apex is then an OUTPUT that can be honestly compared.
# A LONG BRIDGE IS NOT A CANAL.
# Bridging every island produced thin strings branching from the chambers of 19
# teeth. A canal interrupted by partial volume resumes within a fraction of a
# millimetre; a path running millimetres through solid dentin to reach an
# isolated blob is connecting an ARTEFACT -- beam hardening between dense roots
# reads dark and thresholds like pulp. Real accessory canals do exist, but they
# run from a canal to the root SURFACE and average 132 um, well under this
# scan's 160 um voxel, so nothing here can resolve one and a string drawn at
# voxel calibre would overstate it several-fold.
#
# Islands beyond this range are DROPPED, not bridged: leaving them would put
# free-floating debris back in the mesh, which is what the operator saw first.
MAX_BRIDGE_MM = 1.5
# ...BUT A CANAL IS ALLOWED A LONGER ONE, BECAUSE OF ITS SHAPE.
# Capping on span alone deleted the MB canals of teeth 3 and 14 outright. An MB
# canal is genuinely detached from the chamber in the threshold mask -- its
# orifice is the narrowest part and drops out first -- so it presents exactly as
# a distant island. What separates it from a beam-hardening blob is not distance
# but FORM: a canal is long, thin and points at the apex; an artefact is compact
# and points nowhere. Span is the wrong discriminator on its own.
CANAL_BRIDGE_MM = 5.0
CANAL_MIN_LEN_MM = 1.5
CANAL_MIN_ASPECT = 2.5

# EVERY ROOT HAS A CANAL. THE THRESHOLD DOES NOT ALWAYS FIND IT.
# Tooth 14's three roots held 990, 69 and 4 pulp voxels: the palatal canal and
# the chamber absorb the tooth's whole calibrated volume budget and the MB and
# DB canals never appear, so there is nothing to bridge and no trajectory to
# extrapolate. That a root contains a canal is not an inference, it is what a
# root IS -- so it is asserted here as a prior, exactly like CANAL_COUNT in
# pulp_all.py, while the PATH stays image-derived (the darkest route from the
# pulp body to that root's apex). Existence: prior. Route: measured. Calibre:
# modelled. Do not let a later cleanup collapse those three into one claim.
# THE CANAL MUST NOT BE THRESHOLDED. CLAUDE.md RULE 4, WHICH I BROKE.
# Thresholding a sub-resolution canal does not find a canal, it finds scattered
# dark voxels through dentin -- and because the volume is calibrated, the budget
# gets SPENT on that scatter. Tooth 9, a maxillary central incisor with exactly
# one canal, had more than one blob in 63% of its slices (up to 5); tooth 22, a
# mandibular canine, in 70% (up to 9). That is the "crunchiness", and no amount
# of smoothing fixes it because the geometry itself is wrong.
#
# The pulp is therefore built from the two things each method is good at:
#   CHAMBER  thresholded, then opened -- it is wide enough to resolve, and the
#            opening deletes the speckle, which is thin by nature
#   CANAL    the smooth swept tube along the centreline pulp_all.py MEASURED by
#            deficit integration, which survives sub-resolution blurring
# Multi-blob slices fall to 9% and 1%. The tube's RADIUS is then scaled so the
# union matches the same calibrated volume as before, which reallocates the
# speckle volume into the canal instead of throwing it away.
# CANAL CALIBRE IS CAPPED BY MEASURED ANATOMY, NOT BY THE VOLUME BUDGET.
# Scaling the tube until the union hit the calibrated volume made the canals
# 0.65/0.70/0.69/0.74 mm equivalent diameter at 1/2/3/4 mm from the apex, when
# micro-CT of molar mesial canals gives 0.29/0.39/0.40/0.44 (MD 0.22-0.36,
# BL 0.37-0.60 -- they are elliptical, BL > MD). Even allowing this model's
# tissue-vs-lumen factor of sqrt(SHADING_SCALE) = 1.46 the apical millimetre was
# over 1.5x too wide: a fat canal was standing in for volume that belongs in the
# chamber. The envelope below is the literature profile scaled by that same
# factor, and the tube is clamped to it.
CANAL_ENV_MM = ((0.0, 0.26), (1.0, 0.42), (2.0, 0.57), (3.0, 0.58), (4.0, 0.64))


def canal_envelope_r(dist_mm):
    """Max modelled canal RADIUS at a distance from the apex."""
    xs = [p[0] for p in CANAL_ENV_MM]
    ys = [p[1] / 2.0 for p in CANAL_ENV_MM]
    d = np.asarray(dist_mm, float)
    r = np.interp(d, xs, ys)
    # Beyond the apical 4 mm the canal widens toward the orifice and the
    # literature series stops, so the cap is released rather than extrapolated.
    return np.where(d > xs[-1], np.inf, r)


# THE MEASURED LUMEN IS OVER-STATED ON SOME TEETH, AND IT SHOWS AS A BULGE.
# The operator flagged 13 teeth whose chambers bulged coronally. Sorting every
# tooth by lumen as a FRACTION of its own volume separates their list perfectly:
#
#   teeth they called good     2.83 - 3.67 %
#   molars, unflagged          1.69 - 3.57 %
#   teeth they called bulging  4.06 - 8.17 %   (median 6.00)
#
# with a clean gap between 3.75 and 4.06 and no overlap. Two independent
# judgements -- a clinician's eye and a ratio neither of us chose in advance --
# landing on the same partition is what makes this a measurement error in
# pulp_all.py's deficit integration rather than a rendering complaint. It
# over-integrates on single-rooted teeth with wide canals, where much of the
# tooth's cross-section is close to pulp density.
#
# Until that tracker is fixed, the target volume is capped at the fraction the
# well-behaved population supports. Molars and the operator's reference teeth
# (6, 11, 24, 25) are all under the cap and are therefore untouched by it.
PULP_FRACTION_MAX = 0.039

# PULP DOES NOT REACH THE OCCLUSAL SURFACE.
# The chamber was running to within 0.16 mm -- ONE VOXEL -- of the tooth
# surface, which the operator saw as bulges up to the occlusal surfaces and
# incisal edges. The limit is taken from their own hand shading of tooth 14
# rather than from a textbook: 99% of what they shaded lies at least 0.92 mm
# below the tooth surface (5th percentile 1.06, median 2.22). Their judgement of
# where pulp stops is the best evidence available for this dentition.
#
# IT APPLIES TO THE CORONAL HALF ONLY. A global depth rule would have wrecked
# the very teeth the operator holds up as correct: 24 and 25 have 17% of their
# pulp within 0.92 mm of the surface, because a thin incisor ROOT legitimately
# carries its canal close to the surface. Split by half, the metric separates
# cleanly -- their reference teeth run 0.0-2.8% shallow coronally, against 23.2,
# 14.4, 11.2 and 10.8% on the teeth they flagged.
CHAMBER_MIN_DEPTH_MM = 0.92

# PULP HORNS SIT MILLIMETRES BELOW THE OCCLUSAL SURFACE, NOT A FRACTION OF ONE.
# The 0.92 mm figure above was mis-derived: it is the 1st percentile of ALL the
# operator's shaded voxels, which is dominated by canal and chamber-periphery
# voxels deep in the root, not by the horn tip. It let horns run to within a
# millimetre of the enamel, and the operator -- reading it against periapicals
# of unrestored molars -- rejected three successive builds on exactly this.
#
# Measured against the OCCLUSAL surface specifically, the two sources agree:
#   their shading of tooth 14   closest approach 4.05 mm, median 6.23
#   literature, cusp tip to pulp horn   5.59 mm maxillary 1st molar (SD 0.84),
#                                       5.30 mandibular; to chamber ceiling 6.3
# So 4.0 mm is the permissive end of both, and is used rather than the mean so
# that a genuinely high horn on this dentition is not shaved off.
#
# It is measured from the crown-most 15% of the tooth surface, not from every
# surface: the constraint is occlusal clearance, and a canal may still run close
# to a thin root wall laterally.
OCCLUSAL_BAND_FRAC = 0.15
# Anterior pulp genuinely reaches further coronally, and 4.0 mm was clipping it.
# Measured on this patient: with the constraint OFF, the coherent radiolucency
# starts at 2.7-3.7 mm from the incisal edge on the clean anteriors (9:3.1,
# 8:3.3, 6:3.4, 11:3.7, 24:3.0, 25:3.3, 22:2.7), against 3.3-3.9 on molars.
# Premolars come out at 0.4-1.1, which is threshold leakage, not anatomy --
# which is exactly why they needed the constraint in the first place. So the
# exception is for incisors and canines ONLY.
# Clearance scales with CROWN HEIGHT, which differs by tooth type. The 4.0 mm
# figure was derived from tooth 14 -- a molar, with a long crown -- and applying
# it to a premolar or an incisor squeezes the coronal pulp between it and the
# chamber floor until the crown reads as having almost none: premolars 20, 21,
# 28 and 29 came out with 0-6% of their pulp in the chamber. Literature puts
# cusp tip to pulp horn at 5.59 mm on a maxillary first molar; premolars and
# anteriors are shorter-crowned and their horns sit correspondingly closer.
OCCLUSAL_CLEARANCE_MM = 4.0     # molars
PREMOLAR_CLEARANCE_MM = 3.0
ANTERIOR_CLEARANCE_MM = 2.2     # incisors and canines
ANTERIOR_UNIVERSAL = frozenset((6, 7, 8, 9, 10, 11, 22, 23, 24, 25, 26, 27))
PREMOLAR_UNIVERSAL = frozenset((4, 5, 12, 13, 20, 21, 28, 29))


def occlusal_clearance(universal):
    if universal in ANTERIOR_UNIVERSAL:
        return ANTERIOR_CLEARANCE_MM
    if universal in PREMOLAR_UNIVERSAL:
        return PREMOLAR_CLEARANCE_MM
    return OCCLUSAL_CLEARANCE_MM

CHAMBER_OPEN_ITER = 1
TUBE_SCALE_BOUNDS = (0.15, 2.60)

MIN_ROOT_PULP = 150
ROOT_CANAL_R = (0.30, 0.13)

TRAJECTORY_MM = 1.6      # canal length used to estimate the apical direction
MARCH_MAX_MM = 4.0
# A foramen further from the apex than any reported one is not a foramen.
# With the canal now supplied by the measured tube, the trajectory is estimated
# from the tube's end; where that end sits high or its direction is poor the
# march exits the side of the root (tooth 5 came out at 4.78 mm). Reported
# deviations top out near 2.0 mm, so beyond that the extension is refused
# outright rather than recorded as anatomy -- an unplaced foramen is honest, a
# misplaced one is not.
FORAMEN_MAX_DEV_MM = 2.5
# A foramen placed by darkest-path exit rather than by extrapolating a measured
# trajectory is MODELLED, so it is constrained by the anatomical prior instead:
# searched within 1.5 mm of the apex rather than 2.5. Note this makes its
# agreement with the literature mean circular -- these placements are not
# independent evidence, and the report separates them from the trajectory ones.
ASSERT_EXIT_MM = 1.5
# Among the candidates, the CHEAPEST is not the right one -- it is systematically
# short, because a route that leaves the root wall early costs less than one
# running the last millimetre to the apex. Teeth 4 and 30's mesiolingual canal
# both stopped ~1.6 mm short, which the operator reads off a periapical
# immediately. Take the cheapest EXIT_COST_QUANTILE of candidates -- all of them
# plausible dark routes -- and among those choose the one nearest the apex.
EXIT_COST_QUANTILE = 0.30
# A canal must actually REACH its foramen, whatever produced it. Fixing the exit
# choice only helped canals that were asserted; tooth 30's mesiolingual comes
# from the MEASURED tube and still stopped 1.65 mm short, because the tube ends
# where pulp_all.py's centreline ends. Any root whose pulp stops further than
# this from the apex is carried the rest of the way.
APEX_REACH_MM = 1.0
# A ROOT MAY CARRY MORE THAN ONE CANAL, AND THE COMMONEST CASE IS THE ONE THAT
# MATTERS: the mesial root of a lower first molar holds MB and ML. Tooth 30 has
# three canals but only two roots, so asserting one canal per root left its ML
# as a stub in the coronal third -- which is what the operator saw. Where the
# canal count exceeds the root count the surplus goes to the largest roots (the
# mesial root of a lower molar is the broad one), and the extra exits are forced
# apart so they are two canals rather than one drawn twice.
MIN_CANAL_SEP_MM = 0.9
# CANALS ARE TRACED FROM THE ORIFICES DOWN, NOT BACK FROM THE APICES.
# Working from apices with a canal quota gets the count right only by accident
# and cannot represent the commonest real anatomy: two canals leaving the
# chamber and JOINING before the apex (Vertucci type II), which this dentition
# shows plainly in tooth 31's mesial root. One-canal-per-root left tooth 30's ML
# as a coronal stub.
#
# So the cost field is seeded at the APICAL exits and each orifice is traced
# down into it. Two orifices whose cheapest route reaches the same exit produce
# two paths that merge partway -- 2:1 falls out of the geometry rather than
# being special-cased -- while two that reach different exits stay separate
# (2:2). The ORIFICE count sets the number of canals, because that is where the
# canal is widest and most reliably resolved; the apical foramina are then
# however many distinct exits those paths actually arrive at.
ORIFICE_BELOW_MM = (0.4, 2.4)   # slab below the chamber floor to look in
ORIFICE_MIN_VOX = 6
ORIFICE_CONTRAST = 360.0        # HU below the slice's own dentin
# If fewer orifices turn up than the tooth should have, lower the bar and look
# again rather than accept the shortfall. The prior says HOW MANY to look for;
# the image still says WHERE each one is, and a canal that is merely faint is
# not a canal that is absent. Teeth 18 and 30 came up one short at 360.
ORIFICE_CONTRAST_STEPS = (360.0, 300.0, 250.0, 210.0)
# A RIBBON ORIFICE IS TWO CANALS, NOT ONE. Teeth 18 and 30 stayed one short at
# every contrast, because a mandibular molar's mesial canals are commonly joined
# at the orifice by an ISTHMUS -- MB and ML share one continuous ribbon there and
# separate further down. Detecting a single blob is correct; treating it as a
# single canal is not. An elongated orifice is therefore seeded at both ends of
# its long axis, which is what the anatomy is.
ISTHMUS_MIN_LEN_MM = 1.2
ISTHMUS_MIN_ASPECT = 2.0
# WHEN TWO CANALS SHARE ONE APICAL EXIT THEY MUST STILL TAKE DIFFERENT ROUTES.
# Tooth 19's mesial root has two orifices but only one exit within reach of the
# apex, so both routed to it on the same cost field and followed an identical
# corridor from just below the floor -- one canal wearing two labels. After a
# canal is drawn its corridor is made expensive, so the next one prefers its own
# route and converges only where there is no alternative. That convergence IS
# the 2:1 join, arrived at rather than asserted.
CANAL_REUSE_PENALTY = 6.0
# A CANAL MAY NOT LEAVE ITS OWN ROOT.
# Giving each canal its own cost field fixed the collapsed-sibling problem but
# left nothing holding a path inside the root it belongs to, and the reuse
# penalty actively pushes the second canal sideways looking for a cheaper route.
# The result was canals detouring through inter-root dentin -- 15-32% of the
# sub-floor pulp on teeth 3, 5, 12 and 14 lay outside every root footprint, and
# the operator saw it as a palatal canal branching into the buccal (5) and a DB
# canal wrapping into the MB (14). Below the chamber floor a canal is therefore
# confined to its own root's footprint; above it, canals share the chamber and
# are free.
ROOT_FOOTPRINT_PAD_MM = 0.8
ORIFICE_MIN_DEPTH_MM = 0.8      # the PDL is dark too -- stay off the surface
# The chamber FLOOR is not the apical end of the chamber mask. That mask is the
# whole opened threshold and runs the length of the tooth, so taking its extreme
# put the orifice band past the apex and found nothing at all. The floor is
# where the pulp stops being a chamber and becomes canals -- i.e. where its
# cross-section collapses from the chamber's width.
FLOOR_AREA_FRAC = 0.35
# THE THRESHOLD BELONGS TO THE CHAMBER; BELOW THE FLOOR ONLY TRACED CANALS.
# This is the defect underneath most of the others. Thresholded radiolucency
# was allowed to run the whole length of the tooth, and in the roots -- where a
# canal is 1-3 voxels wide and the contrast is marginal -- it returns speckle,
# not a canal. That speckle is what produced the "crunchiness", the fragments
# that needed bridging, and the dead-end twigs the operator sees as branches:
# 156 of them across 28 teeth once the measured tube stopped covering for it.
#
# Cutting the threshold at the chamber floor removes the whole class at source.
# Below the floor the geometry is exactly the traced canals and nothing else.
CHAMBER_FLOOR_OVERLAP_MM = 1.0   # keep a little below the floor so orifices join
# A second canal in the same root does NOT exit beside the first. MB and ML on a
# mesial root are separated by that root's buccolingual width -- 2-3 mm -- and
# each sits near its own local apex, not near the single extreme voxel the root
# is measured from. Searching both within 1.5 mm of that one point left teeth
# 19, 31, 3 and 14 a canal short. Multi-canal roots therefore search wider.
MULTI_EXIT_MM = 3.0

# A CONNECTED MASK IS NOT A CONNECTED MESH.
# The mask came out as one component for all 28 teeth while 24 of the 28 MESHES
# had floating pieces, which is what the operator could actually see. A bridge
# painted one voxel wide, smoothed at sigma 0.9 and cut at level 0.5, peaks near
# 0.33 -- below the isosurface -- so it vanishes from the mesh and leaves the
# fragment it was joining adrift. Checking `pieces_after` on the mask could
# never catch this; the check has to run on the field that is actually meshed.
RENDER_SIGMA = 0.9       # back to pulp_solid's value: the floor below, not a
                         # weak blur, is what keeps thin canals alive
THIN_VOX = 1.5           # voxels from background: below this, clamp; above, smooth
FLOOR = 0.55             # see mesh_field: no mask voxel may fall below the isolevel


def cost_field(roi, inside, pulp_hu, dentin_hu):
    """Cheap where the tissue is dark, impassable outside the tooth.

    The canal is the darkest continuous route through dentin, so a path that
    minimises accumulated intensity follows the canal wherever any contrast at
    all survives -- which the shading showed is everywhere, just weakly
    (144-298 HU apically against a ~70 HU noise floor).
    """
    c = (roi - pulp_hu) / max(dentin_hu - pulp_hu, 1.0)
    c = np.clip(c, 0.02, 4.0) ** 2          # square: strongly prefer the dark route
    c[~inside] = np.inf
    return c.astype(np.float64)


def apical_roots(tooth, arch, spacing):
    """One component per root, taken from a slab across the apical third."""
    zs = np.where(tooth.any(axis=(1, 2)))[0]
    if zs.size == 0:
        return []
    z0, z1 = int(zs.min()), int(zs.max())
    n = max(int(round(ROOT_SLAB_FRAC * (z1 - z0))), 3)
    slab = slice(z1 - n, z1 + 1) if arch == "upper" else slice(z0, z0 + n + 1)
    band = np.zeros_like(tooth)
    band[slab] = tooth[slab]
    lab, k = ndi.label(band, structure=np.ones((3, 3, 3)))
    out = []
    for i in range(1, k + 1):
        comp = lab == i
        if comp.sum() >= MIN_ROOT_VOX:
            out.append(comp)
    return out


def canal_tube(rec, v, shape, origin_idx, spacing, limit, scale=1.0):
    """Rasterise the MEASURED canal centrelines, clamped to the envelope."""
    out = np.zeros(shape, bool)
    sp = float(spacing[0])
    zz, yy, xx = np.indices(shape)
    for c in rec.get("canals", []):
        cen = np.asarray(c.get("centreline_lps", []), float)
        rad = np.asarray(c.get("radius_mm", []), float)
        if len(cen) < 3 or len(rad) != len(cen):
            continue
        apex = np.asarray(c.get("apical_position_lps", cen[-1]), float)
        dist = np.linalg.norm(cen - apex, axis=1)
        cap = canal_envelope_r(dist)
        for p, r0, cp in zip(cen, rad, cap):
            r = min(float(r0) * scale, float(cp))
            r = max(r, FORAMEN_MIN_RADIUS_MM)
            ix = np.asarray(v.index(*p), float)
            cx, cy, cz = ix[0] - origin_idx[0], ix[1] - origin_idx[1], ix[2] - origin_idx[2]
            k = int(np.ceil(r / sp)) + 1
            z0, z1 = max(0, int(cz) - k), min(shape[0], int(cz) + k + 1)
            y0, y1 = max(0, int(cy) - k), min(shape[1], int(cy) + k + 1)
            x0, x1 = max(0, int(cx) - k), min(shape[2], int(cx) + k + 1)
            if z0 >= z1 or y0 >= y1 or x0 >= x1:
                continue
            d2 = (((zz[z0:z1, y0:y1, x0:x1] - cz) * sp) ** 2
                  + ((yy[z0:z1, y0:y1, x0:x1] - cy) * sp) ** 2
                  + ((xx[z0:z1, y0:y1, x0:x1] - cx) * sp) ** 2)
            out[z0:z1, y0:y1, x0:x1] |= d2 <= r * r
    return out & limit


def face_path(path):
    """Re-walk an index path so consecutive voxels share a FACE, not a corner.

    MCP traceback steps diagonally, and a tube painted along diagonal steps is
    joined only at corners -- which is no surface at all once it is meshed. One
    axis is moved at a time instead, which costs nothing and makes the bridge
    survive as geometry rather than only as a voxel count.
    """
    out = [tuple(int(c) for c in path[0])]
    for nxt in path[1:]:
        cur = list(out[-1])
        for ax in range(3):
            while cur[ax] != int(nxt[ax]):
                cur[ax] += 1 if int(nxt[ax]) > cur[ax] else -1
                out.append(tuple(cur))
    return out


def despeckle(mask, min_vox=None):
    """Drop face-connected fragments too small to be anatomy.

    Thresholding leaves single voxels and short chains clinging to the pulp by a
    corner. They count as connected under 26-connectivity -- which is why the
    mask reported one piece -- but they mesh as free-floating debris, and that
    debris is what the operator saw drifting beside teeth 2, 3, 4, 14 and 15.
    The main body runs 10-20k voxels and every speck was under 260.
    """
    if min_vox is None:
        min_vox = PS.MIN_PIECE_VOX
    lab, n = ndi.label(mask, structure=ndi.generate_binary_structure(3, 1))
    if n <= 1:
        return mask
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    keep = [i + 1 for i in range(n) if sizes[i] >= min_vox]
    return np.isin(lab, keep)


def find_orifices(chamber, tooth_solid, roi, spacing, arch, max_n):
    """Distinct dark entries just apical to the chamber floor, largest first.

    Two traps here. The PERIODONTAL LIGAMENT is dark and sits just outside the
    root, so without a depth requirement the detector returns the root's whole
    dark rind -- 18 to 35 "orifices" on teeth whose prior is 3 or 4. And the
    contrast available at the floor is 400-800 HU, far more than apically, so
    the cut has to be much tighter here than the taper uses further down.
    """
    cz = np.where(chamber.any(axis=(1, 2)))[0]
    if cz.size == 0:
        return []
    area = np.array([int(chamber[k].sum()) for k in cz])
    wide = cz[area >= FLOOR_AREA_FRAC * area.max()]
    if wide.size == 0:
        return []
    floor = int(wide.max()) if arch == "upper" else int(wide.min())
    lo = int(round(ORIFICE_BELOW_MM[0] / float(spacing[2])))
    hi = int(round(ORIFICE_BELOW_MM[1] / float(spacing[2])))
    if arch == "upper":
        z0, z1 = floor + lo, floor + hi
    else:
        z0, z1 = max(floor - hi, 0), max(floor - lo, 1)
    depth = ndi.distance_transform_edt(tooth_solid, sampling=tuple(spacing))
    inner = tooth_solid & (depth >= ORIFICE_MIN_DEPTH_MM)
    best = []
    for contrast in ORIFICE_CONTRAST_STEPS:
        dark = np.zeros_like(chamber)
        for k in range(max(z0, 0), min(z1, chamber.shape[0])):
            mm = tooth_solid[k]
            if mm.sum() < 40:
                continue
            ref = float(np.percentile(roi[k][mm], 45))
            dark[k] = inner[k] & (roi[k] < ref - contrast)
        lab, n = ndi.label(dark, structure=np.ones((3, 3, 3)))
        if n == 0:
            continue
        sizes = ndi.sum(dark, lab, range(1, n + 1))
        vsp = np.asarray(spacing, float)[::-1]
        out = []
        for i in np.argsort(sizes)[::-1]:
            if sizes[i] < ORIFICE_MIN_VOX or len(out) >= max_n:
                break
            pts = np.argwhere(lab == i + 1)
            mmv = pts * vsp
            X = mmv - mmv.mean(0)
            seeds = []
            if len(pts) >= 8:
                _, _, vt = np.linalg.svd(X, full_matrices=False)
                proj = X @ vt[0]
                length = float(proj.max() - proj.min())
                _w = X @ vt[1]
                width = float(max(_w.max() - _w.min(), float(vsp.min())))
                if (length >= ISTHMUS_MIN_LEN_MM
                        and length / width >= ISTHMUS_MIN_ASPECT
                        and len(out) + 2 <= max_n):
                    seeds = [pts[int(np.argmin(proj))], pts[int(np.argmax(proj))]]
            if not seeds:
                c = pts.mean(0)
                # the component's own voxel closest to its centroid, so the seed
                # lies inside a canal rather than between two of them
                seeds = [pts[int(np.argmin(np.linalg.norm(pts - c, axis=1)))]]
            for sd in seeds:
                out.append(tuple(int(q) for q in sd))
        if len(out) > len(best):
            best = out
        if len(best) >= max_n:
            break
    return best


def pick_exits(cand, cumulative, apex_i, vsp, n):
    """Up to n exits, each a plausible dark route, forced apart from each other."""
    out = []
    remaining = cand
    for _ in range(max(n, 1)):
        if not len(remaining):
            break
        e = pick_exit(remaining, cumulative, apex_i, vsp)
        if e is None:
            break
        out.append(e)
        keep = (np.linalg.norm((remaining - np.asarray(e)) * vsp, axis=1)
                >= MIN_CANAL_SEP_MM)
        remaining = remaining[keep]
    return out


def pick_exit(cand, cumulative, apex_i, vsp):
    """Cheapest plausible dark routes, then the one closest to the apex."""
    c = cumulative[tuple(cand.T)]
    ok = np.isfinite(c)
    if not ok.any():
        return None
    cand, c = cand[ok], c[ok]
    thresh = np.quantile(c, EXIT_COST_QUANTILE)
    keep = c <= thresh
    cand = cand[keep]
    dist = np.linalg.norm((cand - apex_i) * vsp, axis=1)
    return tuple(int(q) for q in cand[int(np.argmin(dist))])


def surface_of(mask):
    return mask & ~ndi.binary_erosion(mask, np.ones((3, 3, 3)))


def paint(out, path, radius_mm, spacing, limit):
    """Draw a tapering tube along an index path."""
    sp = np.asarray(spacing, float)
    zz, yy, xx = np.indices(out.shape)
    n = len(path)
    for i, (z, y, x) in enumerate(path):
        r = radius_mm[0] + (radius_mm[1] - radius_mm[0]) * (i / max(n - 1, 1))
        k = int(np.ceil(r / sp.min())) + 1
        z0, z1 = max(0, z - k), min(out.shape[0], z + k + 1)
        y0, y1 = max(0, y - k), min(out.shape[1], y + k + 1)
        x0, x1 = max(0, x - k), min(out.shape[2], x + k + 1)
        d2 = (((zz[z0:z1, y0:y1, x0:x1] - z) * sp[2]) ** 2
              + ((yy[z0:z1, y0:y1, x0:x1] - y) * sp[1]) ** 2
              + ((xx[z0:z1, y0:y1, x0:x1] - x) * sp[0]) ** 2)
        out[z0:z1, y0:y1, x0:x1] |= (d2 <= r * r) & limit[z0:z1, y0:y1, x0:x1]


def connect(pulp_mask, tooth_solid, roi, spacing, arch, pulp_hu, dentin_hu,
            canal_count=1, orifices=()):
    """Return (mask, added, foramina) -- one body, carried to each root apex."""
    pulp_mask = despeckle(pulp_mask)
    lab, n = ndi.label(pulp_mask, structure=ndi.generate_binary_structure(3, 1))
    if n == 0:
        return pulp_mask, np.zeros_like(pulp_mask), []
    sizes = ndi.sum(pulp_mask, lab, range(1, n + 1))
    main = int(np.argmax(sizes)) + 1

    cost = cost_field(roi, tooth_solid, pulp_hu, dentin_hu)
    mcp = MCP_Geometric(cost, sampling=tuple(float(s) for s in spacing[::-1]))
    starts = np.argwhere(lab == main)
    cumulative, _ = mcp.find_costs([tuple(p) for p in starts])

    out = pulp_mask.copy()
    added = np.zeros_like(pulp_mask)
    dist = ndi.distance_transform_edt(pulp_mask, sampling=tuple(spacing))

    # --- bridges: each island back to the main body along the darkest route ---
    vsp = np.asarray(spacing, float)[::-1]
    bridged, dropped = [], []
    for i in range(1, n + 1):
        if i == main:
            continue
        comp = np.argwhere(lab == i)
        c = cumulative[tuple(comp.T)]
        if not np.isfinite(c).any():
            dropped.append((0.0, len(comp)))
            out &= ~(lab == i)
            continue
        seed = tuple(comp[int(np.nanargmin(np.where(np.isfinite(c), c, np.nan)))])
        try:
            path = mcp.traceback(seed)
        except ValueError:
            dropped.append((0.0, len(comp)))
            out &= ~(lab == i)
            continue
        span = float(np.linalg.norm(
            (np.asarray(path[0], float) - np.asarray(path[-1], float)) * vsp))
        limit = MAX_BRIDGE_MM
        if len(comp) >= 8:
            pts = comp * vsp
            X = pts - pts.mean(0)
            _, _, vt = np.linalg.svd(X, full_matrices=False)
            p0, p1 = X @ vt[0], X @ vt[1]
            length = float(p0.max() - p0.min())
            width = float(max(p1.max() - p1.min(), float(vsp.min())))
            if length >= CANAL_MIN_LEN_MM and length / width >= CANAL_MIN_ASPECT:
                limit = CANAL_BRIDGE_MM
        if span > limit:
            dropped.append((span, len(comp)))
            out &= ~(lab == i)
            continue
        bridged.append((span, len(comp)))
        r_local = float(max(dist[seed], FORAMEN_MIN_RADIUS_MM))
        before = out.copy()
        paint(out, face_path(path), (r_local, r_local), spacing, tooth_solid)
        added |= out & ~before

    # --- extensions: carry each root's canal to its foramen on the surface ---
    # ORDER MATTERS: ORIFICE TRACING IS PRIMARY, THE OTHERS ARE FALLBACKS.
    # Three mechanisms can create a canal here -- tracing from an orifice,
    # asserting one in an apparently empty root, and extrapolating a measured
    # trajectory. Running all three unconditionally layered canal on canal:
    # tooth 14 ended up with SIX foramina for three roots, and the extras are
    # exactly the offshoots the operator saw wrapping from DB into MB. Orifice
    # tracing is the only one that starts from where the canal demonstrably is,
    # so it runs FIRST and claims its roots; the other two then fill only what
    # it could not reach.
    # TRACE EACH CANAL SEPARATELY, ORIFICE TO ITS OWN EXIT.
    # Seeding ONE cost field at all the apical exits and tracing every orifice
    # into it collapses canals that share a root: both mesial orifices snap onto
    # the same cheapest corridor immediately, so MB and ML ran as a single track
    # from just below the floor. Teeth 30, 19 and 31 all showed one canal down
    # the whole mesial root.
    #
    # So each root pairs its orifices with its own exits and routes each pair on
    # a cost field seeded at THAT exit alone. Two canals then keep their own
    # courses and converge only where the geometry makes them -- which is what
    # 2:1 actually is, rather than two labels on one tube. Where a root has more
    # orifices than exits the surplus orifices share an exit, and that is the
    # 2:1 case; where counts match they stay separate to the apex (2:2).
    n_merged = 0
    served_roots = set()
    foramina = []
    # Geometry that is a CANAL, as opposed to chamber or threshold residue.
    # Below the floor the output is rebuilt from this alone -- see the end of
    # this function -- so every canal paint must be recorded into it.
    canal_geom = np.zeros_like(out)
    roots = apical_roots(tooth_solid, arch, spacing)
    surf = surface_of(tooth_solid)
    asserted = 0
    asserted_foramina, done_roots = [], []
    # chamber floor: where the pulp's cross-section collapses from chamber width
    floor_z = None
    _cz = np.where(pulp_mask.any(axis=(1, 2)))[0]
    if _cz.size:
        _ar = np.array([int(pulp_mask[k].sum()) for k in _cz])
        _wide = _cz[_ar >= 0.35 * _ar.max()]
        if _wide.size:
            floor_z = int(_wide.max()) if arch == "upper" else int(_wide.min())
    if orifices:
        root_of = {}
        for oi, orf in enumerate(orifices):
            best_r, best_d = None, None
            for ri, root in enumerate(roots):
                c = np.argwhere(root).mean(0)
                dd = float(np.linalg.norm((np.asarray(orf, float) - c)[1:] * vsp[1:]))
                if best_d is None or dd < best_d:
                    best_r, best_d = ri, dd
            if best_r is not None:
                root_of.setdefault(best_r, []).append(orf)

        for ri, root in enumerate(roots):
            orfs = root_of.get(ri, [])
            if not orfs:
                continue
            rz = np.argwhere(root)
            apex_i = rz[np.argmax(rz[:, 0])] if arch == "upper" else rz[np.argmin(rz[:, 0])]
            cand = np.argwhere(root & surf)
            if not len(cand):
                continue
            near = np.linalg.norm((cand - apex_i) * vsp, axis=1) <= ASSERT_EXIT_MM
            if not near.any():
                continue
            exits = pick_exits(cand[near], cumulative, apex_i, vsp, len(orfs))
            if not exits:
                continue
            if len(exits) < len(orfs):
                n_merged += len(orfs) - len(exits)
            # confine this root's canals to this root, below the chamber floor
            fp = ndi.binary_dilation(
                root.any(axis=0),
                np.ones((2 * int(round(ROOT_FOOTPRINT_PAD_MM / float(spacing[1]))) + 1,) * 2))
            allowed = tooth_solid.copy()
            if floor_z is not None:
                if arch == "upper":
                    allowed[floor_z + 1:] &= fp[None, :, :]
                else:
                    allowed[:floor_z] &= fp[None, :, :]
            root_cost = np.where(allowed, cost, np.inf)
            served_roots.add(ri)

            # 2:2 -> each orifice reaches its own exit.
            # 2:1 -> the SECOND canal is routed to the FIRST CANAL, not to the
            # same exit. Routing both to one exit and pushing them apart with a
            # reuse penalty (which is what this did) makes the second canal
            # detour and then rejoin, producing a loop -- the offshoot that
            # "wraps into the MB". Joining canal to canal produces exactly one
            # junction and no loop, which is what Vertucci type II IS.
            joined_here = np.zeros_like(out)
            for j, orf in enumerate(orfs):
                if j < len(exits):
                    seeds = [tuple(int(q) for q in exits[j])]
                elif joined_here.any():
                    seeds = [tuple(int(q) for q in p2)
                             for p2 in np.argwhere(joined_here)]
                    n_merged += 1
                else:
                    seeds = [tuple(int(q) for q in exits[0])]
                one = MCP_Geometric(root_cost,
                                    sampling=tuple(float(x) for x in
                                                   spacing[::-1]))
                one_cost, _ = one.find_costs(seeds)
                if not np.isfinite(one_cost[orf]):
                    continue
                try:
                    path = one.traceback(orf)
                except ValueError:
                    continue
                # seeded at the exit (or at the sibling canal), so path[0] is
                # the distal end and path[-1] the orifice: the taper runs narrow
                # apically, wide at the floor.
                before = out.copy()
                paint(out, face_path(path),
                      (ROOT_CANAL_R[1], max(float(dist[orf]), ROOT_CANAL_R[0])),
                      spacing, tooth_solid)
                canal_geom |= out & ~before
                added |= out & ~before
                joined_here |= out & ~before
                if j < len(exits):
                    e0 = tuple(int(q) for q in path[0])
                    if e0 not in {tuple(f["exit_index"]) for f in foramina}:
                        foramina.append(dict(exit_index=[int(q) for q in e0],
                                             apex_index=[int(q) for q in apex_i],
                                             path_len=len(path),
                                             source="orifice"))

    served = {i for i in served_roots}

    # --- assert a canal in any root the threshold left effectively empty ---
    for ri, root in enumerate(roots):
        if ri in served or (out & root).sum() >= MIN_ROOT_PULP:
            continue
        rz = np.argwhere(root)
        apex_i = rz[np.argmax(rz[:, 0])] if arch == "upper" else rz[np.argmin(rz[:, 0])]
        cand = np.argwhere(root & surf)
        if not len(cand):
            continue
        near = np.linalg.norm((cand - apex_i) * vsp, axis=1) <= ASSERT_EXIT_MM
        if not near.any():
            continue
        cand = cand[near]
        exit_idx = pick_exit(cand, cumulative, apex_i, vsp)
        if exit_idx is None:
            continue
        try:
            path = mcp.traceback(exit_idx)
        except ValueError:
            continue
        before = out.copy()
        paint(out, face_path(path), ROOT_CANAL_R, spacing, tooth_solid)
        canal_geom |= out & ~before
        added |= out & ~before
        asserted += 1
        # Record the exit as this root's foramen HERE. Painting a canal to the
        # surface and then leaving a separate trajectory step to discover it
        # meant a root could end up with a canal and no foramen -- teeth 5 and
        # 12 each got a second canal but only one foramen, and tooth 20 none at
        # all. The exit is already known at this point.
        asserted_foramina.append(dict(exit_index=[int(q) for q in exit_idx],
                                      apex_index=[int(q) for q in apex_i],
                                      path_len=len(path), source="asserted"))
        done_roots.append(root)

    foramina.extend(asserted_foramina)
    for ri, root in enumerate(roots):
        if ri in served or any(r is root for r in done_roots):
            continue
        rz = np.argwhere(root)
        apex_i = rz[np.argmax(rz[:, 0])] if arch == "upper" else rz[np.argmin(rz[:, 0])]
        inroot = np.argwhere(out & root)
        if len(inroot) < 8:
            continue
        # the canal's terminus in this root, and its direction approaching it
        term = inroot[np.argmax(inroot[:, 0])] if arch == "upper" \
            else inroot[np.argmin(inroot[:, 0])]
        d = np.linalg.norm((inroot - term) * vsp, axis=1)
        seg = inroot[d <= TRAJECTORY_MM]
        if len(seg) < 8:
            continue
        pts = seg * vsp
        u, sv, vt = np.linalg.svd(pts - pts.mean(0), full_matrices=False)
        axis = vt[0]
        apical = np.array([1.0, 0, 0]) if arch == "upper" else np.array([-1.0, 0, 0])
        if np.dot(axis, apical) < 0:
            axis = -axis
        # march the trajectory until it leaves the root
        start = term.astype(float)
        step = 0.5 * float(vsp.min())
        exit_idx, prev = None, tuple(term)
        for i in range(1, int(MARCH_MAX_MM / step)):
            q = start + axis * (i * step) / vsp
            qi = tuple(int(round(c)) for c in q)
            if not all(0 <= qi[a] < out.shape[a] for a in range(3)):
                break
            if not tooth_solid[qi]:
                exit_idx = prev
                break
            prev = qi
        if exit_idx is None or exit_idx == tuple(term):
            continue
        if float(np.linalg.norm((np.asarray(exit_idx, float) - apex_i) * vsp)) \
                > FORAMEN_MAX_DEV_MM:
            continue
        r0 = float(max(dist[tuple(term)], FORAMEN_MIN_RADIUS_MM))
        path = [tuple(term), exit_idx]
        # resample the straight run so paint() lays a continuous tube
        n_step = max(int(np.linalg.norm((np.array(exit_idx) - term) * vsp)
                         / (0.5 * float(vsp.min()))), 2)
        path = [tuple(int(round(c)) for c in
                      (term + (np.array(exit_idx) - term) * (j / n_step)))
                for j in range(n_step + 1)]
        before = out.copy()
        paint(out, face_path(path), (r0, FORAMEN_MIN_RADIUS_MM), spacing,
              tooth_solid)
        added |= out & ~before
        foramina.append(dict(exit_index=[int(q) for q in exit_idx],
                             apex_index=[int(q) for q in apex_i],
                             path_len=len(path)))
    # Every root must end in exactly one foramen. Where the trajectory could not
    # be estimated -- too few voxels near the terminus, or a direction that
    # exits the side of the root -- fall back to the darkest-path exit, the same
    # construction the assertion uses. A root with a canal and no foramen is a
    # canal that stops inside solid dentin.
    have = [f["apex_index"] for f in foramina]
    for root in roots:
        rz = np.argwhere(root)
        apex_i = rz[np.argmax(rz[:, 0])] if arch == "upper" else rz[np.argmin(rz[:, 0])]
        if any(np.array_equal(np.asarray(h), apex_i) for h in have):
            continue
        cand = np.argwhere(root & surf)
        if not len(cand):
            continue
        near = np.linalg.norm((cand - apex_i) * vsp, axis=1) <= ASSERT_EXIT_MM
        if not near.any():
            continue
        cand = cand[near]
        exit_idx = pick_exit(cand, cumulative, apex_i, vsp)
        if exit_idx is None:
            continue
        try:
            path = mcp.traceback(exit_idx)
        except ValueError:
            continue
        before = out.copy()
        paint(out, face_path(path), ROOT_CANAL_R, spacing, tooth_solid)
        canal_geom |= out & ~before
        added |= out & ~before
        foramina.append(dict(exit_index=[int(q) for q in exit_idx],
                             apex_index=[int(q) for q in apex_i],
                             path_len=len(path), source="fallback"))

    # FINAL: carry any canal that still stops short the last stretch to its
    # foramen. Gating the fallbacks on "orifice tracing already served this
    # root" removed this guarantee and tooth 13 came up 1.85 mm short. This is
    # deliberately a SHORT STRAIGHT extension from the existing terminus, not
    # another routed canal -- routing again is what produced the offshoots.
    for ri, root in enumerate(roots):
        pr = np.argwhere(out & root)
        if not len(pr):
            continue
        rz = np.argwhere(root)
        apex_i = rz[np.argmax(rz[:, 0])] if arch == "upper" else rz[np.argmin(rz[:, 0])]
        dd = np.linalg.norm((pr - apex_i) * vsp, axis=1)
        if dd.min() <= APEX_REACH_MM:
            continue
        term = pr[int(np.argmin(dd))]
        cand = np.argwhere(root & surf)
        if not len(cand):
            continue
        near = np.linalg.norm((cand - apex_i) * vsp, axis=1) <= ASSERT_EXIT_MM
        if not near.any():
            continue
        ex = pick_exit(cand[near], cumulative, apex_i, vsp)
        if ex is None:
            continue
        span = float(np.linalg.norm((np.asarray(ex, float) - term) * vsp))
        n_step = max(int(span / (0.5 * float(vsp.min()))), 2)
        path = [tuple(int(round(c)) for c in
                      (term + (np.asarray(ex, float) - term) * (j / n_step)))
                for j in range(n_step + 1)]
        before = out.copy()
        paint(out, face_path(path),
              (max(float(dist[tuple(term)]), ROOT_CANAL_R[1]), ROOT_CANAL_R[1]),
              spacing, tooth_solid)
        canal_geom |= out & ~before
        added |= out & ~before
        if tuple(ex) not in {tuple(f["exit_index"]) for f in foramina}:
            foramina.append(dict(exit_index=[int(q) for q in ex],
                                 apex_index=[int(q) for q in apex_i],
                                 path_len=len(path), source="fallback"))

    # BELOW THE FLOOR, THE GEOMETRY IS THE CANALS AND NOTHING ELSE.
    # This is the rule the whole module was missing. Thresholded radiolucency in
    # a root is speckle, not a canal, and every downstream problem grew out of
    # keeping it: the fragments that needed bridging, the crunchiness, and the
    # dead-end twigs that read as branches. Enforcing it here deletes the class
    # rather than filtering its symptoms one at a time.
    if floor_z is not None:
        ov = int(round(CHAMBER_FLOOR_OVERLAP_MM / float(spacing[2])))
        coronal_keep = np.zeros_like(out)
        if arch == "upper":
            coronal_keep[:floor_z + ov + 1] = True
        else:
            coronal_keep[max(floor_z - ov, 0):] = True
        out = (out & coronal_keep) | canal_geom

    out = despeckle(out)
    return (out, added & out, foramina, bridged, dropped, asserted,
            len(orifices), n_merged)


def mesh_field(mask, sigma=RENDER_SIGMA):
    """Smoothed occupancy that cannot drop a voxel the mask says is pulp.

    Any structure a voxel or two across -- a real apical canal included -- falls
    under the 0.5 isolevel once smoothed, so thin pulp vanishes from the mesh
    while remaining in the mask. Flooring those voxels just above the isolevel
    keeps them, costs no volume, and cannot delete a canal.

    THE FLOOR APPLIES ONLY WHERE THE STRUCTURE IS THIN. Applying it to every
    mask voxel -- including thick chamber walls, whose surface voxels sit near
    0.5 by definition -- shoves the isosurface outward by an uneven fraction of
    a voxel and pebbles the surface. That is the hard-clamp terracing CLAUDE.md
    already warns about, and it is what made the premolar and incisor chambers
    look crunchy. Thick anatomy is left to the Gaussian, which is what makes it
    smooth; only the canals, which have no smooth rendering available at this
    voxel size, are clamped.
    """
    f = ndi.gaussian_filter(mask.astype(np.float32), sigma)
    thin = ndi.distance_transform_edt(mask) <= THIN_VOX
    np.maximum(f, np.where(mask & thin, FLOOR, 0.0).astype(np.float32), out=f)
    return f


def mesh_continuity(mask, sigma=RENDER_SIGMA):
    """Components the isosurface will actually have (face connectivity).

    26-connectivity counts a corner touch as joined; a surface does not.
    """
    lab, n = ndi.label(mesh_field(mask, sigma) >= 0.5,
                       structure=ndi.generate_binary_structure(3, 1))
    return n


def mesh_components(verts, faces):
    """Connected components of a triangle soup, by exact vertex identity."""
    q = np.round(np.asarray(verts, float), 4)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    idx = inv[np.asarray(faces)]
    par = list(range(int(inv.max()) + 1))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for t in idx:
        for b in (t[1], t[2]):
            ra, rb = find(t[0]), find(b)
            if ra != rb:
                par[ra] = rb
    return len({find(t[0]) for t in idx})


# DECIMATION IS WHAT BREAKS THE CANALS, AND IT DOES SO ERRATICALLY.
# marching_cubes returns one surface and Taubin keeps it; collapsing ~24,500
# triangles to 3,500 pinches off the one-voxel canals. The relationship is not
# monotone -- one tooth came apart at 3,500, held at 5,000, came apart again at
# 7,000 and 10,000 -- so no single budget is safe. Take the smallest budget that
# actually survives, per tooth, and verify rather than assume.
TRI_BUDGETS = (3500, 5000, 7000, 10000, 14000, 20000)


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
    all_bridged, all_dropped = [], []
    n_asserted = 0
    n_capped = 0
    tot_orifices = 0
    tot_merged = 0
    by_source = {}
    print(f"{'Univ':>4s} {'pieces':>6s} {'->':>3s} {'mm3':>7s} {'added':>6s} "
          f"{'foramina':>8s} {'apex dev mm':>11s} {'thick':>5s}")
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
            origin_idx = (sl[2].start, sl[1].start, sl[0].start)   # x, y, z
            rec = pulp.get(str(num), {})
            pulp_hu = float(rec.get("pulp_density_hu", PS.PULP_FALLBACK_HU))
            target = rec.get("total_lumen_mm3")

            m_solid = m.copy()
            for k in range(m.shape[0]):
                if m[k].any():
                    m_solid[k] = ndi.binary_fill_holes(m[k])

            def asm(frac):
                return PS.solid_pulp(sub, m, sp, pulp_hu, None, arch, frac=frac) & m_solid

            # The old search calibrated the raw threshold to the whole pulp
            # volume; the chamber search below supersedes it. Running both cost
            # 24 threshold evaluations per tooth and timed the pass out.
            want = target * PS.SHADING_SCALE if target else None
            tooth_mm3 = rec.get("tooth_mm3")
            if want and tooth_mm3:
                capped = PULP_FRACTION_MAX * tooth_mm3 * PS.SHADING_SCALE
                if capped < want:
                    n_capped += 1
                    want = capped

            # SPLIT THE VOLUME BUDGET; DO NOT LET THE CHAMBER EAT IT ALL.
            # Calibrating the threshold against the WHOLE pulp volume and then
            # adding the canal on top made the chamber bulge coronally: with the
            # canal clamped to literature calibre, the chamber was absorbing
            # nearly the entire budget in the crown, and the operator saw it on
            # 14 teeth. The canal's volume is measured, so it is subtracted
            # first and the chamber is calibrated to what remains.
            cross = ndi.generate_binary_structure(3, 1)

            # Pulp may not lie within CHAMBER_MIN_DEPTH_MM of the surface in
            # the coronal half; apically there is no such limit.
            _d = ndi.distance_transform_edt(m_solid, sampling=tuple(sp))
            _zs = np.where(m_solid.any(axis=(1, 2)))[0]
            _mid = (int(_zs.min()) + int(_zs.max())) // 2 if _zs.size else 0
            coronal = np.zeros_like(m_solid)
            if arch == "upper":
                coronal[:_mid] = True
            else:
                coronal[_mid:] = True
            _surf = m_solid & ~ndi.binary_erosion(m_solid, np.ones((3, 3, 3)))
            _h = int(_zs.max()) - int(_zs.min()) if _zs.size else 0
            _n = max(int(round(OCCLUSAL_BAND_FRAC * _h)), 2)
            occ = np.zeros_like(m_solid)
            if arch == "upper":                      # crown at LOW z
                occ[int(_zs.min()):int(_zs.min()) + _n + 1] = \
                    _surf[int(_zs.min()):int(_zs.min()) + _n + 1]
            else:                                    # crown at HIGH z
                occ[int(_zs.max()) - _n:int(_zs.max()) + 1] = \
                    _surf[int(_zs.max()) - _n:int(_zs.max()) + 1]
            d_occ = (ndi.distance_transform_edt(~occ, sampling=tuple(sp))
                     if occ.any() else np.full(m_solid.shape, np.inf))
            domain = (m_solid
                      & ~(coronal & (_d < CHAMBER_MIN_DEPTH_MM))
                      & (d_occ >= occlusal_clearance(num)))
            deep = domain

            def chamber_at(frac):
                c = ndi.binary_opening(asm(frac) & deep, cross,
                                       iterations=CHAMBER_OPEN_ITER)
                cl, cn = ndi.label(c, structure=np.ones((3, 3, 3)))
                if cn > 1:
                    csz = ndi.sum(c, cl, range(1, cn + 1))
                    c = cl == (int(np.argmax(csz)) + 1)
                return c

            # NO TUBE. ONE CANAL MODEL, NOT TWO.
            # pulp.json's centrelines and the orifice traces are INDEPENDENT
            # reconstructions of the same canals; unioning them means that
            # wherever they disagree the difference renders as a Y-shaped
            # offshoot. Six sources of geometry were being merged here and the
            # result carried 71 dead-end twigs across 28 teeth, with 124 branch
            # points on tooth 31 alone. Orifice tracing is the one that starts
            # from where the canal demonstrably is, so it is now the ONLY canal
            # model; pulp.json stays a measurement of lumen volume and no longer
            # contributes geometry.
            tube = np.zeros_like(m_solid)
            if want:
                want_chamber = max(want - tube.sum() * vox, 0.15 * want)
                lo2, hi2 = 0.25, 1.80
                for _ in range(12):
                    mid = 0.5 * (lo2 + hi2)
                    if chamber_at(mid).sum() * vox > want_chamber:
                        lo2 = mid
                    else:
                        hi2 = mid
                chamber = chamber_at(0.5 * (lo2 + hi2))
            else:
                chamber = chamber_at(0.5)
            # Fit the tube against the FIXED chamber so the total lands on the
            # budget. Splitting the budget but then rasterising the tube at a
            # nominal scale left the total unbounded -- 2313 mm3 against a 1495
            # target -- because nothing constrained the sum. The envelope still
            # caps calibre, so this can only ever shrink the canal, never
            # inflate it past what the anatomy allows.
            if want and tube.any():
                tlo, thi = TUBE_SCALE_BOUNDS
                for _ in range(12):
                    tmid = 0.5 * (tlo + thi)
                    got = ((chamber | canal_tube(rec, v, m.shape, origin_idx, sp,
                                                 domain, tmid)).sum() * vox)
                    if got > want:
                        thi = tmid
                    else:
                        tlo = tmid
                tube = canal_tube(rec, v, m.shape, origin_idx, sp, domain,
                                  0.5 * (tlo + thi))
            # CUT THE CHAMBER AT ITS FLOOR. Everything apical to it comes from
            # canal tracing, so threshold speckle in the roots cannot survive.
            czs = np.where(chamber.any(axis=(1, 2)))[0]
            if czs.size:
                ca = np.array([int(chamber[k].sum()) for k in czs])
                wide = czs[ca >= FLOOR_AREA_FRAC * ca.max()]
                if wide.size:
                    ov = int(round(CHAMBER_FLOOR_OVERLAP_MM / float(sp[2])))
                    if arch == "upper":
                        cut = int(wide.max()) + ov
                        chamber[cut + 1:] = False
                    else:
                        cut = int(wide.min()) - ov
                        chamber[:max(cut, 0)] = False
            P = chamber
            if not P.any():
                P = chamber_at(0.5)

            _, n_before = ndi.label(P, structure=np.ones((3, 3, 3)))
            dentin = float(np.percentile(sub[m], 45))
            n_canals = int(rec.get("canal_count_prior",
                                   len(rec.get("canals", [])) or 1))
            orf = find_orifices(chamber, domain, sub, sp, arch, n_canals)
            (joined, added, foramina, bridged, dropped, asserted,
             n_orf, n_merge) = connect(
                P, domain, sub, sp, arch, pulp_hu, dentin,
                canal_count=n_canals, orifices=orf)
            tot_orifices += n_orf
            tot_merged += n_merge
            n_asserted += asserted
            all_bridged.extend(bridged)
            all_dropped.extend(dropped)
            _, n_after = ndi.label(joined,
                                   structure=ndi.generate_binary_structure(3, 1))
            ncomp, grown = mesh_continuity(joined), 0

            # EVERY COORDINATE THAT LEAVES THIS FUNCTION IS A WORLD COORDINATE.
            # CLAUDE.md invariant 8 -- this bug class has already shipped three
            # times, and a foramen is exactly the kind of small object whose
            # scalars (deviation, diameter) stay plausible while the point sits
            # in the wrong quadrant.
            recs = []
            for f in foramina:
                ez, ey, ex = f["exit_index"]
                az, ay, ax = f["apex_index"]
                ew = v.world(origin_idx[0] + ex, origin_idx[1] + ey,
                             origin_idx[2] + ez)
                aw = v.world(origin_idx[0] + ax, origin_idx[1] + ay,
                             origin_idx[2] + az)
                dev = float(np.linalg.norm(np.asarray(ew) - np.asarray(aw)))
                devs.append(dev)
                how = f.get("source", "trajectory")
                recs.append(dict(world_lps=[float(q) for q in ew],
                                 root_apex_lps=[float(q) for q in aw],
                                 apex_deviation_mm=round(dev, 3),
                                 radius_mm=FORAMEN_MIN_RADIUS_MM,
                                 source=how,
                                 provenance=("DERIVED" if how == "trajectory"
                                             else "MODELLED")))
                by_source.setdefault(how, []).append(dev)
            np.save(os.path.join(outdir, f"{fma}-pulp.npy"), joined)
            f = mesh_field(joined)
            verts, faces, _, _ = marching_cubes(f, level=0.5)
            # WORLD, not indices -- CLAUDE.md invariant 8. marching_cubes
            # returns (z, y, x); origin_idx is (x, y, z).
            world = np.empty_like(verts)
            world[:, 0] = v.origin[0] + (origin_idx[0] + verts[:, 2]) * sp[0]
            world[:, 1] = v.origin[1] + (origin_idx[1] + verts[:, 1]) * sp[1]
            world[:, 2] = v.origin[2] + (origin_idx[2] + verts[:, 0]) * sp[2]
            world = taubin(world, faces, 10)
            world, faces, budget = decimate_connected(world, faces)
            world = taubin(world, faces, 3)
            mc = mesh_components(world, faces)
            write_binary_stl(os.path.join(outdir, f"{fma}-pulp.stl"), world, faces)
            dv = ", ".join(f"{r['apex_deviation_mm']:.2f}" for r in recs) or "-"
            warn = "" if mc == 1 else f"  MESH IN {mc} PIECES"
            print(f"{num:4d} {n_before:6d} {'->':>3s} {joined.sum() * vox:7.1f} "
                  f"{added.sum() * vox:6.1f} {len(recs):8d} {dv:>11s} "
                  f"{grown:5d}{warn}")
            report[fma] = dict(universal=num, arch=arch,
                               pulp_mm3=round(joined.sum() * vox, 2),
                               added_mm3=round(added.sum() * vox, 2),
                               pieces_before=int(n_before),
                               pieces_after=int(n_after),
                               mesh_pieces=int(ncomp),
                               connector_dilations=int(grown),
                               foramina=recs)

    if all_bridged or all_dropped:
        b = np.array([x[0] for x in all_bridged]) if all_bridged else np.array([])
        d = np.array([x[0] for x in all_dropped]) if all_dropped else np.array([])
        dv = np.array([x[1] for x in all_dropped]) if all_dropped else np.array([])
        print(f"\nbridged {len(b)} islands"
              + (f", span {b.min():.2f}-{b.max():.2f} mm (mean {b.mean():.2f})" if len(b) else ""))
        print(f"dropped {len(d)} islands beyond {MAX_BRIDGE_MM} mm"
              + (f", span up to {d.max():.2f} mm, {dv.sum()} voxels total" if len(d) else ""))
    if tot_orifices:
        print(f"traced {tot_orifices} canal orifices to the apex; "
              f"{tot_merged} apical exits received more than one canal "
              f"(2:1 anatomy)")
    if n_capped:
        print(f"volume target capped by the {100 * PULP_FRACTION_MAX:.1f}% "
              f"tooth-fraction prior on {n_capped} teeth")
    if n_asserted:
        print(f"asserted a canal in {n_asserted} roots the threshold left empty "
              f"(existence: anatomical prior; route: darkest path; calibre: modelled)")
    for k in sorted(by_source):
        a = np.array(by_source[k])
        print(f"  {k:11s} n={len(a):3d}  mean {a.mean():.2f} mm  "
              f"median {np.median(a):.2f}  range {a.min():.2f}-{a.max():.2f}")
    if devs:
        d = np.array(devs)
        print(f"\n{len(d)} foramina  deviation from anatomical apex: "
              f"mean {d.mean():.2f} mm, median {np.median(d):.2f}, "
              f"range {d.min():.2f}-{d.max():.2f}")
        print(f"  literature: mean {FORAMEN_APEX_MEAN_MM} mm, range 0.2-2.0, "
              f"deviating in ~85% of teeth")
        print(f"  deviating >0.2 mm here: {100 * (d > 0.2).mean():.0f}%")
    json.dump(dict(provenance="DERIVED -- canal path from image, "
                              "apical extension and foramen placement modelled",
                   literature=dict(foramen_apex_mean_mm=FORAMEN_APEX_MEAN_MM,
                                   constriction_offset_mm=0.2,
                                   minor_diameter_mm=0.255,
                                   apical_delta_note="9.7% of teeth, median "
                                   "branch 132 um, below the 160 um voxel -- "
                                   "not modelled"),
                   teeth=report),
              open(os.path.join(outdir, "pulp-connect.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
