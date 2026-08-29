#!/usr/bin/env python3
"""Pilot: segment one tooth from a CBCT volume into enamel / dentin / pulp and
write binary STLs in LPS millimetres.

Isolation is marker-based watershed, not thresholding. A tooth cannot be
thresholded out of its socket: root dentin and alveolar bone overlap in density,
and neighbouring teeth touch at their contact points. What *does* separate them
is darkness -- the interproximal space and the periodontal ligament -- so the
watershed is seeded inside the target tooth, inside each neighbour, and inside
bone, and the dark boundaries become the basin walls.

Output is LPS millimetres, which is z-up with anterior toward -y -- the same
convention BodyParts3D uses, so these STLs pass through tools/build-assets.mjs
without any extra transform and satisfy the laterality assertion unchanged.

Usage: python3 tools/cbct/segment_tooth.py <volume.nrrd> <tooth-key> <out-dir>
"""
import json, os, struct, sys

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import threshold_otsu
from skimage.measure import marching_cubes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume

NOISE_HU = 70.0          # measured sd in homogeneous regions, docs/cbct-survey.md
BONE_CUT = 1050          # above PDL/marrow, below dentin; see the survey
PULP_CUT = 1050          # pulp cavity is far below dentin; see docs/cbct-pilot.md

# Per-tooth pilot spec. Seeds are (x, y, z) volume indices.
TEETH = {
    # Universal 9, maxillary left central incisor. FMA id is the pipeline join key.
    "9": dict(
        fma="FMA55682", name="maxillary left central incisor",
        roi=dict(z=(195, 330), y=(25, 160), x=(215, 360)),
        seeds=[(288, 61, 215), (290, 80, 258)],
        neighbours=[[(235, 61, 215), (238, 80, 258)],     # tooth 8
                    [(330, 70, 215), (333, 85, 255)]],    # tooth 10
        # Bone basins as half-spaces in volume-index coordinates: periapical bone
        # above the apex, and the palatal shelf behind the tooth.
        bone_planes=[("z", ">=", 312), ("y", ">=", 135)],
        canals=1,
    ),
    # Universal 5, maxillary right first premolar. Two roots, two canals -- the
    # multi-canal test. The palate is medial here, so the palatal bone plane is
    # on +x (toward the midline), not posterior as it is for an incisor.
    "5": dict(
        fma="FMA55689", name="maxillary right first premolar",
        roi=dict(z=(195, 350), y=(95, 265), x=(105, 235)),
        seeds=[(178, 168, 218), (155, 174, 257)],
        neighbours=[[(171, 113, 227), (180, 133, 268)],   # tooth 6, canine
                    [(137, 201, 216), (140, 218, 261)]],  # tooth 4
        bone_planes=[("z", ">=", 335), ("x", ">=", 215)],
        canals=2,
    ),
    # Universal 12, maxillary left first premolar. Mirror of 5; palatal is -x.
    "12": dict(
        fma="FMA55690", name="maxillary left first premolar",
        roi=dict(z=(195, 350), y=(70, 255), x=(300, 460)),
        seeds=[(392, 149, 216), (392, 168, 256)],
        neighbours=[[(356, 100, 224), (357, 124, 268)],   # tooth 11, canine
                    [(387, 191, 216), (402, 211, 258)]],  # tooth 13
        bone_planes=[("z", ">=", 335), ("x", "<=", 316)],
        canals=2,
    ),
}


def _ball(rad):
    k = np.arange(-rad, rad + 1)
    Z, Y, X = np.meshgrid(k, k, k, indexing="ij")
    return (Z**2 + Y**2 + X**2) <= rad * rad + 1e-9


def write_binary_stl(path, verts, faces):
    tris = verts[faces]                                    # (n, 3, 3)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    with open(path, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(faces)))
        rec = np.zeros((len(faces), 12), dtype="<f4")
        rec[:, 0:3] = n
        rec[:, 3:6], rec[:, 6:9], rec[:, 9:12] = a, b, c
        buf = bytearray()
        raw = rec.tobytes()
        for i in range(len(faces)):
            buf += raw[i * 48:(i + 1) * 48] + b"\0\0"
        f.write(bytes(buf))


