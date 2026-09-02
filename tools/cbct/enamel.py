#!/usr/bin/env python3
"""Enamel as a DEPTH-LIMITED SHELL on the anatomic crown, not as a threshold blob.

The first attempt thresholded density inside the tooth and kept the largest
component. The operator's reading of those sheets was that it failed in both
directions at once, and both failures are structural rather than tuning:

  CUSPS MISSING.  Enamel is THICKEST at a cusp tip (~2.5 mm), so losing cusps is
      failing where the tissue is most certain. Two causes. A cusp tip is a
      sharp convexity, so its voxels are enamel/air mixtures and partial volume
      drives them DOWN -- the densest anatomy reads faint. And taking the
      largest connected component then DELETES a cusp whose enamel joins the
      rest only through thin fissure enamel. The second was mine.
  REACHING THE PULP CHAMBER.  Coronal dentin near the DEJ is dense, so a cut
      loose enough to hold cervical enamel floods inward. Anatomically enamel
      can never approach the chamber: the DEJ is its inner boundary and the
      whole dentin thickness lies between.

So density stops being the primary instrument. The tooth's own geometry says
where enamel CAN be, and the image only chooses within that.

THE RULES, and where they come from
-----------------------------------
1. Enamel covers the ANATOMIC CROWN ONLY and stops at the CEJ. Ectopic enamel
   apical to it exists -- cervical enamel projections in 8.8-87.4% of molars
   (~45% pooled) and enamel pearls in 1.5-2.5% -- but both are furcation-region
   features. They are a named exception, not the default, and are NOT modelled.
2. It is a SHELL: bounded outside by the crown surface, inside by the DEJ.
   Thickness, therefore, is measured from the surface inward, never from a
   centreline.
3. Thickness envelope, by site (Wheeler; micro-CT and CBCT series below):
       cusp tip, molar/premolar     2.0-2.5 mm
       incisal edge                 ~2.0 mm
       mid-crown lateral face       0.6-1.4 mm, rising anterior -> posterior
       1 mm coronal to the CEJ      ~0.5 mm
       at the CEJ                   a knife edge, -> 0
   The CBCT series on maxillary central incisors (200 um voxel, comparable to
   this scan's 160) measures the gradient directly: 0.48 mm at 1 mm above the
   CEJ, 0.81 at 3 mm, 0.95 at 5 mm, 1.11 at the incisal edge. Monotone, rising
   steeply off the CEJ then flattening -- hence the sqrt profile below.
4. Enamel is the most radiopaque tissue in the body (~95% mineral against
   dentin's ~75%), so within the envelope a density cut IS the right instrument.
   It simply cannot be the ONLY one, because at 0.16 mm a 0.5 mm feather edge
   and a sharp cusp tip are both partial-volume dominated.

THE CEJ USED HERE IS NOT THE ENAMEL RAY. That would be circular -- the ray is
the thing being replaced, and its error is one-directional (CLAUDE.md 97, 102).
The crown/root divider is the CERVICAL NARROWING of the TOOTH mask, which
pulp_build.py already relies on and which lands at 0.46-0.55 of tooth length on
anteriors and 0.25-0.36 on molars, where a CEJ belongs.

KNOWN SIMPLIFICATION: the divider is one axial level, while a real CEJ scallops
mesiodistally (CLAUDE.md 96). The amplitude is ~1 mm on anteriors. Refining it
per angle is the obvious next step and is why cej_level() is separate.

Sources
  Wheeler's Dental Anatomy, Physiology and Occlusion -- 2.5 mm cusp / 2.0 mm
    incisal / 0.5 mm cervical.
  Quantitative Evaluation of Enamel Thickness in Maxillary Central Incisors...
    CBCT, PMC11592583 -- the cervical-to-incisal gradient.
  Radiographic evaluation of enamel thickness of permanent teeth, PMC11235574
    -- interproximal thickness by tooth type, 0.60-1.44 mm.
  Prevalence of cervical enamel projections / enamel pearls -- the exception.
"""
import numpy as np
from scipy import ndimage as ndi

