#!/usr/bin/env python3
"""Show one tooth's ENAMEL shell against the CBCT, at several density cuts.

Same discipline as pulp_tune.py: the level is CHOSEN BY LOOKING, not defended
afterwards. What changed is what is being tuned. Enamel is no longer a threshold
blob -- enamel.py constrains it to a depth-limited shell on the anatomic crown
from published thickness figures -- so the cut now only has to separate enamel
from dentin INSIDE that envelope, which is a far easier question than the one a
global threshold was being asked.

The sheet is laid out to make the two failures the operator identified visible:

  CUSPS.  Axials span the WHOLE crown, tip to CEJ, not just the cervical third,
      because "cusps missing" is invisible on a sheet that never shows a cusp.
  DEPTH.  The envelope's inner boundary is drawn, so enamel running deeper than
      anatomy allows is seen against the rule rather than argued about. If the
      blue ever reaches the chamber the envelope is drawn wrong.

The CEJ that divides crown from root is marked on the longitudinal panels. It
comes from the tooth's cervical narrowing, NOT from the enamel ray -- see
enamel.py.

Usage: tissue_tune.py <vol.nrrd> <split-dir> <out-dir> <universal|all> [cuts...]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
import enamel as EN                                        # noqa: E402

SCALE = 3
WIN = (150.0, 2600.0)      # enamel lives at the top of the range
PAD = 5
N_AXIAL = 5
CUTS = (300.0, 420.0, 540.0, 660.0)     # HU above the tooth's own coronal dentin
BLUE = (90, 190, 255)
EDGE = (255, 210, 90)      # envelope boundary
CEJ = (255, 120, 120)


def bbox2d(mask, pad=4):
    if not mask.any():
        return slice(None), slice(None)
    r = np.where(mask.any(1))[0]
    c = np.where(mask.any(0))[0]
    return (slice(max(0, r.min() - pad), r.max() + 1 + pad),
            slice(max(0, c.min() - pad), c.max() + 1 + pad))


def grey(a):
    lo, hi = WIN
    return (np.clip((a - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


def tile(bg, mask, env=None, cej_row=None):
    """Grey slice, enamel filled blue, the envelope's limit outlined amber."""
    rgb = np.dstack([bg, bg, bg]).astype(np.uint8)
    if env is not None and env.any():
        line = env & ~ndi.binary_erosion(env, np.ones((3, 3)))
        rgb[line] = (0.45 * rgb[line] + 0.55 * np.array(EDGE)).astype(np.uint8)
    if mask.any():
        edge = mask & ~ndi.binary_erosion(mask, np.ones((3, 3)))
        rgb[mask] = (0.5 * rgb[mask] + 0.5 * np.array(BLUE)).astype(np.uint8)
        rgb[edge] = np.array(BLUE, np.uint8)
    if cej_row is not None and 0 <= cej_row < rgb.shape[0]:
        rgb[cej_row, ::2] = np.array(CEJ, np.uint8)
    h, w = bg.shape
    return Image.fromarray(rgb, "RGB").resize((w * SCALE, h * SCALE), Image.NEAREST)


def load_tooth(v, split_dir, uni, want_neighbours=False):
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    roi = v.data.astype(np.float32)
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
        if want_neighbours:
            nb = (arr[sl] > 0) & (arr[sl] != best)
            return arch, roi[sl], ms, nb
        return arch, roi[sl], ms
    raise SystemExit(f"tooth {uni} not found in {split_dir}/split.json")


def crown_axials(solid, z_cej, z_tip, n=N_AXIAL):
    """Axial levels spanning the whole crown, tip first, CEJ last.

    Spanning only the cervical third is what hid the missing cusps.
    """
    if z_cej is None:
        zs = np.where(solid.any(axis=(1, 2)))[0]
        return np.linspace(zs.min(), zs.max(), n).astype(int)
    return np.linspace(z_tip, z_cej, n).astype(int)


