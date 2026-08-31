#!/usr/bin/env python3
"""Show one tooth's pulp segmentation at several contrast levels, side by side.

The threshold that separates pulp from dentin is not knowable a priori -- it
depends on this scanner, this patient's mineralisation, and how much partial
volume a given canal suffers. So instead of guessing it and defending the guess,
render the candidates and look: each row is one contrast level, each column the
same slice. The right level is the one where red fills the dark lumen and stops.

Usage: pulp_tune.py <vol.nrrd> <split-dir> <out-dir> <universal> [levels...]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from pulp_segment import segment_tooth                     # noqa: E402

SCALE = 3
WIN = (150.0, 1900.0)
PAD = 5


def grey(a):
    lo, hi = WIN
    return (np.clip((a - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


def tile(bg, mask):
    rgb = np.dstack([bg, bg, bg]).astype(np.uint8)
    edge = mask & ~ndi.binary_erosion(mask, np.ones((3, 3)))
    rgb[mask] = (0.5 * rgb[mask] + 0.5 * np.array([255, 60, 60])).astype(np.uint8)
    rgb[edge] = np.array([255, 25, 25], np.uint8)
    h, w = bg.shape
    return Image.fromarray(rgb, "RGB").resize((w * SCALE, h * SCALE), Image.NEAREST)


def main():
    vol_path, split_dir, outdir, uni = sys.argv[1:5]
    uni = int(uni)
    levels = [float(x) for x in sys.argv[5:]] or [200, 280, 360, 450]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    roi = v.data.astype(np.float32)
    vox = float(np.prod(sp))
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    for arch in ("upper", "lower"):
        hit = [t for t in rep[arch]["teeth"] if t["universal"] == uni]
        if not hit:
            continue
        t = hit[0]
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
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
        ms = m.copy()
        for k in range(m.shape[0]):
            if m[k].any():
                ms[k] = ndi.binary_fill_holes(m[k])
        sub = roi[sl]
        zs = np.where(ms.any(axis=(1, 2)))[0]
        panels = []
        for c in levels:
            keep, _ = segment_tooth(sub, ms, sp, arch, c)
            pz = np.where(keep.any(axis=(1, 2)))[0]
            cy, cx = (ndi.center_of_mass(keep)[1:] if keep.any()
                      else (ms.shape[1] // 2, ms.shape[2] // 2))
            row = [tile(grey(sub[:, int(cy), :]), keep[:, int(cy), :])]
            lo, hi = (int(pz.min()), int(pz.max())) if pz.size else (zs.min(), zs.max())
            for z in np.linspace(lo, hi, 4).astype(int):
                row.append(tile(grey(sub[z]), keep[z]))
            panels.append((c, keep.sum() * vox, 100 * keep.sum() / max(ms.sum(), 1), row))
        wmax = max(p.width for _, _, _, r in panels for p in r)
        hmax = max(p.height for _, _, _, r in panels for p in r)
        cols = 5
        sheet = Image.new("RGB", (cols * (wmax + PAD) + 150,
                                  len(panels) * (hmax + PAD) + PAD),
                          (18, 18, 20))
        dr = ImageDraw.Draw(sheet)
        for i, (c, mm3, pct, row) in enumerate(panels):
            y = PAD + i * (hmax + PAD)
            dr.text((4, y + 4), f"{c:.0f} HU", fill=(255, 220, 120))
            dr.text((4, y + 18), f"{mm3:.1f} mm3", fill=(200, 200, 200))
            dr.text((4, y + 32), f"{pct:.1f}% of tooth", fill=(160, 160, 160))
            for j, p in enumerate(row):
                sheet.paste(p, (150 + j * (wmax + PAD), y))
        out = os.path.join(outdir, f"tune-{uni:02d}.png")
        sheet.save(out)
        print(f"tooth {uni} -> {out}")


if __name__ == "__main__":
    main()
