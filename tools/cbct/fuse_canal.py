#!/usr/bin/env python3
"""Rebuild the mandibular canal from both volumes, in the centered frame.

The canal is the inferior alveolar nerve's bony course, and it is the one neural
structure this dataset measures rather than approximates. In `centered` alone it
is truncated -- 328.7 mm3 in five pieces, with the left canal running into the
field-of-view edge at x = +40.8 mm against a boundary at +40.96. The `mandibular`
volume sees 544.3 mm3 of it.

This composites the two through the rigid transform from register.py. Per
docs/cbct-plan.md the fusion happens in MESH space, not voxel space: CBCT gray
values are uncalibrated and shift between exposures, so a spliced volume has two
intensity regimes and no threshold works across the seam. Labels are not
intensities, so unioning the two segmentations is legitimate where unioning the
two volumes would not be -- but the principle stands, and nothing here resamples
gray values.

Usage: python3 tools/cbct/fuse_canal.py <transform.json> <fixed.nii.gz> <moving.nii.gz> <out-dir>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import marching_cubes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_nifti import read_nifti
from register import euler
from segment_tooth import write_binary_stl
from vol import Volume

CANAL = 5


def main():
    tp, fp, mp, outdir = sys.argv[1:5]
    os.makedirs(outdir, exist_ok=True)
    p = json.load(open(tp))
    fl, _, pix = read_nifti(fp)
    ml, _, _ = read_nifti(mp)
    sp = tuple(float(x) for x in pix)
    vox = float(np.prod(sp))
    v = Volume.load(os.path.join(os.path.dirname(outdir), "nrrd", "centered.nrrd")) \
        if os.path.exists(os.path.join(os.path.dirname(outdir), "nrrd", "centered.nrrd")) else None

    centre = np.array(ndi.center_of_mass(fl == p["label"]))
    R = euler(*np.radians(p["rotation_deg"]))
    t = np.asarray(p["translation_mm"]) / np.asarray(sp)

    # Fuse on an EXPANDED grid, not the fixed volume's own.
    #
    # The transform is dominated by a -34.9 mm shift along z -- the mandibular
    # scan was aimed lower -- so resampling its canal into the centered grid
    # pushes roughly a third of it off the end and throws away exactly the
    # coverage this exercise exists to gain. The grid is therefore grown to hold
    # the union of both volumes' extents before anything is resampled.
    pad = np.ceil(np.abs(t)).astype(int) + 8
    shape = tuple(int(n + 2 * q) for n, q in zip(fl.shape, pad))
    off = pad.astype(float)

    big_fixed = np.zeros(shape, bool)
    big_fixed[pad[0]:pad[0] + fl.shape[0],
              pad[1]:pad[1] + fl.shape[1],
              pad[2]:pad[2] + fl.shape[2]] = (fl == CANAL)

    zz, yy, xx = np.indices(shape, dtype=np.float32)
    pts = np.stack([zz - off[0] - centre[0], yy - off[1] - centre[1],
                    xx - off[2] - centre[2]], axis=-1)
    src = pts @ R + np.asarray(centre) - t
    moved = ndi.map_coordinates((ml == CANAL).astype(np.float32),
                                [src[..., 0], src[..., 1], src[..., 2]],
                                order=1, mode="constant", cval=0.0) > 0.5

    a = big_fixed
    fused = a | moved
    k = np.ones((3, 3, 3))
    print(f"centered canal   {a.sum()*vox:8.1f} mm3  "
          f"{ndi.label(a, structure=k)[1]} pieces")
    print(f"mandibular canal {moved.sum()*vox:8.1f} mm3  "
          f"{ndi.label(moved, structure=k)[1]} pieces  (transformed)")
    print(f"union            {fused.sum()*vox:8.1f} mm3  "
          f"{ndi.label(fused, structure=k)[1]} pieces")
    # Close the small gaps the two views leave at their seam, then keep the
    # substantial runs -- ideally one canal per side.
    closed = ndi.binary_closing(fused, np.ones((5, 5, 5)))
    lab, n = ndi.label(closed, structure=k)
    sizes = ndi.sum(closed, lab, range(1, n + 1)) * vox
    keep = [i + 1 for i in np.argsort(sizes)[::-1] if sizes[i] > 15.0]
    canal = np.isin(lab, keep)
    print(f"after closing    {canal.sum()*vox:8.1f} mm3  {len(keep)} pieces kept")

    for i, sid in enumerate(keep, start=1):
        m = lab == sid
        zs, ys, xs = np.where(m)
        side = "RIGHT" if (np.mean(xs) - off[2]) * sp[2] - 40.96 < 0 else "LEFT"
        ext = [(xs.min(), xs.max()), (ys.min(), ys.max()), (zs.min(), zs.max())]
        print(f"  piece {i}: {m.sum()*vox:7.1f} mm3 [{side:5s}] "
              f"length along y {(ext[1][1]-ext[1][0])*sp[1]:5.1f} mm")

    # mesh it, in LPS millimetres like every other artefact
    field = ndi.gaussian_filter(canal.astype(np.float32), 0.8)
    verts, faces, _, _ = marching_cubes(field, level=0.5)
    world = np.empty_like(verts)
    origin = (-40.96, -58.074258, -44.520221)
    world[:, 0] = origin[0] + (verts[:, 2] - off[2]) * sp[2]
    world[:, 1] = origin[1] + (verts[:, 1] - off[1]) * sp[1]
    world[:, 2] = origin[2] + (verts[:, 0] - off[0]) * sp[0]
    out = os.path.join(outdir, "mandibular-canal.stl")
    write_binary_stl(out, world, faces)
    np.save(os.path.join(outdir, "mandibular-canal.npy"), canal)
    rep = dict(centered_mm3=round(float(a.sum()) * vox, 1),
               mandibular_mm3=round(float(moved.sum()) * vox, 1),
               fused_mm3=round(float(canal.sum()) * vox, 1),
               pieces=len(keep), stl=os.path.basename(out),
               triangles=int(len(faces)),
               source="union of both volumes' canal labels through "
                      "transform-mandibular-to-centered.json")
    with open(os.path.join(outdir, "canal.json"), "w") as f:
        json.dump(rep, f, indent=2)
    print(f"\n-> {out} ({len(faces)} triangles)")


if __name__ == "__main__":
    main()