def sheet(v, split_dir, outdir, uni, cuts):
    sp = np.array(v.spacing, float)
    vox = float(np.prod(sp))
    arch, sub, solid, nbrs = load_tooth(v, split_dir, uni, want_neighbours=True)
    tooth_mm3 = float(solid.sum()) * vox
    env_mm, z_cej, z_tip, ring = EN.envelope(solid, arch, uni, sp)
    depth = EN.outer_depth(solid, nbrs, sp)
    env = solid & (depth <= env_mm) & (env_mm > 0)
    panels = []
    for cut in cuts:
        cap, info = EN.enamel_mask(sub, solid, arch, uni, sp, margin_hu=cut,
                                   neighbours=nbrs)
        cy, cx = ((int(x) for x in ndi.center_of_mass(cap)[1:]) if cap.any()
                  else (solid.shape[1] // 2, solid.shape[2] // 2))
        cy, cx = int(cy), int(cx)
        ry, rx = bbox2d(solid[:, cy, :]), bbox2d(solid[:, :, cx])
        crow = None if z_cej is None else z_cej - ry[0].start
        ccol = None if z_cej is None else z_cej - rx[0].start
        row = [tile(grey(sub[:, cy, :][ry]), cap[:, cy, :][ry],
                    env[:, cy, :][ry], crow),
               tile(grey(sub[:, :, cx][rx]), cap[:, :, cx][rx],
                    env[:, :, cx][rx], ccol)]
        ax = bbox2d(solid.any(axis=0))
        for z in crown_axials(solid, z_cej, z_tip):
            row.append(tile(grey(sub[z][ax]), cap[z][ax], env[z][ax]))
        mm3 = float(cap.sum()) * vox
        panels.append((cut, mm3, 100 * mm3 / max(tooth_mm3, 1e-6), info, row))
    wmax = max(p.width for *_, r in panels for p in r)
    hmax = max(p.height for *_, r in panels for p in r)
    cols = max(len(r) for *_, r in panels)
    img = Image.new("RGB", (cols * (wmax + PAD) + 175,
                            len(panels) * (hmax + PAD) + PAD + 30), (18, 18, 20))
    dr = ImageDraw.Draw(img)
    ttype = EN.tooth_type(uni)
    dr.text((4, 3), f"tooth {uni} ({arch}, {ttype})  {tooth_mm3:.0f} mm3   "
                    f"envelope {EN.MAX_DEPTH_MM[ttype]:.1f} mm at the tip -> "
                    f"{EN.CEJ_DEPTH_MM:.2f} mm at the CEJ", fill=EDGE)
    scal = "" if ring is None else f"   CEJ scallop {ring[1].max()-ring[1].min():.2f} mm"
    dr.text((4, 16), "blue = enamel   amber = envelope limit   red dashes = mean CEJ"
                     f"   |   long. x2, then crown axials tip -> CEJ{scal}",
            fill=(150, 150, 150))
    for i, (cut, mm3, pct, info, row) in enumerate(panels):
        y = PAD + 30 + i * (hmax + PAD)
        dr.text((4, y + 4), f"+{cut:.0f} HU", fill=(255, 220, 120))
        dr.text((4, y + 18), f"over dentin", fill=(150, 150, 150))
        dr.text((4, y + 34), f"{mm3:.1f} mm3", fill=(200, 200, 200))
        dr.text((4, y + 48), f"{pct:.1f}% of tooth", fill=(160, 160, 160))
        if info.get("cut"):
            dr.text((4, y + 64), f"cut {info['cut']:.0f} HU", fill=(130, 130, 130))
        for j, p in enumerate(row):
            img.paste(p, (175 + j * (wmax + PAD), y))
    out = os.path.join(outdir, f"enamel-tune-{uni:02d}.png")
    img.save(out)
    print(f"tooth {uni} ({arch}, {ttype}) {tooth_mm3:.0f} mm3 -> {out}")
    for cut, mm3, pct, info, _ in panels:
        print(f"  +{cut:5.0f} HU  cut {info.get('cut', 0):6.0f}  "
              f"{mm3:7.1f} mm3  {pct:5.1f}% of tooth")
    return [dict(universal=uni, arch=arch, type=ttype, cut_over_dentin=cut,
                 dentin_ref=info.get("dentin_ref"), abs_cut=info.get("cut"),
                 enamel_mm3=round(mm3, 2), tooth_mm3=round(tooth_mm3, 1),
                 enamel_pct=round(pct, 2))
            for cut, mm3, pct, info, _ in panels]


def main():
    vol_path, split_dir, outdir, which = sys.argv[1:5]
    cuts = [float(x) for x in sys.argv[5:]] or list(CUTS)
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)          # loaded ONCE; it is 185 MB
    if which == "all":
        rep = json.load(open(os.path.join(split_dir, "split.json")))
        unis = sorted(t["universal"] for a in ("upper", "lower")
                      for t in rep[a]["teeth"])
    else:
        unis = [int(x) for x in which.split(",")]
    rows = []
    for u in unis:
        rows += sheet(v, split_dir, outdir, u, cuts)
    json.dump(rows, open(os.path.join(outdir, "enamel-tune.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