# CEILINGS on where enamel may reach, not thickness targets: the image still
# decides what is enamel inside them. TWO of them, because the cusp figure is a
# LOCAL THICKENING AT THE TIP, not a property of that height.
#
# Applying 2.0-2.5 mm at the tip's height in every direction let enamel fill
# nearly the whole crown of a lower incisor -- which is 5 mm thick
# labiolingually, so a 2 mm allowance from each surface leaves almost no dentin.
# Its labial enamel is about 0.6 mm. So the lateral ceiling is separate, and the
# cusp/incisal allowance is added back only NEAR the tip.
#
# Lateral ceilings sit above the measured interproximal table (0.68-1.44 mm by
# type) with room to spare, since they bound rather than predict; the tip
# figures are Wheeler's.
LATERAL_MAX_MM = {"molar": 1.9, "premolar": 1.7, "canine": 1.5, "incisor": 1.3}
TIP_MAX_MM = {"molar": 2.5, "premolar": 2.5, "canine": 2.2, "incisor": 2.0}
# How fast the cusp thickening decays away from the tip, in millimetres.
TIP_SCALE_MM = 1.2
MAX_DEPTH_MM = TIP_MAX_MM        # what the tune sheet reports as the tip figure
# At the CEJ enamel is a knife edge. Two voxels, not zero, or the shell breaks
# off the crown at exactly the place the CEJ is being read from.
CEJ_DEPTH_MM = 0.32
# The outermost shell of the crown IS enamel, whatever it reads. A cusp tip is
# an enamel/air mixture and a facial surface an enamel/soft-tissue one, so both
# read below any cut that excludes dentin. Without this the tips are lost --
# which is the operator's "cusps missing", and no threshold fixes it.
SURFACE_MM = 0.24
# Within the envelope, enamel against dentin. Expressed relative to the tooth's
# own coronal dentin rather than absolutely, because dentin density varies down
# a tooth and between teeth (p50 1112-1489 across this dentition).
DENTIN_MARGIN_HU = 420.0
# ...AND IT MUST TAPER TOWARD THE CEJ, for the reason rule 9 gives for the pulp
# canal: one cut cannot hold a structure that narrows. Cervical enamel is a
# feather edge -- under ~3 voxels at 0.16 mm -- so every voxel there is an
# enamel/dentin mixture and reads far below bulk enamel. A cut that is honest
# over a cusp therefore deletes the cervical rind, which is precisely the
# one-directional error the enamel ray had (CLAUDE.md 97, 102) reappearing in a
# new method. Loosening it cervically is SAFE here in a way it never was for a
# bare threshold, because the envelope caps the damage at 0.32 mm of depth.
CEJ_MARGIN_FRAC = 0.30
RESTORATION_HU = 2600.0
# WHERE A RESTORATION SITS, ENAMEL IS GONE -- it was cut away to place the
# filling. But clearing a MARGIN around every saturated voxel was catastrophic:
# a lower incisor carries a few hundred bright voxels of attrition facet and
# contact-point artefact -- tooth 26 carries SIXTY-NINE -- and a 1.0 mm margin
# around those deleted 7-22% of the crown, taking the whole incisal edge with
# it. That is the operator's "huge sections missing like blocks cut out", and
# it was mine, not the tooth masks'.
#
# So: a restoration is a SUBSTANTIAL CONNECTED BLOB, not a bright voxel. Only
# those get a margin, and a small one, just to keep the metal's bright rim from
# reading as enamel. Scattered specks are excluded where they sit and nowhere
# else, and the smooth thickness field below carries the surface across them --
# which is honest inference over a filling, and the tooth is FLAGGED so the
# atlas says so (CLAUDE.md 86).
RESTORATION_MIN_MM3 = 2.0
RESTORATION_MARGIN_MM = 0.3
RESTORATION_FLAG_MM3 = 5.0
# Enamel is a smooth tissue and must render as one. The thickness the image
# supports is measured per surface point and then SMOOTHED OVER THE SURFACE, so
# speckle and dropouts are filled from their neighbours instead of surviving as
# jagged edges and holes. Sigma is in millimetres.
SMOOTH_MM = 0.55
# ENAMEL COVERS THE WHOLE ANATOMIC CROWN, AND THE IMAGE DOES NOT ALWAYS SHOW IT.
# On tooth 13 a contiguous 90-degree arc of the crown reads 1193-1224 HU in the
# enamel zone against 1646-2016 in every other sector of the SAME tooth -- a
# ~700 HU deficit sitting at dentin density. The mask is not at fault (its edge
# leads the tissue outside it by 496-1119 HU there, so it is on the real tooth
# boundary) and neither is the cut: at no level tried does that wall appear,
# which is why the operator could see it was cut-independent. The scan simply
# does not resolve the DEJ on that wall.
#
# Coverage of the anatomic crown is not in doubt, so this is rule 23's split:
# EXISTENCE is an anatomical prior, THICKNESS is interpolated from the measured
# surface around it, and the tooth records how much of its cap was inferred so
# the atlas can say so rather than passing it off as measurement.
INFER_GAPS = True
INFER_SMOOTH_MM = 1.8
# Below this the surface counts as carrying no reading at all. IT MUST EXCEED
# SURFACE_MM: the unconditional surface shell gives every crown point a 0.24 mm
# reading, so a floor beneath that finds no gaps anywhere and the whole step is
# a no-op -- which is exactly what it was until this was raised.
MEASURED_MIN_MM = 0.40
# Angular resolution of the scalloped CEJ. A real cervical line rises
# interproximally and dips mid-facially and mid-lingually; one flat axial level
# cannot express that, and the gingival margin is lofted from it.
N_CEJ_ANGLES = 36
CEJ_SMOOTH_BINS = 5
# Enamel thins where a fissure descends, so the profile is measured from the
# crown TIP downward. Fraction of crown height, from CEJ (0) to tip (1).
PROFILE_POWER = 0.5