def mesh(mask, v, roi_origin_idx, roi=None, level=None, sigma=0.6, band=2):
    """Mask -> surface in world-space LPS millimetres.

    Where a grey-level `level` is given, marching cubes runs on the intensity
    field itself (confined to a dilation of the mask) rather than on the binary
    mask. That matters: a binary mask can only put a vertex on a voxel boundary,
    so its surface terraces at 0.16 mm no matter how much it is smoothed
    afterwards. Interpolating the real grey levels puts the surface where the
    density boundary actually falls, which is what the atlas should show.
    """
    if mask.sum() < 64:
        return None
    if roi is not None and level is not None:
        near = ndi.binary_dilation(mask, ndi.generate_binary_structure(3, 1), band)
        field = np.where(near, ndi.gaussian_filter(roi, 0.5), level - 1500.0)
        field = np.maximum(field, np.where(mask, level + 1.0, field))
        verts, faces, _, _ = marching_cubes(field.astype(np.float32), level=float(level))
    else:
        field = ndi.gaussian_filter(mask.astype(np.float32), sigma)
        verts, faces, _, _ = marching_cubes(field, level=0.5)
    # verts are (z, y, x) index within the ROI
    zi, yi, xi = verts[:, 0], verts[:, 1], verts[:, 2]
    world = np.empty_like(verts)
    world[:, 0] = v.origin[0] + (roi_origin_idx[0] + xi) * v.spacing[0]
    world[:, 1] = v.origin[1] + (roi_origin_idx[1] + yi) * v.spacing[1]
    world[:, 2] = v.origin[2] + (roi_origin_idx[2] + zi) * v.spacing[2]
    return world, faces


def segment(v, spec):
    z0, z1 = spec["roi"]["z"]; y0, y1 = spec["roi"]["y"]; x0, x1 = spec["roi"]["x"]
    roi = v.data[z0:z1, y0:y1, x0:x1].astype(np.float32)
    mask = roi > BONE_CUT

    markers = np.zeros(roi.shape, np.int32)
    def put(lbl, seeds, r=2):
        for (x, y, z) in seeds:
            k, j, i = z - z0, y - y0, x - x0
            markers[k-r:k+r+1, j-r:j+r+1, i-r:i+r+1] = lbl

    markers[roi < 800] = 1                                  # background
    put(2, spec["seeds"])
    for n, seeds in enumerate(spec["neighbours"]):
        put(3 + n, seeds)
    bone = 3 + len(spec["neighbours"])
    # Bone basins, given as half-spaces so the geometry can follow the tooth.
    # An incisor's non-tooth neighbourhood is behind it (palatal shelf) and above
    # it (periapical); a premolar's is medial, because the palate is toward the
    # midline rather than posterior. A fixed posterior plane is wrong there.
    axes = {"z": 0, "y": 1, "x": 2}
    lows = {"z": z0, "y": y0, "x": x0}
    for axis, op, idx in spec["bone_planes"]:
        a = axes[axis]
        local = idx - lows[axis]
        n_a = roi.shape[a]
        if op == ">=":
            sl = slice(max(local, 0), n_a)
        else:
            sl = slice(0, min(local + 1, n_a))
        view = [slice(None)] * 3
        view[a] = sl
        view = tuple(view)
        sub = markers[view]
        sub[mask[view]] = bone

    ws = watershed_isolate(roi, markers, mask)
    tooth = ws == 2
    lab, n = ndi.label(tooth)
    if n > 1:
        sz = ndi.sum(tooth, lab, range(1, n + 1))
        tooth = lab == (int(np.argmax(sz)) + 1)
    # --- Reconstruct the tooth as a SOLID.
    #
    # The watershed basin is dentin and enamel only: the pulp is below the
    # isolation threshold, so it is a void in the basin. A plain 3D fill_holes
    # does not close it, because the canal opens to the periapical space through
    # the apical foramen -- the void is not topologically enclosed. Filling
    # per axial slice does close it, since in an axial cut the canal is a ring
    # of dentin, and it leaves the outer surface untouched. A small 3D closing
    # afterwards seals the slices where that ring is broken by partial volume.
    tooth = ndi.binary_fill_holes(tooth)
    for k in range(tooth.shape[0]):
        tooth[k] = ndi.binary_fill_holes(tooth[k])
    tooth = ndi.binary_fill_holes(ndi.binary_closing(tooth, _ball(2)))

    dist = ndi.distance_transform_edt(tooth, sampling=tuple(v.spacing))

    # --- pulp: the low-density cavity inside the solid.
    # PROVISIONAL. The cavity is real and strongly contrasted (see the QC block
    # in the report), but the canal wall is not consistently above the isolation
    # threshold, so the extracted space fragments and its cross-section varies
    # more than real canal anatomy does. Treat the volume as an estimate and do
    # not ship this surface without review -- see docs/cbct-pilot.md.
    cand = tooth & (roi < PULP_CUT) & (dist > 0.30)
    lab, n = ndi.label(cand)
    pulp = np.zeros_like(tooth)
    n_frag = 0
    if n:
        sz = ndi.sum(cand, lab, range(1, n + 1)) * float(np.prod(v.spacing))
        keep = [i + 1 for i in range(n) if sz[i] > 0.4]     # drop noise specks
        n_frag = len(keep)
        pulp = np.isin(lab, keep)

    body = tooth & ~pulp
    thr = float(threshold_otsu(roi[body]))
    en = ndi.binary_opening(body & (roi > thr), ndi.generate_binary_structure(3, 1))
    l3, n3 = ndi.label(en)
    if n3:
        sz = ndi.sum(en, l3, range(1, n3 + 1))
        en = l3 == (int(np.argmax(sz)) + 1)
    enamel = ndi.binary_closing(en, ndi.generate_binary_structure(3, 1), iterations=2) & body
    dentin = body & ~enamel
    # --- diagnostic: the half-maximum level, and the tooth-to-bone contrast.
    #
    # Reported, NOT used for meshing. Placing the surface at the half-maximum was
    # tried and over-grows: it made an incisor and a premolar measure identically
    # (~21 mm long, ~490-530 mm3), which is wrong. It is kept because the numbers
    # diagnose the real problem -- tooth 5's root dentin reads 1059 HU against
    # tooth 9's 1305 with the same surrounding PDL, so the premolar's thin roots
    # lose 42% of the tooth-to-bone contrast to partial volume. Density is a weak
    # discriminator there; the PDL dark ring is a much stronger one.
    zs = np.where(tooth)[0]
    zmid = (zs.min() + zs.max()) // 2
    rootband = np.zeros_like(tooth)
    rootband[zmid:] = True
    shell = (ndi.binary_dilation(tooth, _ball(4))
             & ~ndi.binary_dilation(tooth, _ball(1)) & rootband)
    core = tooth & (dist > 0.8) & rootband
    if shell.sum() > 500 and core.sum() > 200:
        surface_level = 0.5 * (float(np.percentile(roi[shell], 25))
                               + float(np.percentile(roi[core], 60)))
    else:
        surface_level = float(BONE_CUT)

    pulp_contrast = (float(np.median(roi[dentin])) - float(np.median(roi[pulp]))
                     if pulp.any() else 0.0)
    return dict(tooth=tooth, enamel=enamel, dentin=dentin, pulp=pulp,
                roi=roi, origin_idx=(x0, y0, z0), otsu=thr,
                surface_level=surface_level,
                pulp_fragments=n_frag, pulp_contrast_hu=pulp_contrast)


