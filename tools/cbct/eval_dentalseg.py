#!/usr/bin/env python3
"""Evaluate a DentalSegmentator label map against the hand-built segmentations.

DentalSegmentator gives per-CLASS labels, not per-tooth instances -- "Upper
Teeth" is one label covering all 14. That is still the blocker it removes: what
defeated the threshold pipeline was separating tooth from trabecular bone, not
separating adjacent teeth from each other. Splitting a teeth-only mask at the
interproximal contacts is a much easier problem than pulling a thin premolar
root out of the alveolus.

Usage: python3 tools/cbct/eval_dentalseg.py <pred.nii.gz> <volume.nrrd>
"""
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from read_nifti import read_nifti
from segment_tooth import TEETH, segment

LABELS = {1: "Upper Skull", 2: "Mandible", 3: "Upper Teeth",
          4: "Lower Teeth", 5: "Mandibular canal"}


def dice(a, b):
    s = a.sum() + b.sum()
    return 0.0 if s == 0 else 2.0 * (a & b).sum() / s


def main():
    pred_path, vol_path = sys.argv[1], sys.argv[2]
    lab, srow, pix = read_nifti(pred_path)
    v = Volume.load(vol_path)
    print(f"prediction shape {lab.shape}  spacing {pix}  volume shape {v.data.shape}")
    if lab.shape != v.data.shape:
        print("  !! shape mismatch -- prediction was not resampled back to the "
              "input grid; comparisons below would be meaningless")
        return
    vox = float(np.prod(v.spacing))
    print(f"\n{'label':20s} {'voxels':>10s} {'mm3':>10s}  components(>1mm3)")
    for k, name in LABELS.items():
        m = lab == k
        if not m.any():
            print(f"{name:20s} {'0':>10s}  {'0.0':>9s}  -- ABSENT")
            continue
        cc, n = ndi.label(m)
        sz = ndi.sum(m, cc, range(1, n + 1)) * vox
        print(f"{name:20s} {m.sum():10d} {m.sum()*vox:10.1f}  {(sz > 1.0).sum()}")

    # --- does the teeth label agree with the hand-built teeth?
    upper = lab == 3
    print("\nagreement with the hand-built segmentations (Dice):")
    for key in ("9", "5", "12"):
        if key not in TEETH:
            continue
        seg = segment(v, TEETH[key])
        z0, z1 = TEETH[key]["roi"]["z"]
        y0, y1 = TEETH[key]["roi"]["y"]
        x0, x1 = TEETH[key]["roi"]["x"]
        mine = seg["tooth"]
        theirs = upper[z0:z1, y0:y1, x0:x1]
        # restrict theirs to the connected piece overlapping mine, so we compare
        # the same tooth rather than mine against the whole arch
        cc, n = ndi.label(theirs)
        keep = set(np.unique(cc[mine])) - {0}
        theirs_t = np.isin(cc, list(keep)) if keep else np.zeros_like(theirs)
        print(f"  tooth {key:>2s}: mine {mine.sum()*vox:6.1f} mm3   "
              f"DentalSeg piece {theirs_t.sum()*vox:7.1f} mm3   "
              f"Dice {dice(mine, theirs_t):.3f}   "
              f"recall(mine covered) {(mine & theirs_t).sum()/max(mine.sum(),1):.3f}")


if __name__ == "__main__":
    main()