def tooth_type(universal):
    """Universal number -> tooth type.

    Position is counted FROM THE MIDLINE in each quadrant (1 = central incisor,
    8 = third molar), which is the only direction that is the same in all four.
    Getting this backwards in two quadrants is exactly the class of error
    invariant 5 exists to catch, so tooth_type is checked against the manifest's
    own derivation in enamel.test.py rather than trusted.
    """
    u = int(universal)
    if 1 <= u <= 8:            # upper right, midline is 8
        idx = 9 - u
    elif 9 <= u <= 16:         # upper left, midline is 9
        idx = u - 8
    elif 17 <= u <= 24:        # lower left, midline is 24
        idx = 25 - u
    elif 25 <= u <= 32:        # lower right, midline is 25
        idx = u - 24
    else:
        raise ValueError(f"not a Universal tooth number: {universal!r}")
    return {1: "incisor", 2: "incisor", 3: "canine", 4: "premolar",
            5: "premolar", 6: "molar", 7: "molar", 8: "molar"}[idx]


def tooth_frame(solid, arch, spacing):
    """Long axis (coronal-positive) plus two cross axes, in millimetres."""
    pts = np.argwhere(solid).astype(np.float32)
    mm = pts * np.array([spacing[2], spacing[1], spacing[0]], np.float32)
    c = mm.mean(0)
    _, _, vt = np.linalg.svd(mm - c, full_matrices=False)
    ax = vt[0]
    # index axis 0 is z; coronal is -z for maxillary teeth, +z for mandibular
    if (ax[0] > 0) != (arch == "lower"):
        ax = -ax
    return c, ax, vt[1], vt[2]


def tooth_coords(solid, arch, spacing):
    """Per-voxel (t, angle, r) in the tooth's own frame. t is coronal-positive."""
    c, ax, e2, e3 = tooth_frame(solid, arch, spacing)
    zz, yy, xx = np.nonzero(solid)
    mm = np.stack([zz * spacing[2], yy * spacing[1], xx * spacing[0]], 1) - c
    t = mm @ ax
    u, w = mm @ e2, mm @ e3
    return (zz, yy, xx), t, np.arctan2(w, u), np.hypot(u, w)