def watershed_isolate(roi, markers, mask):
    from skimage.segmentation import watershed
    return watershed(-roi, markers, mask=mask)


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    vol_path, key, outdir = sys.argv[1:4]
    if key not in TEETH:
        raise SystemExit(f"unknown tooth {key!r}; known: {sorted(TEETH)}")
    spec = TEETH[key]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    r = segment(v, spec)
    vox_mm3 = float(np.prod(v.spacing))
    report = dict(tooth=key, fma=spec["fma"], name=spec["name"],
                  source=os.path.basename(vol_path),
                  otsu_enamel_dentin_hu=round(r["otsu"]),
                  surface_level_hu=round(r["surface_level"]),
                  qc=dict(pulp_fragments=r["pulp_fragments"],
                          pulp_dentin_contrast_hu=round(r["pulp_contrast_hu"]),
                          pulp_status="provisional - fragments, do not ship unreviewed"),
                  tissues={})
    # Grey-level isovalues for the surfaces that have one. Dentin's outer surface
    # is the tooth surface and its inner surface is the pulp, so it is meshed
    # from its mask; the atlas shows it under enamel anyway.
    levels = dict(tooth=BONE_CUT, enamel=r["otsu"], dentin=None, pulp=None)
    for tis in ("tooth", "enamel", "dentin", "pulp"):
        m = r[tis]
        out = mesh(m, v, r["origin_idx"], roi=r["roi"], level=levels[tis])
        entry = dict(volume_mm3=round(float(m.sum()) * vox_mm3, 1), voxels=int(m.sum()))
        if out is not None:
            verts, faces = out
            name = spec["fma"] if tis == "tooth" else f"{spec['fma']}-{tis}"
            p = os.path.join(outdir, f"{name}.stl")
            write_binary_stl(p, verts, faces)
            entry.update(stl=os.path.basename(p), triangles=int(len(faces)),
                         bbox_lps_min=[round(float(x), 2) for x in verts.min(0)],
                         bbox_lps_max=[round(float(x), 2) for x in verts.max(0)])
        report["tissues"][tis] = entry
        print(f"  {tis:7s} {entry['volume_mm3']:8.1f} mm3"
              + (f"  -> {entry['stl']} ({entry['triangles']} tris)" if "stl" in entry else "  (no mesh)"))
    with open(os.path.join(outdir, f"tooth{key}.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("wrote", os.path.join(outdir, f"tooth{key}.json"))


if __name__ == "__main__":
    main()
