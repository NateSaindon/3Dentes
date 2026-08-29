#!/usr/bin/env python3
"""Export the measured jaws and gingiva into the CBCT asset tree.

Building CBCT teeth alongside BodyParts3D jaws does not work, and the reason is
worth stating: **they are different coordinate frames belonging to different
people.** BodyParts3D is a whole-body frame with the head about 1470 mm off the
floor; CBCT is scanner-centred at a few tens of millimetres. Mixing them gave a
model 1582 mm tall. Even registered, the teeth of one individual do not sit in
another's jaws.

So the patient's own anatomy becomes the reference frame, and the model is built
from measured structures only. Muscles have no CBCT equivalent -- there is no
soft-tissue contrast in this scan at all -- so they are simply absent from this
build rather than borrowed and misplaced.

"Maxilla" here is DentalSegmentator's Upper Skull label cropped to the alveolar
process and palate. The full label is the whole cranium, which is neither what
the manifest's maxilla entry means nor something the atlas wants to draw.

Usage: python3 tools/cbct/export_bone.py <volume.nrrd> <pred.nii.gz> <split-dir>
                                         <gingiva-dir> <out-dir>
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
from export_teeth import decimate
from meshsmooth import taubin, weld

MANDIBLE_FMA = "FMA52748"
MAXILLA_FMA = "FMA53649"
GINGIVA = {"upper": "FMA59763", "lower": "FMA59764"}
MAXILLA_NEAR_TEETH_MM = 22.0
TARGET = {"bone": 24000, "gingiva": 12000}


def mesh_mask(mask, v, target, smooth=1.0):
    if mask.sum() < 500:
        return None
    f = ndi.gaussian_filter(mask.astype(np.float32), smooth)
    verts, faces, _, _ = marching_cubes(f, level=0.5)
    world = np.empty_like(verts)
    sp = float(v.spacing[0])
    world[:, 0] = v.origin[0] + verts[:, 2] * sp
    world[:, 1] = v.origin[1] + verts[:, 1] * sp
    world[:, 2] = v.origin[2] + verts[:, 0] * sp
    world = taubin(world, faces, 16)
    world, faces = decimate(world, faces, target)
    return taubin(world, faces, 4), faces


def main():
    vol_path, pred_path, split_dir, ging_dir, outdir = sys.argv[1:6]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    lab, _, _ = read_nifti(pred_path)
    sp = float(v.spacing[0])
    upper = np.load(os.path.join(split_dir, "upper_labels.npy")) > 0
    rep = {}

    # mandible: the label as-is, minus the teeth so the sockets read correctly
    mand = (lab == 2) & ~(np.load(os.path.join(split_dir, "lower_labels.npy")) > 0)
    mand = ndi.binary_closing(mand, np.ones((3, 3, 3)))
    got = mesh_mask(mand, v, TARGET["bone"])
    if got:
        write_binary_stl(os.path.join(outdir, f"{MANDIBLE_FMA}.stl"), *got)
        rep[MANDIBLE_FMA] = dict(name="mandible", triangles=int(len(got[1])),
                                 volume_mm3=round(float(mand.sum()) * sp ** 3, 1))
        print(f"  mandible  {MANDIBLE_FMA}  {len(got[1]):,} tris")

    # maxilla: Upper Skull cropped to the alveolar process and palate
    near = ndi.distance_transform_edt(~upper, sampling=(sp,) * 3) < MAXILLA_NEAR_TEETH_MM
    maxi = (lab == 1) & near & ~upper
    maxi = ndi.binary_closing(maxi, np.ones((3, 3, 3)))
    l, n = ndi.label(maxi)
    if n:
        szs = ndi.sum(maxi, l, range(1, n + 1))
        maxi = l == (int(np.argmax(szs)) + 1)
    got = mesh_mask(maxi, v, TARGET["bone"])
    if got:
        write_binary_stl(os.path.join(outdir, f"{MAXILLA_FMA}.stl"), *got)
        rep[MAXILLA_FMA] = dict(name="maxilla (alveolar process and palate)",
                                triangles=int(len(got[1])),
                                volume_mm3=round(float(maxi.sum()) * sp ** 3, 1))
        print(f"  maxilla   {MAXILLA_FMA}  {len(got[1]):,} tris")

    # gingiva: decimate what gingiva.py produced
    for arch, fma in GINGIVA.items():
        src = os.path.join(ging_dir, f"gingiva-{arch}.stl")
        if not os.path.exists(src):
            continue
        import struct
        b = open(src, "rb").read()
        nt = struct.unpack("<I", b[80:84])[0]
        rec = np.frombuffer(b[84:84 + nt * 50], dtype=np.uint8).reshape(nt, 50)
        tri = rec[:, 12:48].copy().view("<f4").reshape(nt * 3, 3).astype(np.float64)
        verts, faces = weld(tri)
        verts = taubin(verts, faces, 10)
        verts, faces = decimate(verts, faces, TARGET["gingiva"])
        verts = taubin(verts, faces, 6)
        write_binary_stl(os.path.join(outdir, f"{fma}.stl"), verts, faces)
        rep[fma] = dict(name=f"gingiva of {arch} jaw", triangles=int(len(faces)))
        print(f"  gingiva   {fma}  {nt:,} -> {len(faces):,} tris")

    with open(os.path.join(outdir, "bone.json"), "w") as f:
        json.dump(rep, f, indent=2)
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