def cej_ring(solid, arch, spacing, cervical_frac=0.80, max_crown_frac=0.45):
    """The CEJ as a SCALLOPED ring: cervical height per angle around the tooth.

    A cervical line rises interproximally and dips mid-facially and
    mid-lingually (CLAUDE.md 96), so one flat axial level is wrong by the
    scallop amplitude -- about a millimetre on an anterior, which is most of the
    cervical enamel it is supposed to bound. Per angle, walk apically from that
    angle's widest point to where its radius falls below `cervical_frac` of it.

    Derived from the TOOTH mask only. Using the enamel ray would be circular:
    it is the thing being replaced, and its error is one-directional
    (CLAUDE.md 97, 102). This ring is therefore also an honest anchor for the
    gingival margin, which is what rule 102 says that fix needs.

    Returns (angles, cej_t, t_tip, per-voxel arrays), all in millimetres.
    """
    idx, t, ang, r = tooth_coords(solid, arch, spacing)
    t_tip = float(np.percentile(t, 99.5))
    edges = np.linspace(-np.pi, np.pi, N_CEJ_ANGLES + 1)
    centres = 0.5 * (edges[:-1] + edges[1:])
    which = np.clip(np.digitize(ang, edges) - 1, 0, N_CEJ_ANGLES - 1)
    t_floor = float(np.percentile(t, 0.5))
    cap_t = t_tip - max_crown_frac * (t_tip - t_floor)
    cej = np.full(N_CEJ_ANGLES, np.nan, np.float32)
    nbins = 40
    for k in range(N_CEJ_ANGLES):
        sel = which == k
        if sel.sum() < 40:
            continue
        tk, rk = t[sel], r[sel]
        lo, hi = tk.min(), tk.max()
        if hi - lo < 1e-3:
            continue
        b = np.clip(((tk - lo) / (hi - lo) * (nbins - 1)).astype(int), 0, nbins - 1)
        # 90th percentile radius per height band: robust to a stray voxel
        prof = np.full(nbins, np.nan)
        for j in range(nbins):
            m = b == j
            if m.sum() >= 3:
                prof[j] = np.percentile(rk[m], 90)
        good = ~np.isnan(prof)
        if good.sum() < 6:
            continue
        heights = lo + (hi - lo) * np.arange(nbins) / (nbins - 1)
        pj, hj = prof[good], heights[good]
        order = np.argsort(-hj)                     # crown -> apex
        pj, hj = pj[order], hj[order]
        # START AT THE WIDEST POINT, not at the tip. A crown narrows toward its
        # cusp or incisal edge, so a walk beginning at the tip meets "radius
        # below 0.80 of the maximum" on its first step and puts the CEJ within a
        # millimetre of the tip -- tooth 8 came out with a 0.69 mm crown. The
        # flat-level reading always started at the widest slice; going per angle
        # dropped that and nothing about the output looked obviously wrong until
        # the enamel volume collapsed.
        imax = int(np.nanargmax(pj))
        rmax = float(pj[imax])
        hit = None
        for j in range(imax, len(pj)):
            if pj[j] < cervical_frac * rmax:
                hit = hj[j]
                break
        cej[k] = cap_t if hit is None else max(float(hit), cap_t)
    if np.all(np.isnan(cej)):
        return None
    # fill gaps and smooth AROUND the ring -- it is periodic, and a cervical
    # line is smooth; a per-angle reading is not
    nan = np.isnan(cej)
    if nan.any():
        good = ~nan
        cej[nan] = np.interp(centres[nan], centres[good], cej[good], period=2 * np.pi)
    pad = CEJ_SMOOTH_BINS
    wrapped = np.concatenate([cej[-pad:], cej, cej[:pad]])
    kern = np.ones(2 * pad + 1) / (2 * pad + 1)
    cej = np.convolve(wrapped, kern, mode="same")[pad:-pad]
    return centres, cej, t_tip, idx, t, ang


def cej_level(solid, arch, cervical_frac=0.80, max_crown_frac=0.45):
    """Flat-level CEJ, kept for callers that want a single axial index.

    The scalloped ring in cej_ring() is what the envelope actually uses; this
    reports its mean as a z index, for reporting and for the tune sheet's
    reference line.
    """
    tz = np.where(solid.any(axis=(1, 2)))[0]
    if tz.size < 4:
        return None, None
    zz = tz if arch == "upper" else tz[::-1]
    area = np.array([int(solid[k].sum()) for k in zz])
    imax = int(np.argmax(area))
    cap = min(int(max_crown_frac * len(area)), len(area) - 1)
    hit = cap
    for i in range(imax, len(area)):
        if area[i] < cervical_frac * area.max():
            hit = min(i, cap)
            break
    return int(zz[hit]), int(zz[0])


