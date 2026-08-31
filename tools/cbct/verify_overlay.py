#!/usr/bin/env python3
"""Overlay the modelled pulp on the CBCT it came from, tooth by tooth.

Every metric used so far has been a proxy, and several of them were blind to
defects the operator could see instantly (a whole-tooth twig count cannot
distinguish a pulp horn from an artefact; area/volume^(2/3) is dominated by the
canals and barely moves when the chamber changes). The only check that settles
whether the pulp sits in the void is looking at the pulp ON the void.

For each tooth this writes one sheet:

  row 1   two LONGITUDINAL planes through the pulp centroid, at right angles --
          roughly buccolingual and mesiodistal, so a canal that leaves the
          radiolucency in one plane is caught in the other
  rows 2+ AXIAL slices evenly spaced from the chamber roof to the apex

Grey is the CBCT at a fixed window; red is the model. Where the model is right
the red sits inside a dark lumen. Red on grey dentin is the model inventing
tissue; dark lumen with no red is the model missing it.

Usage: verify_overlay.py <vol.nrrd> <split-dir> <pulp-dir> <out-dir>
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402

SCALE = 5
N_AXIAL = 8
WIN = (150.0, 1900.0)        # display window, HU-ish
PAD = 6


def grey(a):
    lo, hi = WIN
    g = np.clip((a - lo) / (hi - lo), 0, 1)
    return (g * 255).astype(np.uint8)


def tile(bg, mask, scale=SCALE):
    """Grey background with the model in red, nearest-neighbour upscaled."""
    h, w = bg.shape
    rgb = np.dstack([bg, bg, bg]).astype(np.uint8)
    # solid fill at low alpha plus a hard outline, so thin canals stay visible
    edge = mask & ~ndi.binary_erosion(mask, np.ones((3, 3)))
    rgb[mask] = (0.55 * rgb[mask] + 0.45 * np.array([255, 60, 60])).astype(np.uint8)
    rgb[edge] = np.array([255, 30, 30], np.uint8)
    im = Image.fromarray(rgb, "RGB")
    return im.resize((w * scale, h * scale), Image.NEAREST)


def main():
    vol_path, split_dir, pulp_dir, outdir = sys.argv[1:5]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    roi_full = v.data.astype(np.float32)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    teeth = json.load(open(os.path.join(pulp_dir, "pulp-connect.json")))["teeth"]

    for arch in ("upper", "lower"):
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            num, fma = t["universal"], t["fma"]
            if fma not in teeth:
                continue
            tgt = np.array(t["world"][:2])
            best = min(ids, key=lambda s: float(np.hypot(
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[0] - tgt[0],
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[1] - tgt[1])))
            # USE THE CROP THE MASK WAS MADE WITH. Recomputing it here with a
            # different pad silently mismatched every hand-traced mask (the
            # tracing export pads by 10, this padded by 8) and the tool wrote no
            # sheets at all. Take the origin and shape from the record when the
            # producer wrote them.
            rec = teeth[fma]
            if "crop_origin_zyx" in rec and "shape_zyx" in rec:
                o = rec["crop_origin_zyx"]
                sh = rec["shape_zyx"]
                sl = tuple(slice(o[a], o[a] + sh[a]) for a in range(3))
            else:
                box = boxes[best - 1]
                pad = 8
                sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                           for b, n in zip(box, arr.shape))
            sub = roi_full[sl]
            P = np.load(os.path.join(pulp_dir, f"{fma}-pulp.npy"))
            if P.shape != sub.shape:
                print(f"{num}: shape mismatch {P.shape} vs {sub.shape}, skipped")
                continue
            pz = np.where(P.any(axis=(1, 2)))[0]
            if not pz.size:
                continue
            cy, cx = ndi.center_of_mass(P)[1:]
            cy, cx = int(round(cy)), int(round(cx))

            panels = []
            # longitudinal: the two planes through the pulp's own centroid
            panels.append(("long y", tile(grey(sub[:, cy, :]), P[:, cy, :])))
            panels.append(("long x", tile(grey(sub[:, :, cx]), P[:, :, cx])))
            # axial, chamber roof -> apex
            lo, hi = int(pz.min()), int(pz.max())
            for z in np.linspace(lo, hi, N_AXIAL).astype(int):
                panels.append((f"z={z}", tile(grey(sub[z]), P[z])))

            wmax = max(p.width for _, p in panels)
            hmax = max(p.height for _, p in panels)
            cols = 5
            rows = (len(panels) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * (wmax + PAD) + PAD,
                                      rows * (hmax + PAD + 14) + PAD),
                              (18, 18, 20))
            dr = ImageDraw.Draw(sheet)
            for i, (label, p) in enumerate(panels):
                r, c = divmod(i, cols)
                x = PAD + c * (wmax + PAD)
                y = PAD + r * (hmax + PAD + 14)
                sheet.paste(p, (x, y + 14))
                dr.text((x + 2, y + 2), f"{label}", fill=(200, 200, 200))
            dr.text((PAD, sheet.height - 12), f"tooth {num}  {fma}",
                    fill=(255, 220, 120))
            out = os.path.join(outdir, f"tooth-{num:02d}.png")
            sheet.save(out)
            print(f"tooth {num:2d} -> {os.path.basename(out)} "
                  f"({len(panels)} panels, {sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
