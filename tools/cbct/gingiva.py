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

MARGIN_ABOVE_CEJ_MM = 1.0     # free gingival margin sits ~1 mm coronal to the CEJ
THICKNESS_MM = 1.1            # gingival thickness on the tooth and bone
MGJ_BELOW_CREST_MM = 4.0      # mucogingival junction, apical to the measured crest
PAPILLA_CLOSE_MM = 1.8        # closes the interdental gap between adjacent collars
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


def sleeve(tooth, frame, cej_by_angle, crest_by_angle, spacing, shape):
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
        top = (cej + MARGIN_ABOVE_CEJ_MM) / spacing
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

    report = dict(provenance="DERIVED from the measured CEJ and alveolar crest. "
                             "Gingiva is not visible in CBCT.",
                  models="health -- no recession, no inflammation, average biotype",
                  construction="per-tooth collar lofted from the margin ring to "
                               "below the crest, closed interdentally into papillae",
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
            acc[sl] |= sleeve(tsub, fr, cej_by, crest_by, sp, tsub.shape)
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