def envelope(solid, arch, universal, spacing):
    """Depth from the surface that enamel may occupy, per voxel, in millimetres.

    Zero apical to the SCALLOPED CEJ (rule 1); a knife edge at it; rising to the
    tooth type's maximum at the crown tip on the sqrt profile fitted to the CBCT
    gradient (rule 3).
    """
    ring = cej_ring(solid, arch, spacing)
    z_cej, z_tip = cej_level(solid, arch)
    if ring is None:
        return np.zeros(solid.shape, np.float32), z_cej, z_tip, None
    centres, cej, t_tip, idx, t, ang = ring
    cej_at = np.interp(ang, centres, cej, period=2 * np.pi)
    span = np.maximum(t_tip - cej_at, 1e-3)
    h = np.clip((t - cej_at) / span, 0.0, 1.0)
    ttype = tooth_type(universal)
    lat, tip = LATERAL_MAX_MM[ttype], TIP_MAX_MM[ttype]
    # lateral profile: sqrt in height above the CEJ, which is what the CBCT
    # gradient measures (0.48 / 0.81 / 0.95 mm at 1 / 3 / 5 mm)
    prof = CEJ_DEPTH_MM + (lat - CEJ_DEPTH_MM) * np.power(h, PROFILE_POWER)
    # the cusp cap, added back only near the tip
    d_tip = np.maximum(t_tip - t, 0.0)
    prof = prof + (tip - lat) * np.exp(-(d_tip / TIP_SCALE_MM) ** 2)
    prof[t <= cej_at] = 0.0                  # nothing apical to the CEJ
    env = np.zeros(solid.shape, np.float32)
    env[idx] = prof
    return env, z_cej, z_tip, (centres, cej, t_tip)


def dentin_reference(sub, solid, env, spacing):
    """Coronal dentin density for this tooth: the crown's core.

    Taken deep to the envelope so it cannot be contaminated by the enamel it is
    used to separate.
    """
    depth = ndi.distance_transform_edt(solid, sampling=tuple(spacing))
    crown = solid & (env > 0)
    if not crown.any():
        return float(np.percentile(sub[solid], 50))
    grown = ndi.binary_dilation(crown, np.ones((3, 3, 3)), iterations=2) & solid
    core = grown & (depth > 2.6) & (sub < RESTORATION_HU)
    if core.sum() < 50:
        core = grown & (depth > 1.2) & (sub < RESTORATION_HU)
    if core.sum() < 20:
        return float(np.percentile(sub[solid], 50))
    return float(np.percentile(sub[core], 60))


def restorations(sub, solid, spacing):
    """Saturated material that is really a restoration, and its exclusion zone.

    A restoration is a SUBSTANTIAL CONNECTED BLOB. Treating every bright voxel
    as one, and clearing a millimetre around it, deleted up to 22% of a lower
    incisor's crown -- see RESTORATION_MIN_MM3.
    """
    vox = float(np.prod(spacing))
    metal = solid & (sub >= RESTORATION_HU)
    total = float(metal.sum()) * vox
    free = np.ones_like(solid)
    if not metal.any():
        return metal, free, total
    lab, n = ndi.label(metal, structure=np.ones((3, 3, 3)))
    if n:
        sizes = ndi.sum(metal, lab, range(1, n + 1)) * vox
        big = np.isin(lab, [i + 1 for i, sz in enumerate(sizes)
                            if sz >= RESTORATION_MIN_MM3])
        if big.any():
            free = ndi.distance_transform_edt(
                ~big, sampling=tuple(spacing)) >= RESTORATION_MARGIN_MM
    return metal, free, total


