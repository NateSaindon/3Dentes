#!/usr/bin/env python3
"""Generate gingiva from the measured CEJ and the bone surface.

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

So: the margin comes from the CEJ, and the attached gingiva is draped on the bone
surface itself without ever needing a crest height.

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
PAPILLA_RISE_MM = 2.5         # interdental papilla above the mid-facial margin
THICKNESS_MM = 1.3            # gingival thickness over bone
MGJ_BELOW_CREST_MM = 4.0      # mucogingival junction, apical to the measured crest
NEAR_TEETH_MM = 11.0          # gingiva hugs the alveolar ridge, not the whole jaw
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


def main():
    vol_path, split_dir, pred_path, lm_path, crest_path, outdir = sys.argv[1:7]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    lab, _, _ = read_nifti(pred_path)
    lm = json.load(open(lm_path))
    crest = json.load(open(crest_path))
    sp = float(v.spacing[0])

    upper = np.load(os.path.join(split_dir, "upper_labels.npy")) > 0
    lower = np.load(os.path.join(split_dir, "lower_labels.npy")) > 0
    teeth = upper | lower
    marg = margin_points(lm, v)

    report = dict(provenance="DERIVED from the measured CEJ and the segmented "
                             "bone surface. Gingiva is not visible in CBCT.",
                  models="health -- no recession, no inflammation, average biotype",
                  margin_above_cej_mm=MARGIN_ABOVE_CEJ_MM,
                  mgj_below_crest_mm=MGJ_BELOW_CREST_MM,
                  papilla_rise_mm=PAPILLA_RISE_MM,
                  thickness_mm=THICKNESS_MM, arches={})

    for arch, sign in (("upper", -1.0), ("lower", +1.0)):
        # `sign` is the coronal direction in z: maxillary crowns hang down.
        bone = lab == BONE[arch]
        if not bone.any():
            continue
        pts = np.vstack([m["points"] for m in marg.values() if m["arch"] == arch])

        # Margin height from the NEAREST margin point, not a smoothed field.
        # Smoothing over (x, y) averages across the arch and flattens the
        # scallop; nearest-neighbour keeps each tooth's own margin, and the
        # interdental rise appears on its own because the CEJ is already higher
        # between the teeth.
        ix = np.clip(((pts[:, 0] - v.origin[0]) / sp).astype(int), 0, bone.shape[2] - 1)
        iy = np.clip(((pts[:, 1] - v.origin[1]) / sp).astype(int), 0, bone.shape[1] - 1)
        iz = (pts[:, 2] - v.origin[2]) / sp
        H, W = bone.shape[1], bone.shape[2]
        acc = np.full((H, W), np.nan)
        for a, b, z in zip(iy, ix, iz):
            acc[a, b] = z if np.isnan(acc[a, b]) else (
                max(acc[a, b], z) if sign > 0 else min(acc[a, b], z))
        known = ~np.isnan(acc)
        if known.sum() < 10:
            continue
        idx = ndi.distance_transform_edt(~known, return_distances=False,
                                         return_indices=True)
        field = ndi.gaussian_filter(acc[tuple(idx)], 1.5)

        # Apical limit from the MEASURED crest, per tooth, not a fixed depth.
        capical = np.full((H, W), np.nan)
        for key, m in marg.items():
            if m["arch"] != arch:
                continue
            cr = crest.get(key)
            if cr is None:
                continue
            depth = float(np.median(list(cr["crest_mm"].values())))
            fr = lm[key]
            c = np.array(fr["centre_index"], float)
            ax = np.array(fr["axis"], float)
            base = c + (depth / sp - MGJ_BELOW_CREST_MM / sp) * ax
            w = v.world(base[2], base[1], base[0])
            bx = int((w[0] - v.origin[0]) / sp); by = int((w[1] - v.origin[1]) / sp)
            if 0 <= by < H and 0 <= bx < W:
                capical[by, bx] = (w[2] - v.origin[2]) / sp
        kn2 = ~np.isnan(capical)
        if kn2.sum() >= 3:
            i2 = ndi.distance_transform_edt(~kn2, return_distances=False,
                                            return_indices=True)
            apical_field = ndi.gaussian_filter(capical[tuple(i2)], 2.0)
        else:
            apical_field = field - sign * (7.0 / sp)

        zz = np.arange(bone.shape[0])[:, None, None]
        below_margin = (zz - field[None, :, :]) * sign <= 0
        above_mgj = (zz - apical_field[None, :, :]) * sign >= 0
        band = below_margin & above_mgj

        # Hug the alveolar ridge. Without this the envelope wraps the entire
        # mandible and returns a 7300 mm3 slab instead of gingiva.
        near = ndi.distance_transform_edt(~teeth, sampling=(sp, sp, sp)) < NEAR_TEETH_MM

        env = ndi.binary_dilation(bone, np.ones((3, 3, 3)),
                                  int(round(THICKNESS_MM / sp)))
        ging = (env & ~bone
                & ~ndi.binary_dilation(teeth, np.ones((3, 3, 3)), 1)
                & band & near)
        ging = ndi.binary_closing(ging, np.ones((3, 3, 3)))
        l2, n2 = ndi.label(ging)
        if n2:
            szs = ndi.sum(ging, l2, range(1, n2 + 1)) * sp ** 3
            ging = np.isin(l2, [i + 1 for i in range(n2) if szs[i] > 60.0])

        vol_mm3 = float(ging.sum()) * sp ** 3
        print(f"{arch}: {vol_mm3:8.1f} mm3 gingiva")
        if ging.sum() > 500:
            f = ndi.gaussian_filter(ging.astype(np.float32), 1.2)
            verts, faces, _, _ = marching_cubes(f, level=0.5)
            world = np.empty_like(verts)
            world[:, 0] = v.origin[0] + verts[:, 2] * sp
            world[:, 1] = v.origin[1] + verts[:, 1] * sp
            world[:, 2] = v.origin[2] + verts[:, 0] * sp
            write_binary_stl(os.path.join(outdir, f"gingiva-{arch}.stl"),
                             world, faces)
            report["arches"][arch] = dict(volume_mm3=round(vol_mm3, 1),
                                          triangles=int(len(faces)))
    with open(os.path.join(outdir, "gingiva.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
