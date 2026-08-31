#!/usr/bin/env python3
"""Generate gingiva from the measured CEJ and alveolar crest.

DERIVED, not measured. Gingiva is invisible in this scan -- soft tissue forms a
single unimodal distribution around 195 HU with no boundary to find
(docs/phase-3-soft-tissue.md). What makes this patient-specific rather than a
generic mesh is that its *form* is dictated by hard tissue that IS measured: the
free gingival margin follows the cementoenamel junction, and the attached gingiva
drapes the alveolar bone.

The CEJ is trustworthy. Detected enamel extent matches published crown heights to
within 0.6 mm across the anterior and molar teeth, which is the check that
matters, because the CEJ is where the enamel cap ends.

The alveolar crest is NOT trustworthy, and no crest-derived number is used here.
Two methods disagreed by 8 mm in opposite directions -- a wide angular sector
catches bone that belongs to neighbouring teeth, and a tight shell around the
tooth catches the neighbours' crowns instead. **No claim about bone level should
be made from this pipeline**, and in particular the 4.5 mm CEJ-to-crest figure an
earlier draft produced is an artefact, not periodontitis.

Built as a COLLAR, not as a shell over bone. An earlier version took "everything
within 1.1 mm outside the bone, inside a coronal-apical band", which fails for a
structural reason: the alveolar ridge is roughly horizontal on top, so that shell
is a flat sheet there and the result reads as a plate. Real gingiva hugs the
buccal and lingual *walls* of the alveolar process and closes interdentally as
papillae.

So each tooth gets a sleeve swept along its own surface, from the margin ring
(CEJ + 1 mm, measured) down to an apical ring below the crest (measured). The
collars are then closed together across the interdental gaps, which is what forms
the papillae -- they appear on their own, because adjacent collars nearly touch
at the contact point and are far apart lower down.

Usage: python3 tools/cbct/gingiva.py <volume.nrrd> <split-dir> <pred.nii.gz>
                                     <landmarks.json> <out-dir>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import marching_cubes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from read_nifti import read_nifti
from segment_tooth import write_binary_stl

SULCUS_FACIAL_MM = 1.0        # healthy probing depth mid-facial and mid-lingual
SULCUS_PROXIMAL_MM = 2.0      # healthy probing depth interproximally (the col)
MARGIN_ABOVE_CEJ_MM = SULCUS_FACIAL_MM      # kept for the report/margin_points
THICKNESS_MM = 1.1            # gingival thickness on the tooth and bone
MGJ_BELOW_CREST_MM = 4.0      # mucogingival junction, apical to the measured crest
PAPILLA_CLOSE_MM = 1.8        # closes the interdental gap between adjacent collars
SCALLOP_TOL_MM = 1.0          # how far a measured aspect may sit off the scallop

# Curvature of the cervical line, mesial and distal, in mm (Wheeler). This is
# the rise of the CEJ from its mid-facial (equally, mid-lingual) low point to
# its interproximal high point, and it is the ONLY thing that bounds how tall a
# papilla may be. Posterior teeth are nearly flat distally.
CERVICAL_CURVATURE = {
    "u-central": (3.5, 2.5), "u-lateral": (3.0, 2.0), "u-canine": (2.5, 1.5),
    "l-central": (3.0, 2.0), "l-lateral": (3.0, 2.0), "l-canine": (2.5, 1.0),
    "premolar":  (1.0, 0.0), "molar":     (1.0, 0.0),
}
# Crown height, cusp/incisal tip to the mid-facial CEJ, in mm (Wheeler). This is
# the anchor the vote needs: it says where the CEJ must be WITHOUT reference to
# any aspect of the ring, so a wrong plateau covering more than half the ring
# cannot carry the fit. gingiva.py's own docstring already leans on this figure
# -- detected enamel extent matches it to within 0.6 mm on the teeth that work.
CROWN_HEIGHT = {
    "u-central": 10.5, "u-lateral": 9.0, "u-canine": 10.0,
    "l-central": 9.0, "l-lateral": 9.5, "l-canine": 11.0,
    "premolar": 8.5, "molar": 7.3,
}
# Lowers the molar gingival margin. The margin is uniformly ~2.3 mm too coronal
# across the WHOLE arch -- the anchor's calibration constant is measured from the
# same enamel ray whose error is one-directional (losing thin cervical enamel can
# only read the CEJ too high, and cervical enamel is thin on every tooth), so it
# partly measures the error rather than an artefact. It shows up on the molars
# first because their crowns are shortest: the same 2.3 mm is 37% of a 6.3 mm
# molar crown and 23% of a 10 mm canine. The anteriors are accepted as they
# stand, so only the molars are moved. PROVISIONAL -- the full correction is
# 2.3 mm and the honest fix is to stop calibrating the constant off the ray.
MOLAR_MARGIN_DROP_MM = 1.5
# How far the baseline may sit off the crown-height anchor. Set from the
# anchor's own dispersion, not by taste: across the 17 rings that fit a scallop
# unaided the anchor's residual has sigma 0.44 mm and a 95th percentile of
# 1.17 mm, so 1.5 mm is 3.4 sigma. Anything looser lets a wrong plateau stand
# (teeth 20 and 29 rode a 2.2 mm offset through a 2.5 mm tolerance).
CROWN_TOL_MM = 1.5
CENTRAL, LATERAL, CANINE = {8, 9, 24, 25}, {7, 10, 23, 26}, {6, 11, 22, 27}
PREMOLAR = {4, 5, 12, 13, 20, 21, 28, 29}


def tooth_type(u):
    if u in CENTRAL:
        return ("u-" if u < 17 else "l-") + "central"
    if u in LATERAL:
        return ("u-" if u < 17 else "l-") + "lateral"
    if u in CANINE:
        return ("u-" if u < 17 else "l-") + "canine"
    return "premolar" if u in PREMOLAR else "molar"


def mesial_neighbour(u):
    """The tooth one step toward the midline, in Universal numbering."""
    return u + 1 if u <= 8 or 17 <= u <= 24 else u - 1


def orient(lm, v):
    """Facial angle and mesial side for each tooth, in its own (e2, e3) frame.

    Both come from geometry, not from a table: facial is away from the arch
    centroid, mesial is toward the neighbour one step nearer the midline. A
    hand-typed list of which aspect is which is 28 chances to face a tooth the
    wrong way, the same argument that keeps the notation derived in manifest.mjs.
    """
    def wpt(m, idx):
        return np.array(v.world(idx[2], idx[1], idx[0]))

    cen, out = {}, {}
    for arch in ("upper", "lower"):
        pts = [wpt(m, m["centre_index"]) for m in lm.values() if m["arch"] == arch]
        cen[arch] = np.mean(pts, axis=0)
    by_u = {m["universal"]: k for k, m in lm.items()}
    for k, m in lm.items():
        c = np.array(m["centre_index"], float)
        here = wpt(m, c)
        d2 = wpt(m, c + np.array(m["e2"], float)) - here
        d3 = wpt(m, c + np.array(m["e3"], float)) - here
        ang = lambda w: float(np.degrees(np.arctan2(w @ d3, w @ d2)))

        away = here - cen[m["arch"]]
        away[2] = 0.0                       # the arch is a curve in the axial plane
        facial = ang(away)

        nb = by_u.get(mesial_neighbour(m["universal"]))
        if nb is None:                      # no mesial neighbour: assume symmetry
            mes_sign = 1.0
        else:
            toward = wpt(lm[nb], np.array(lm[nb]["centre_index"], float)) - here
            toward[2] = 0.0
            mes_sign = np.sign((ang(toward) - facial + 180) % 360 - 180) or 1.0
        out[k] = (facial, float(mes_sign))
    return out


def scallop(angles, cej, facial, mes_sign, amp_m, amp_d, anchor=None):
    """Force a measured CEJ ring onto an anatomically possible scallop.

    The cervical line has exactly two low points -- mid-facial and mid-lingual --
    and rises to a maximum mesially and distally. Its amplitude is the published
    cervical-line curvature for that tooth. So the model has ONE free parameter,
    the baseline, and the shape is fixed; fitting it robustly is what lets a
    contiguous run of wrong aspects be outvoted rather than averaged in.

    The fit is a consensus vote (every aspect proposes a baseline, the baseline
    with the most aspects within tolerance wins) because the failures here are
    PLATEAUX, not scatter: teeth 22 and 27 read 8.1-8.9 mm across their whole
    lingual half. A median or a percentile is dragged by a run that wide; a vote
    is not. Ties go to the lower baseline -- of two readings of the same tooth,
    the more apical CEJ is the one that did not lose thin enamel to the
    threshold.

    An aspect inside the tolerance keeps its measured value, so real per-patient
    detail survives. Outside it, the model stands in. Nothing may sit ABOVE the
    model, ever: that is the ceiling the whole exercise is for.
    """
    a = np.asarray(angles, float)
    x = np.asarray(cej, float)
    rel = (a - facial + 180.0) % 360.0 - 180.0
    amp = np.where(np.sign(rel) == mes_sign, amp_m, amp_d)
    rise = amp * np.sin(np.radians(rel)) ** 2

    resid = x - rise
    cand = resid
    if anchor is not None:
        near = resid[np.abs(resid - anchor) <= CROWN_TOL_MM]
        cand = near if len(near) else np.array([anchor])
    best_b, best_n = float(np.median(cand)), -1
    for b in cand:                           # every admissible aspect proposes one
        n = int((np.abs(resid - b) <= SCALLOP_TOL_MM).sum())
        if n > best_n or (n == best_n and b < best_b):
            best_b, best_n = float(b), n
    keep = np.abs(resid - best_b) <= SCALLOP_TOL_MM
    if keep.sum() >= 4:
        best_b = float(np.median(resid[keep]))
        if anchor is not None:
            best_b = float(np.clip(best_b, anchor - CROWN_TOL_MM,
                                   anchor + CROWN_TOL_MM))
        keep = np.abs(x - (best_b + rise)) <= SCALLOP_TOL_MM

    model = best_b + rise
    return np.where(keep, np.minimum(x, model), model), int(keep.sum()), best_b
N_ANGLES = 24                 # aspects the CEJ and crest were MEASURED at
N_SWEEP = 72                  # aspects the collar is SWEPT at, interpolated
BONE = {"upper": 1, "lower": 2}


def margin_points(lm, v):
    """Free gingival margin as world points, per tooth, from the measured CEJ."""
    out = {}
    for key, m in lm.items():
        c = np.array(m["centre_index"], float)
        ax = np.array(m["axis"], float)
        e2 = np.array(m["e2"], float)
        e3 = np.array(m["e3"], float)
        pts = []
        for ang, cej in zip(m["angles"], m["cej_mm"]):
            if cej is None:
                continue
            a = np.radians(ang)
            # radius: take it from the tooth's own cross-section at the CEJ.
            # 4 mm is a reasonable cervical radius and the margin is redrawn onto
            # the tooth surface later, so precision here is not critical.
            r = 4.0 / 0.16
            t = (cej + MARGIN_ABOVE_CEJ_MM) / 0.16
            idx = c + t * ax + r * (np.cos(a) * e2 + np.sin(a) * e3)
            pts.append(v.world(idx[2], idx[1], idx[0]))
        if pts:
            out[key] = dict(points=np.array(pts), arch=m["arch"],
                            universal=m["universal"], fma=m["fma"])
    return out


def sleeve(tooth, frame, cej_by_angle, crest_by_angle, spacing, shape,
           facial=0.0):
    """A gingival collar hugging one tooth, from the margin ring to below the crest."""
    c = np.array(frame["centre_index"], float)
    ax = np.array(frame["axis"], float)
    e2 = np.array(frame["e2"], float)
    e3 = np.array(frame["e3"], float)
    pts = np.argwhere(tooth).astype(float) - c
    t_all = pts @ ax
    u, w = pts @ e2, pts @ e3
    r_all = np.hypot(u, w)
    ang_all = np.degrees(np.arctan2(w, u))

    out = np.zeros(shape, bool)
    thick = THICKNESS_MM / spacing

    # Interpolate the measured rings onto a finer sweep. The CEJ and crest are
    # measured at 24 aspects, but sweeping the collar at 24 gives a scallop made
    # of 15-degree facets -- it steps around the tooth instead of curving around
    # it, and the interproximal rise and mid-facial dip both read as stairs.
    # Both curves are periodic in angle, so they interpolate cleanly.
    meas = 360.0 / N_ANGLES
    ks = sorted(cej_by_angle)
    if len(ks) < 6:
        return out
    ang_meas = np.array([-180 + k * meas + meas / 2 for k in ks])
    cej_meas = np.array([cej_by_angle[k] for k in ks])
    crest_meas = np.array([crest_by_angle.get(k, cej_by_angle[k] - 2.0) for k in ks])
    wrap_a = np.concatenate([ang_meas - 360, ang_meas, ang_meas + 360])
    wrap_c = np.tile(cej_meas, 3)
    wrap_r = np.tile(crest_meas, 3)
    step = 360.0 / N_SWEEP
    for k in range(N_SWEEP):
        a_mid_deg = -180 + k * step + step / 2
        cej = float(np.interp(a_mid_deg, wrap_a, wrap_c))
        crest = float(np.interp(a_mid_deg, wrap_a, wrap_r))
        # The margin sits one healthy sulcus coronal to the CEJ, and a healthy
        # sulcus is deeper interproximally (the col) than at the mid-facial and
        # mid-lingual. Both ends stay inside the 1-2 mm the operator specified.
        s2 = np.sin(np.radians(a_mid_deg - facial)) ** 2
        sulcus = SULCUS_FACIAL_MM + (SULCUS_PROXIMAL_MM - SULCUS_FACIAL_MM) * s2
        top = (cej + sulcus) / spacing
        base = (crest - MGJ_BELOW_CREST_MM) / spacing
        if base >= top:
            continue
        sel = (ang_all >= a_mid_deg - meas) & (ang_all < a_mid_deg + meas)
        if sel.sum() < 20:
            continue
        a_mid = np.radians(a_mid_deg)
        dirv = np.cos(a_mid) * e2 + np.sin(a_mid) * e3
        for t in np.arange(base, top, 0.45):
            near = sel & (np.abs(t_all - t) < 2.0)
            r_surf = (float(np.percentile(r_all[near], 92)) if near.sum() > 8
                      else float(np.percentile(r_all[sel], 92)))
            for rr in np.arange(r_surf - 0.5, r_surf + thick, 0.45):
                for da in (-step / 2, 0.0, step / 2):
                    d2 = (np.cos(a_mid + np.radians(da)) * e2
                          + np.sin(a_mid + np.radians(da)) * e3)
                    p = c + t * ax + rr * d2
                    iz, iy, ix = (int(round(p[0])), int(round(p[1])),
                                  int(round(p[2])))
                    if (0 <= iz < shape[0] and 0 <= iy < shape[1]
                            and 0 <= ix < shape[2]):
                        out[iz, iy, ix] = True
    return out


def main():
    vol_path, split_dir, pred_path, lm_path, crest_path, outdir = sys.argv[1:7]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    lab, _, _ = read_nifti(pred_path)
    lm = json.load(open(lm_path))
    crest = json.load(open(crest_path))
    sp = float(v.spacing[0])

    upper = np.load(os.path.join(split_dir, "upper_labels.npy"))
    lower = np.load(os.path.join(split_dir, "lower_labels.npy"))
    teeth = (upper > 0) | (lower > 0)

    tlabel = {}
    for arch, arr in (("upper", upper), ("lower", lower)):
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        for key, m in lm.items():
            if m["arch"] != arch:
                continue
            c = np.array(m["centre_index"], float)
            tlabel[key] = min(ids, key=lambda s2:
                              np.linalg.norm(np.array(cents[s2 - 1]) - c))

    # CORRECT THE MEASURED CEJ -- everything downstream is a loft off it.
    # The enamel ray under-reads thin lingual enamel on the mandibular anteriors
    # (it returns the most apical voxel it still calls enamel, which is up in the
    # incisal third once cervical enamel falls under threshold) and over-reads
    # where a restoration or the alveolar plate is caught instead. Both produce a
    # flat PLATEAU of wrong aspects, which is why the ring is refitted rather
    # than smoothed -- a median or a percentile is dragged by a run that wide.
    facing = orient(lm, v)
    raw, anchor0 = {}, {}
    for key, m in lm.items():
        old_c = np.array([np.nan if c is None else c for c in m["cej_mm"]], float)
        if np.isnan(old_c).all():
            continue
        raw[key] = np.where(np.isnan(old_c), np.nanmedian(old_c), old_c)
        arr = upper if m["arch"] == "upper" else lower
        pts = np.argwhere(arr == tlabel[key]).astype(np.float32)
        t = (pts - np.array(m["centre_index"], float)) @ np.array(m["axis"], float)
        anchor0[key] = (float(np.percentile(t, 99.5)) * sp
                        - CROWN_HEIGHT[tooth_type(m["universal"])])

    # Calibrate the anchor's CONSTANT against this patient. Crown height places
    # the CEJ correctly RELATIVE to the cusp tip, but the tip is a percentile of
    # a segmentation and the axis is a principal direction, so the pair carries a
    # fixed bias -- here 1.5 mm, and near-identical on every tooth. Teeth whose
    # ring already fits a scallop unaided calibrate it; the rest inherit it. What
    # the table is trusted for is the DIFFERENCE between an incisor and a molar,
    # which is what no measurement on a broken tooth can supply.
    fit0 = {k: scallop(lm[k]["angles"], raw[k], facing[k][0], facing[k][1],
                       *CERVICAL_CURVATURE[tooth_type(lm[k]["universal"])])
            for k in raw}
    clean = [fit0[k][2] - anchor0[k] for k in raw if fit0[k][1] >= 18]
    bias = float(np.median(clean)) if len(clean) >= 6 else 0.0
    print(f"crown-height anchor bias {bias:+.2f} mm from {len(clean)} clean rings\n")

    print(f"{'U':>3} {'arch':<6} {'type':<10} {'facial':>7} {'lingual':>8} "
          f"{'anchor':>7} {'->fac':>7} {'->ling':>7} {'kept':>5} {'drop':>6}")
    fixed = {}
    for key, m in sorted(lm.items(), key=lambda kv: kv[1]["universal"]):
        if key not in raw:
            continue
        u, (facial, mes) = m["universal"], facing[key]
        amp_m, amp_d = CERVICAL_CURVATURE[tooth_type(u)]
        old_c = raw[key]
        anchor = anchor0[key] + bias
        new_c, kept, _ = scallop(m["angles"], old_c, facial, mes, amp_m, amp_d,
                                 anchor=anchor)
        if tooth_type(u) == "molar":
            # A straight apical shift, not an anchor tweak: moving the anchor
            # only recentres the window the fit may land in, and on 6 of the 8
            # molars the consensus baseline was already inside it, so nothing
            # moved. The margin is what is too coronal, so shift the ring.
            new_c = new_c - MOLAR_MARGIN_DROP_MM
        m["cej_mm"] = [round(float(x), 2) for x in new_c]
        m["cej_source"] = "scalloped"
        rel = (np.array(m["angles"], float) - facial + 180.0) % 360.0 - 180.0
        f_i, l_i = int(np.abs(rel).argmin()), int(np.abs(np.abs(rel) - 180).argmin())
        print(f"{u:>3} {m['arch']:<6} {tooth_type(u):<10} {old_c[f_i]:7.2f} "
              f"{old_c[l_i]:8.2f} {anchor:7.2f} {new_c[f_i]:7.2f} "
              f"{new_c[l_i]:7.2f} {kept:>3}/24 {old_c.max() - new_c.max():6.2f}")
        fixed[key] = float(old_c.max() - new_c.max())
    if fixed:
        print(f"    CEJ lowered by up to {max(fixed.values()):.2f} mm; "
              f"{sum(1 for x in fixed.values() if x > 1.0)} teeth moved > 1 mm\n")

    report = dict(provenance="DERIVED from the measured CEJ and alveolar crest. "
                             "Gingiva is not visible in CBCT.",
                  models="health -- no recession, no inflammation, average biotype",
                  construction="per-tooth collar lofted from the margin ring to "
                               "below the crest, closed interdentally into papillae",
                  sulcus_mm=dict(facial=SULCUS_FACIAL_MM,
                                 proximal=SULCUS_PROXIMAL_MM),
                  cej="measured, then refitted to the published cervical-line "
                      "curvature; the enamel ray under-reads thin lingual enamel",
                  margin_above_cej_mm=MARGIN_ABOVE_CEJ_MM,
                  mgj_below_crest_mm=MGJ_BELOW_CREST_MM,
                  thickness_mm=THICKNESS_MM, arches={})

    for arch, arr in (("upper", upper), ("lower", lower)):
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        acc = np.zeros(arr.shape, bool)
        n_teeth = 0
        for key, m in lm.items():
            if m["arch"] != arch:
                continue
            c = np.array(m["centre_index"], float)
            best = min(ids, key=lambda s: np.linalg.norm(np.array(cents[s - 1]) - c))
            box = boxes[best - 1]
            pad = 46
            sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                       for b, n in zip(box, arr.shape))
            tsub = np.zeros(tuple(x.stop - x.start for x in sl), bool)
            tsub[tuple(slice(b.start - x.start, b.stop - x.start)
                       for b, x in zip(box, sl))] = arr[box] == best
            fr = dict(m)
            fr["centre_index"] = [c[i] - sl[i].start for i in range(3)]
            cej_by = {}
            for ang, cj in zip(m["angles"], m["cej_mm"]):
                if cj is not None:
                    cej_by[int((ang + 180 - 7.5) // 15)] = cj
            cr = crest.get(key, {}).get("crest_mm", {})
            crest_by = {int(k2): val for k2, val in cr.items()}
            acc[sl] |= sleeve(tsub, fr, cej_by, crest_by, sp, tsub.shape,
                              facial=facing[key][0])
            n_teeth += 1

        # Close the interdental gaps IN PLANE, slice by slice.
        #
        # A 3D closing at this radius reaches ~1.8 mm in every direction, and in
        # the crowded posterior that bridges vertically across the occlusal
        # embrasures as readily as it bridges between neighbours -- fusing the
        # collars into flat slabs that lie over the buccal surfaces of the
        # molars. The operator spotted exactly that, and only in the posterior.
        #
        # An interdental gap is in-plane: it separates two teeth standing side by
        # side around the arch. Closing per axial slice fills it and cannot reach
        # over a crown, because it has no vertical extent to reach with.
        r = int(round(PAPILLA_CLOSE_MM / sp))
        disk = np.zeros((2 * r + 1, 2 * r + 1), bool)
        yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
        disk[yy * yy + xx * xx <= r * r] = True
        ging = np.zeros_like(acc)
        for z in range(acc.shape[0]):
            if acc[z].any():
                ging[z] = ndi.binary_closing(acc[z], disk)
        ging &= ~ndi.binary_dilation(teeth, np.ones((3, 3, 3)), 1)
        ging &= ~(lab == BONE[arch])
        l2, n2 = ndi.label(ging)
        if n2:
            szs = ndi.sum(ging, l2, range(1, n2 + 1)) * sp ** 3
            ging = np.isin(l2, [i + 1 for i in range(n2) if szs[i] > 40.0])

        vol_mm3 = float(ging.sum()) * sp ** 3
        print(f"{arch}: {n_teeth} collars -> {vol_mm3:7.1f} mm3")
        if ging.sum() > 500:
            f = ndi.gaussian_filter(ging.astype(np.float32), 1.1)
            verts, faces, _, _ = marching_cubes(f, level=0.5)
            world = np.empty_like(verts)
            world[:, 0] = v.origin[0] + verts[:, 2] * sp
            world[:, 1] = v.origin[1] + verts[:, 1] * sp
            world[:, 2] = v.origin[2] + verts[:, 0] * sp
            write_binary_stl(os.path.join(outdir, f"gingiva-{arch}.stl"),
                             world, faces)
            report["arches"][arch] = dict(volume_mm3=round(vol_mm3, 1),
                                          triangles=int(len(faces)),
                                          teeth=n_teeth)
    with open(os.path.join(outdir, "gingiva.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