def smooth_shell(raw, spacing, sigma_mm=SMOOTH_MM):
    """Smooth the enamel boundary by smoothing its SIGNED DISTANCE, not the mask.

    This is rule 93's recipe, which this pipeline already relies on for the
    hand-traced pulp: blurring a binary mask erodes thin structure and shifts
    the boundary inward, while smoothing the distance field the mask defines
    turns every step into a taper and leaves the surface where it was. It also
    closes single-voxel dropouts and deletes speckle for free, because an
    isolated voxel's signed distance is outweighed by the space around it.

    Two things were tried first and both failed, so they are recorded rather
    than repeated. Measuring a THICKNESS per surface point and smoothing that
    over the surface under-read by about half: thickness had to be read as
    either the deepest enamel in a column (which one speckle voxel sets) or the
    contiguous run from the surface (which one stray dentin voxel cuts short),
    and smoothing a peaked non-negative field across a folded surface -- an
    embrasure folds the shell back within a sigma of itself -- biases it down
    again. Interproximal enamel came out 0.54 mm below the published table
    where the unsmoothed mask had been 0.07 mm below it.
    """
    sig = [sigma_mm / float(spacing[2 - i]) for i in range(3)]
    inside = ndi.distance_transform_edt(raw, sampling=tuple(spacing))
    outside = ndi.distance_transform_edt(~raw, sampling=tuple(spacing))
    sd = outside - inside                     # negative inside the enamel
    return ndi.gaussian_filter(sd, sig, mode="nearest")


def infer_gaps(raw, solid, env, depth, spacing, metal, free):
    """Fill crown surface the scan could not resolve, by interpolating thickness.

    Enamel covers the anatomic crown; where a whole arc of it fails to separate
    from dentin, drawing bare dentin at the surface asserts something the
    anatomy rules out, and it renders as a wall cleanly cut out of the cap.
    So thickness is read per surface point where it IS resolved, inpainted
    across the gaps by a normalised Gaussian over the surface, and rasterised
    within the envelope.

    The interpolation RAISES a locally thin reading to its neighbourhood, it
    does not merely fill holes. Filling only where the reading was zero barely
    moved the dark arc (41 -> 46% of the envelope band), because the failure is
    patchy: most columns there return a thin reading rather than none. Enamel
    thickness varies smoothly across a crown, so a column reading far below the
    surface around it is an imaging failure, not a local thinning.

    It can only ever ADD, and the envelope still bounds it -- so the cervical
    feather edge is protected by geometry (0.32 mm at the CEJ) no matter what
    the neighbourhood says, and the result cannot exceed the published
    thickness ceiling anywhere.
    """
    vox = float(np.prod(spacing))
    crown = solid & (env > 0)
    if not crown.any():
        return raw, 0.0
    _, inds = ndi.distance_transform_edt(solid, sampling=tuple(spacing),
                                         return_indices=True)
    nb = np.ravel_multi_index((inds[0].ravel(), inds[1].ravel(),
                               inds[2].ravel()), solid.shape)
    n = solid.size
    # thickness where it was measured: the contiguous run in from the surface
    reach = np.zeros(n, np.float32)
    np.maximum.at(reach, nb[raw.ravel()], depth.ravel()[raw.ravel()])
    # which surface points belong to the CROWN at all
    oncrown = np.zeros(n, bool)
    oncrown[np.unique(nb[crown.ravel()])] = True
    have = oncrown & (reach >= MEASURED_MIN_MM)
    if not have.any() or have.all():
        return raw, 0.0
    T = reach.reshape(solid.shape) * have.reshape(solid.shape)
    M = have.reshape(solid.shape).astype(np.float32)
    sig = [INFER_SMOOTH_MM / float(spacing[2 - i]) for i in range(3)]
    num = ndi.gaussian_filter(T, sig, mode="nearest")
    den = ndi.gaussian_filter(M, sig, mode="nearest")
    filled = np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0)
    # take the neighbourhood value wherever it exceeds what was measured
    t_use = np.maximum(filled, reach.reshape(solid.shape))
    t_use = np.where(oncrown.reshape(solid.shape), t_use, 0.0)
    t_at = t_use.ravel()[nb].reshape(solid.shape)
    # NEVER INFER ENAMEL ONTO A RESTORATION. Without this the crowned molars
    # 19 and 30 had enamel painted back under their zirconia, where it was
    # prepared away -- the inferred volume came out larger than the cap itself.
    add = crown & (depth <= np.minimum(t_at, env)) & ~raw & ~metal & free
    return raw | add, float(add.sum()) * vox


