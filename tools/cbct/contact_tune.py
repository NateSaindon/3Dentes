#!/usr/bin/env python3
"""Show each inter-tooth BOUNDARY against the CBCT that the split was cut from.

Same discipline as pulp_tune.py and tissue_tune.py, and for the same reason: the
four enamel hole-detectors were all blind, and the thing that actually found the
defect was a sheet somebody looked at. So this does not score a boundary. It
draws it on the image and lets the operator say which ones are wrong.

What to look for -- the signature is the one CLAUDE.md already names for enamel:
a STRAIGHT edge. Anatomy does not produce those. Two crowns in true contact meet
at a point (a small area, clinically), and above and below that point the
interproximal EMBRASURES open out as curved, facing gaps. So a correct boundary
should read as an hourglass across the axial stack -- wide apart occlusally,
pinching to the contact, opening again cervically. A boundary that is a straight
chord at every level, of roughly constant length, is the watershed having found
no waist to settle into and splitting the difference between two eroded seeds.

Layout, one sheet per contact:

  ROWS are the two teeth's own colours, so a wedge of one sitting inside the
      other's crown is visible as colour, not as a line to be interpreted.
  AXIALS span the contact's whole z extent, occlusal to cervical, because the
      hourglass is a claim about how the boundary CHANGES with depth and a
      single level cannot show it.
  The BOUNDARY voxels are drawn white on top, so its straightness is judged
      directly rather than inferred from where two colours meet.

Usage: contact_tune.py <vol.nrrd> <split-dir> <out-dir> <upper|lower|all> [n_axial]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402

SCALE = 4
WIN = (150.0, 2600.0)      # same window as the enamel sheets, for comparability
PAD = 6
N_AXIAL = 7
A = (255, 140, 60)         # the mesial tooth of the pair
B = (90, 190, 255)         # the distal tooth of the pair
LINE = (255, 255, 255)     # the boundary itself
STR6 = ndi.generate_binary_structure(3, 1)


def grey(a):
    lo, hi = WIN
    return (np.clip((a - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


def tile(bg, ma, mb, iface):
    rgb = np.dstack([bg, bg, bg]).astype(np.uint8)
    for m, col in ((ma, A), (mb, B)):
        if m.any():
            rgb[m] = (0.55 * rgb[m] + 0.45 * np.array(col)).astype(np.uint8)
    if iface.any():
        rgb[iface] = np.array(LINE, np.uint8)
    h, w = bg.shape
    return Image.fromarray(rgb, "RGB").resize((w * SCALE, h * SCALE), Image.NEAREST)


def seg_to_universal(v, arch, arr, rep):
    """Map each label id to its Universal number by CENTROID, not by order.

    split_arch walks the lower arch from the patient's left and split_teeth's
    main() therefore iterates it in reverse, so for the lower arch label id 1 is
    tooth 31 and not tooth 18. Assuming the two orders agree silently mirrors
    every lower-arch sheet -- the pairs stay real, because the arch is roughly
    symmetric in tooth type, which is exactly why it survives a glance.
    """
    n = int(arr.max())
    cents = ndi.center_of_mass(arr > 0, arr, range(1, n + 1))
    out = {}
    for s in range(1, n + 1):
        cz, cy, cx = cents[s - 1]
        wx, wy, _ = v.world(cx, cy, cz)
        best = min(rep[arch]["teeth"],
                   key=lambda t: (t["world"][0] - wx) ** 2 + (t["world"][1] - wy) ** 2)
        out[s] = best["universal"]
    return out


def contact_sheet(v, arch, arr, seg2uni, i, j, outdir, n_axial):
    """One sheet for the boundary between label i and label j."""
    uni_i, uni_j = seg2uni[i], seg2uni[j]
    a, b = arr == i, arr == j
    iface = a & ndi.binary_dilation(b, STR6)
    if iface.sum() < 10:
        return None

    # Crop to the interface, padded enough to show both crowns around it.
    zz, yy, xx = np.where(iface)
    pad = 22
    sl = tuple(slice(max(0, c.min() - pad), min(n, c.max() + 1 + pad))
               for c, n in zip((zz, yy, xx), arr.shape))
    sub = v.data[sl].astype(np.float32)
    sa, sb, si = a[sl], b[sl], iface[sl]

    # Axials spanning the interface, occlusal first. In LPS z increases
    # superiorly, so the upper arch is walked downwards and the lower upwards
    # to put the occlusal surface first in both.
    zs = np.where(si.any(axis=(1, 2)))[0]
    levels = np.linspace(zs.min(), zs.max(), n_axial).astype(int)
    if arch == "upper":
        levels = levels[::-1]

    tiles, labels = [], []
    for z in levels:
        tiles.append(tile(grey(sub[z]), sa[z], sb[z], si[z]))
        wz = v.world(0, 0, sl[0].start + int(z))[2]
        labels.append(f"z {wz:.1f}")

    w, h = tiles[0].size
    head = 30
    img = Image.new("RGB", (len(tiles) * (w + PAD) + PAD, h + head + 20), (18, 18, 20))
    dr = ImageDraw.Draw(img)
    dr.text((PAD, 6), f"{arch}  {uni_i}-{uni_j}   "
                      f"interface {si.sum() * float(np.prod(v.spacing)) ** (2/3):.0f} vox   "
                      f"occlusal -> cervical", fill=(230, 230, 230))
    dr.text((PAD, 18), f"orange = {uni_i}   blue = {uni_j}   white = boundary",
            fill=(150, 150, 150))
    for k, (t, lb) in enumerate(zip(tiles, labels)):
        x = PAD + k * (w + PAD)
        img.paste(t, (x, head))
        dr.text((x + 2, head + h + 4), lb, fill=(150, 150, 150))
    out = os.path.join(outdir, f"contact-{arch}-{uni_i:02d}-{uni_j:02d}.png")
    img.save(out)
    return out


def main():
    if len(sys.argv) < 5:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    vol_path, split_dir, outdir, which = sys.argv[1:5]
    n_axial = int(sys.argv[5]) if len(sys.argv) > 5 else N_AXIAL
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    arches = ("upper", "lower") if which == "all" else (which,)
    made = []
    for arch in arches:
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        seg2uni = seg_to_universal(v, arch, arr, rep)
        for i in range(1, int(arr.max())):
            out = contact_sheet(v, arch, arr, seg2uni, i, i + 1, outdir, n_axial)
            if out:
                made.append(out)
                print(out)
    print(f"\n{len(made)} sheets -> {outdir}")


if __name__ == "__main__":
    main()