def outer_depth(solid, neighbours, spacing):
    """Depth from the tooth's TRUE OUTER SURFACE, ignoring the arch-split cut.

    The arch is split BY ARC POSITION (CLAUDE.md 5), so each tooth's mask ends
    in a FLAT PLANE at its mesial and distal contacts. That plane is not a tooth
    surface -- it is where the neighbour begins, and at a contact the two
    crowns' enamel is one contiguous bright mass that the split divides
    arbitrarily.

    Treating it as surface is what produced the straight, axis-aligned blocks
    the operator kept reporting: depth measured from an internal cut face is
    small, so the envelope opens there and the surface shell paints a veneer
    across it, and where the plane falls inside the real enamel the cap ends in
    a clean straight edge instead of carrying on round the tooth.

    Every earlier test missed this because the tissue beyond the plane carries
    the NEIGHBOUR's label -- so it is neither orphaned, nor unlabelled, nor
    outside any mask, and four separate measurements all scored it as fine.

    Distances are therefore measured against solid UNION its neighbours, so the
    contact face is interior and only the real outer surface bounds the tooth.
    """
    both = solid | neighbours if neighbours is not None else solid
    return ndi.distance_transform_edt(both, sampling=tuple(spacing))


def enamel_mask(sub, solid, arch, universal, spacing, margin_hu=DENTIN_MARGIN_HU,
                neighbours=None):
    """The enamel shell for one tooth, as a smooth thickness field.

    Three claims, kept apart:
      WHERE IT MAY BE      the envelope -- anatomy, from published thickness.
      HOW THICK IT IS      measured from the image inside that envelope.
      WHAT IS DRAWN        that thickness smoothed over the crown surface, so
                           the result is a tissue and not a threshold artefact.
    """
    env, z_cej, z_tip, ring = envelope(solid, arch, universal, spacing)
    meta = dict(cej_z=z_cej, tip_z=z_tip, type=tooth_type(universal),
                max_depth_mm=MAX_DEPTH_MM[tooth_type(universal)])
    if not (env > 0).any():
        return np.zeros_like(solid), meta
    depth = outer_depth(solid, neighbours, spacing)
    within = solid & (depth <= env) & (env > 0)
    ref = dentin_reference(sub, solid, env, spacing)
    metal, free, rest_mm3 = restorations(sub, solid, spacing)
    # the cut tapers with the enamel, on the envelope's own profile
    mx = TIP_MAX_MM[tooth_type(universal)]
    h = np.clip((env - CEJ_DEPTH_MM) / max(mx - CEJ_DEPTH_MM, 1e-6), 0.0, 1.0)
    frac = CEJ_MARGIN_FRAC + (1.0 - CEJ_MARGIN_FRAC) * h
    dense = sub >= (ref + margin_hu * frac)
    shell = depth <= SURFACE_MM
    raw = within & (dense | shell) & ~metal & free
    inferred_mm3 = 0.0
    if INFER_GAPS:
        raw, inferred_mm3 = infer_gaps(raw, solid, env, depth, spacing,
                                       metal, free)
    field = smooth_shell(raw, spacing)
    cap = solid & (env > 0) & (depth <= env) & (field <= 0.0) & ~metal
    # the smoothed boundary may retreat from the crown surface by a fraction of
    # a voxel; the outermost shell of the crown is enamel by definition, so put
    # it back rather than shipping a cap with the surface shaved off it
    cap |= solid & (env > 0) & (depth <= SURFACE_MM) & ~metal & free
    if cap.any():
        face = ndi.generate_binary_structure(3, 1)
        lab, n = ndi.label(cap, structure=face)
        if n > 1:
            sz = ndi.sum(cap, lab, range(1, n + 1))
            cap = lab == (int(np.argmax(sz)) + 1)
    meta.update(inferred_mm3=round(inferred_mm3, 2),
                dentin_ref=round(ref, 1), cut=round(ref + margin_hu, 1),
                restoration_mm3=round(rest_mm3, 2),
                obscured=bool(rest_mm3 > RESTORATION_FLAG_MM3),
                scalloped_cej=ring is not None,
                cej_scallop_mm=(round(float(ring[1].max() - ring[1].min()), 2)
                                if ring is not None else None))
    return cap, meta
