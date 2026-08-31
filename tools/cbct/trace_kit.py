#!/usr/bin/env python3
"""Export planes for the operator to trace the pulp on, one per root.

Automatic segmentation could not tell pulp from dentin reliably on this scan, so
the pulp is traced by hand. Two things were measured first, so that the tracing
is not wasted:

  Sparse AXIAL tracing cannot rebuild a canal. Slices ~1.6 mm apart, and a 1-2
  voxel canal wanders further than its own width between them, so consecutive
  outlines do not overlap: leave-one-out on the operator's tooth-14 tracing gave
  Dice 0.076, and 0.274 even with centroid-following interpolation.

  LONGITUDINAL tracing rebuilds a single-canal tooth well (Dice 0.79-0.89 on
  teeth 9 and 24) but fails on a molar (0.55, volume 2-3x too large), because
  two silhouettes cannot say which canal is which and invent phantoms where
  canals cross in projection.

So: one longitudinal plane PER ROOT, which contains that root's own canal and
therefore cannot produce a phantom, plus a few axial slices for the chamber.

The planes are CURVED REFORMATS. A real root bends, and a flat oblique cut loses
the canal halfway down; following the root's own centreline keeps the whole
canal in one image. Every pixel's exact (z, y, x) sample point is written to the
sidecar, so tracing maps back to voxels with no interpolation of position.

Usage: trace_kit.py export <vol.nrrd> <split-dir> <out-dir>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from shade_kit import write_png, read_png                  # noqa: E402
from pulp_connect import apical_roots                      # noqa: E402

SCALE = 6
HALF_WIDTH_MM = 3.2        # how far either side of the centreline to show
CHAMBER_AXIALS = 5
# Premolars are NOT single-canal for tracing purposes. Several carry two canals
# and all of them benefit from axial slices through the chamber, which the
# single-canal treatment did not produce. Where root detection finds only one
# root the geometry falls back to two perpendicular whole-tooth planes, which is
# exactly what they had before -- so tracings already done still apply.
SINGLE_CANAL = frozenset((6, 7, 8, 9, 10, 11, 22, 23, 24, 25, 26, 27))


def grey(a):
    return np.clip((a + 500) * 255 / 2600, 0, 255).astype(np.uint8)


def centreline(mask, zs):
    """Per-slice centroid, gaps filled, lightly smoothed."""
    ys, xs = [], []
    for z in zs:
        if mask[z].any():
            cy, cx = ndi.center_of_mass(mask[z])
        else:
            cy, cx = np.nan, np.nan
        ys.append(cy)
        xs.append(cx)
    ys, xs = np.array(ys, float), np.array(xs, float)
    for arr in (ys, xs):
        ok = ~np.isnan(arr)
        if ok.sum() < 2:
            arr[:] = mask.shape[1] / 2 if arr is ys else mask.shape[2] / 2
        else:
            arr[~ok] = np.interp(np.flatnonzero(~ok), np.flatnonzero(ok), arr[ok])
    k = max(int(len(zs) * 0.12) | 1, 3)
    ys = ndi.uniform_filter1d(ys, k)
    xs = ndi.uniform_filter1d(xs, k)
    return ys, xs


def reformat(sub, tooth, zs, ys, xs, direction, spacing, half_mm=HALF_WIDTH_MM):
    """Sample a curved plane: for each z, a line through (ys,xs) along `direction`."""
    dy, dx = direction
    n = int(round(half_mm / float(spacing[1])))
    ts = np.arange(-n, n + 1)
    img = np.zeros((len(zs), len(ts)), np.float32)
    inside = np.zeros_like(img, bool)
    coords = np.zeros((len(zs), len(ts), 3), np.float32)
    for i, z in enumerate(zs):
        yy = ys[i] + ts * dy
        xx = xs[i] + ts * dx
        pts = np.vstack([np.full(len(ts), z, float), yy, xx])
        img[i] = ndi.map_coordinates(sub, pts, order=1, mode="constant", cval=-500)
        inside[i] = ndi.map_coordinates(tooth.astype(np.float32), pts, order=1,
                                        mode="constant", cval=0.0) > 0.5
        coords[i, :, 0] = pts[0]
        coords[i, :, 1] = pts[1]
        coords[i, :, 2] = pts[2]
    return img, inside, coords


def emit(path, img, inside, scale=SCALE):
    g = grey(img)
    rgb = np.dstack([g, g, g])
    edge = inside ^ ndi.binary_erosion(inside)
    rgb[edge] = (60, 130, 200)
    big = np.repeat(np.repeat(rgb, scale, 0), scale, 1)
    write_png(path, big)


def do_axials(vol_path, split_dir, outdir, only=None, n=6, lo_f=0.45, hi_f=0.97):
    """Axial slices over a chosen span of the tooth, for tracing only.

    The longitudinal views map the chamber and the orifices well, but they thin
    out apically: a canal splitting or rejoining in the apical third shows in
    cross-section long before it separates in either longitudinal view. These
    slices are for exactly that -- 2:1 versus 2:2 is an axial question.
    """
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    os.makedirs(outdir, exist_ok=True)
    total = 0
    for arch in ("upper", "lower"):
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            num, fma = t["universal"], t["fma"]
            if only is not None and num not in only:
                continue
            tgt = np.array(t["world"][:2])
            best = min(ids, key=lambda s2: float(np.hypot(
                v.world(cents[s2 - 1][2], cents[s2 - 1][1], cents[s2 - 1][0])[0] - tgt[0],
                v.world(cents[s2 - 1][2], cents[s2 - 1][1], cents[s2 - 1][0])[1] - tgt[1])))
            box = boxes[best - 1]
            pad = 10
            sl = tuple(slice(max(0, b.start - pad), min(nn, b.stop + pad))
                       for b, nn in zip(box, arr.shape))
            m = np.zeros(tuple(x.stop - x.start for x in sl), bool)
            m[tuple(slice(b.start - x.start, b.stop - x.start)
                    for b, x in zip(box, sl))] = arr[box] == best
            ms = m.copy()
            for k in range(m.shape[0]):
                if m[k].any():
                    ms[k] = ndi.binary_fill_holes(m[k])
            sub = v.data[sl].astype(np.float32)
            zs = np.where(ms.any(axis=(1, 2)))[0]
            z0, z1 = int(zs.min()), int(zs.max())
            span = z1 - z0
            # measure the fractions from the CROWN, whichever end that is
            if arch == "upper":
                lo, hi = z0 + lo_f * span, z0 + hi_f * span
            else:
                lo, hi = z1 - hi_f * span, z1 - lo_f * span
            picks = np.linspace(lo, hi, n).astype(int)
            tdir = os.path.join(outdir, f"tooth-{num:02d}")
            os.makedirs(tdir, exist_ok=True)
            meta = dict(universal=num, fma=fma, arch=arch, scale=SCALE,
                        crop_origin_zyx=[int(x.start) for x in sl],
                        shape_zyx=[int(x.stop - x.start) for x in sl],
                        spacing_mm=float(sp[0]), planes=[], axials=[])
            for z in picks:
                g = grey(sub[z])
                rgb = np.dstack([g, g, g])
                edge = ms[z] ^ ndi.binary_erosion(ms[z])
                rgb[edge] = (60, 130, 200)
                big = np.repeat(np.repeat(rgb, SCALE, 0), SCALE, 1)
                name = f"{num:02d}_axial_z{int(z):03d}.png"
                write_png(os.path.join(tdir, name), big)
                meta["axials"].append(dict(file=name, z=int(z)))
                total += 1
            with open(os.path.join(tdir, "trace.json"), "w") as f:
                json.dump(meta, f)
            print(f"tooth {num:2d}: {len(picks)} axial slices "
                  f"z {picks.min()}-{picks.max()}")
    print(f"\n{total} images -> {outdir}")


def main():
    vol_path, split_dir, outdir = sys.argv[2:5]
    only = set(int(x) for x in sys.argv[5].split(",")) if len(sys.argv) > 5 else None
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    total = 0
    index = []
    for arch in ("upper", "lower"):
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            num, fma = t["universal"], t["fma"]
            if only is not None and num not in only:
                continue
            tgt = np.array(t["world"][:2])
            best = min(ids, key=lambda s: float(np.hypot(
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[0] - tgt[0],
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[1] - tgt[1])))
            box = boxes[best - 1]
            pad = 10
            sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                       for b, n in zip(box, arr.shape))
            m = np.zeros(tuple(x.stop - x.start for x in sl), bool)
            m[tuple(slice(b.start - x.start, b.stop - x.start)
                    for b, x in zip(box, sl))] = arr[box] == best
            ms = m.copy()
            for k in range(m.shape[0]):
                if m[k].any():
                    ms[k] = ndi.binary_fill_holes(m[k])
            sub = v.data[sl].astype(np.float32)
            tdir = os.path.join(outdir, f"tooth-{num:02d}")
            os.makedirs(tdir, exist_ok=True)
            meta = dict(universal=num, fma=fma, arch=arch, scale=SCALE,
                        crop_origin_zyx=[int(x.start) for x in sl],
                        shape_zyx=[int(x.stop - x.start) for x in sl],
                        spacing_mm=float(sp[0]), planes=[], axials=[])
            zs_all = np.where(ms.any(axis=(1, 2)))[0]

            if num in SINGLE_CANAL:
                targets = [("whole", ms)]
                dirs = [(1.0, 0.0), (0.0, 1.0)]
            else:
                roots = apical_roots(ms, arch, sp)
                targets = []
                for ri, r in enumerate(roots):
                    # extend the root's footprint up through the crown so the
                    # plane follows it all the way to the chamber
                    fp = r.any(axis=0)
                    col = ms & fp[None, :, :]
                    targets.append((f"root{ri + 1}", col))
                # TWO perpendicular planes per root, not one. A single view
                # gives the canal's width in one direction only, so the
                # cross-section had to be assumed circular; two give a real
                # ellipse. This is what the operator asked for after seeing the
                # first reconstruction.
                dirs = [(1.0, 0.0), (0.0, 1.0)]
                if len(targets) < 2:
                    # Root detection found one root on a tooth that has two
                    # canals (teeth 12 and 18). One plane cannot separate them,
                    # so fall back to the biplane treatment: two perpendicular
                    # views of the whole tooth.
                    targets = [("whole", ms)]
                    dirs = [(1.0, 0.0), (0.0, 1.0)]

            for label, region in targets:
                zs = np.where(region.any(axis=(1, 2)))[0]
                if zs.size < 5:
                    continue
                ys, xs = centreline(region, zs)
                for di, dvec in enumerate(dirs):
                    img, inside, coords = reformat(sub, ms, zs, ys, xs, dvec, sp)
                    name = f"{num:02d}_{label}_p{di + 1}.png"
                    emit(os.path.join(tdir, name), img, inside)
                    meta["planes"].append(dict(
                        file=name, label=label, direction=list(dvec),
                        z_list=[int(z) for z in zs],
                        coords=coords.round(3).tolist()))
                    total += 1

            if num not in SINGLE_CANAL:
                zc = np.linspace(zs_all.min(), zs_all.max(), 12).astype(int)
                pick = zc[1:6] if arch == "upper" else zc[6:11]
                for z in pick:
                    g = grey(sub[z])
                    rgb = np.dstack([g, g, g])
                    edge = ms[z] ^ ndi.binary_erosion(ms[z])
                    rgb[edge] = (60, 130, 200)
                    big = np.repeat(np.repeat(rgb, SCALE, 0), SCALE, 1)
                    name = f"{num:02d}_axial_z{int(z):03d}.png"
                    write_png(os.path.join(tdir, name), big)
                    meta["axials"].append(dict(file=name, z=int(z)))
                    total += 1

            with open(os.path.join(tdir, "trace.json"), "w") as f:
                json.dump(meta, f)
            index.append((num, len(meta["planes"]) + len(meta["axials"])))
            print(f"tooth {num:2d} ({'single' if num in SINGLE_CANAL else 'multi'}): "
                  f"{len(meta['planes'])} plane(s) + {len(meta['axials'])} axial")
    with open(os.path.join(outdir, "README.txt"), "w") as f:
        f.write(README.format(total=total))
    print(f"\n{total} images across {len(index)} teeth -> {outdir}")


def spans(red_row):
    """Contiguous runs of traced pixels in one row: (start, end) inclusive."""
    idx = np.flatnonzero(red_row)
    if not idx.size:
        return []
    brk = np.flatnonzero(np.diff(idx) > 1)
    out, start = [], idx[0]
    for b in brk:
        out.append((start, idx[b]))
        start = idx[b + 1]
    out.append((start, idx[-1]))
    return out


def read_plane(tdir, plane, scale):
    """Traced spans per z: list of (z, centre_yx, half_width_vox) in voxels.

    A longitudinal trace gives the pulp's extent along ONE direction at each
    level. That is a width and a position, not a cross-section -- the shape
    across the plane comes from the second view (single-canal teeth) or is taken
    as circular (one view per root).
    """
    f = os.path.join(tdir, plane["file"])
    if not os.path.exists(f):
        return []
    rgb = read_png(f)
    red = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 80) & (rgb[:, :, 2] < 80)
    coords = np.asarray(plane["coords"], np.float32)
    nz, nt = coords.shape[0], coords.shape[1]
    out = []
    for i in range(nz):
        row = red[i * scale:(i + 1) * scale]
        if not row.size:
            continue
        # MAJORITY, not ANY. Marking a voxel traced when any pixel in its
        # scale x scale block is red fattens every edge by up to a voxel on each
        # side; on a canal only a voxel or two wide that doubles the area, and
        # it put the single-canal teeth at 5.6-8.5% of tooth volume against a
        # 3-4% literature norm while the per-root teeth, whose canals are drawn
        # from one view, came out correct.
        col = (row.reshape(scale, -1, scale).mean(axis=(0, 2)) > 0.5)[:nt]
        for a, b in spans(col):
            c = 0.5 * (a + b)
            half = 0.5 * (b - a) + 0.5
            lo = coords[i, int(np.floor(c))]
            hi = coords[i, min(int(np.ceil(c)), nt - 1)]
            centre = 0.5 * (lo + hi)
            out.append((float(centre[0]), centre[1:], float(half)))
    return out


def rasterise(shape, samples, spacing):
    """Draw each traced level as a disc (one view) or ellipse (two views)."""
    out = np.zeros(shape, bool)
    yy, xx = np.mgrid[0:shape[1], 0:shape[2]]
    for z, centre, ry, rx in samples:
        zi = int(round(z))
        if zi < 0 or zi >= shape[0]:
            continue
        dy = (yy - centre[0]) / max(ry, 0.5)
        dx = (xx - centre[1]) / max(rx, 0.5)
        out[zi] |= (dy * dy + dx * dx) <= 1.0
    return out


def do_import(trace_root, outdir):
    os.makedirs(outdir, exist_ok=True)
    rec = {}
    for name in sorted(os.listdir(trace_root)):
        tdir = os.path.join(trace_root, name)
        jf = os.path.join(tdir, "trace.json")
        if not os.path.isdir(tdir) or not os.path.exists(jf):
            continue
        meta = json.load(open(jf))
        shape = tuple(meta["shape_zyx"])
        scale = meta["scale"]
        mask = np.zeros(shape, bool)

        # group planes by the region they were cut for
        by_label = {}
        for pl in meta["planes"]:
            by_label.setdefault(pl["label"], []).append(pl)

        for label, pls in by_label.items():
            traced = [read_plane(tdir, pl, scale) for pl in pls]
            if len(pls) == 2 and all(traced):
                # two perpendicular views: combine into an ellipse per level
                d0 = np.asarray(pls[0]["direction"], float)
                d1 = np.asarray(pls[1]["direction"], float)
                per0 = {}
                for z, c, h in traced[0]:
                    per0.setdefault(int(round(z)), []).append((c, h))
                samples = []
                for z, c1, h1 in traced[1]:
                    zi = int(round(z))
                    if zi not in per0:
                        continue
                    c0, h0 = min(per0[zi],
                                 key=lambda ch: float(np.linalg.norm(ch[0] - c1)))
                    centre = 0.5 * (c0 + c1)
                    ry = h0 if abs(d0[0]) > abs(d0[1]) else h1
                    rx = h1 if abs(d0[0]) > abs(d0[1]) else h0
                    samples.append((z, centre, ry, rx))
                mask |= rasterise(shape, samples, meta["spacing_mm"])
            else:
                for tr in traced:
                    mask |= rasterise(
                        shape, [(z, c, h, h) for z, c, h in tr],
                        meta["spacing_mm"])

        # axial chamber tracings map straight back, no assumption needed
        for ax in meta["axials"]:
            f = os.path.join(tdir, ax["file"])
            if not os.path.exists(f):
                continue
            rgb = read_png(f)
            red = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 80) & (rgb[:, :, 2] < 80)
            h, w = shape[1], shape[2]
            blk = red[:h * scale, :w * scale].reshape(h, scale, w, scale)
            mask[ax["z"]] |= blk.mean(axis=(1, 3)) > 0.5

        # JOIN THE ROOTS AT THE CHAMBER.
        # Each root's canal was traced in its own plane, so they arrive as
        # separate pieces -- teeth 2 and 3 came in 7 and 9 of them. They meet at
        # the chamber in life, and the traced axials show that, but only one of
        # the three axial slices per tooth carries a tracing. Connect each piece
        # to the largest along a straight run between their nearest points,
        # which is short because they all converge at the chamber floor.
        lab, n = ndi.label(mask, structure=ndi.generate_binary_structure(3, 1))
        if n > 1:
            sizes = ndi.sum(mask, lab, range(1, n + 1))
            main = int(np.argmax(sizes)) + 1
            base = np.argwhere(lab == main)
            for i in range(1, n + 1):
                if i == main:
                    continue
                pts = np.argwhere(lab == i)
                d2 = ((pts[:, None, :] - base[None, :, :]) ** 2).sum(-1)
                a, b = np.unravel_index(int(np.argmin(d2)), d2.shape)
                p0, p1 = pts[a].astype(float), base[b].astype(float)
                steps = max(int(np.linalg.norm(p1 - p0) * 2), 2)
                for t in np.linspace(0, 1, steps):
                    q = np.round(p0 + (p1 - p0) * t).astype(int)
                    q = np.clip(q, 1, np.array(shape) - 2)
                    # a 3x3x3 stamp, not a single voxel: a one-voxel diagonal
                    # line is not FACE connected, so it joins nothing and simply
                    # adds more pieces (tooth 2 went from 7 to 36). Rule 18.
                    mask[q[0] - 1:q[0] + 2,
                         q[1] - 1:q[1] + 2,
                         q[2] - 1:q[2] + 2] = True
            mask = ndi.binary_closing(mask, np.ones((3, 3, 3)))

        vox = meta["spacing_mm"] ** 3
        np.save(os.path.join(outdir, f"{meta['fma']}-pulp.npy"), mask)
        rec[meta["fma"]] = dict(universal=meta["universal"], arch=meta["arch"],
                                pulp_mm3=round(float(mask.sum()) * vox, 2),
                                crop_origin_zyx=meta["crop_origin_zyx"],
                                shape_zyx=list(shape),
                                provenance="HAND-TRACED on CBCT reformats",
                                foramina=[])
        print(f"tooth {meta['universal']:2d}: {mask.sum() * vox:6.1f} mm3 "
              f"from {len(meta['planes'])} plane(s) + {len(meta['axials'])} axial")
    json.dump(dict(method="hand-traced", teeth=rec),
              open(os.path.join(outdir, "pulp-connect.json"), "w"), indent=2)
    print(f"\n{len(rec)} teeth, {sum(r['pulp_mm3'] for r in rec.values()):.1f} mm3")


README = """TRACING THE PULP BY HAND
========================

{total} images, one folder per tooth.  Paint the pulp PURE RED (255, 0, 0),
save as PNG, keep the filename.  Any other colour is ignored, so pencil
notes in blue or green are safe.  Do not resize, rotate or crop.

WHAT THE FILES ARE

  NN_whole_p1.png / _p2.png     single-canal teeth: two perpendicular
                                longitudinal views of the whole tooth.
                                Trace the pulp outline in both.

  NN_root1_p1.png, root2, ...   multi-rooted teeth: ONE view per root,
                                cut along that root's own centreline so
                                the whole canal stays in the picture even
                                where the root bends.  Trace only the
                                canal belonging to THAT root.

  NN_axial_zNNN.png             multi-rooted teeth: three axial slices
                                through the chamber.  Trace the chamber
                                outline.  These fix the chamber's shape,
                                which the longitudinal views alone cannot.

  trace.json                    the pixel-to-voxel mapping.  Do not edit.

NOTES

  The blue outline is the tooth surface, drawn for orientation only --
  do not trace it.

  In a longitudinal view the canal is the dark line running down the
  middle; it is normal for it to fade near the apex.  Trace it as far as
  you can actually see it and stop.  Where it fades is itself useful
  information.

  A curved reformat can look slightly odd near the crown, where the
  centreline swings; the geometry is still exact.

ORIENTATION
  Images run along the volume's z axis, top to bottom.  For UPPER teeth
  that puts the crown at the TOP and the apex at the bottom; for LOWER
  teeth it is the other way round -- crown at the BOTTOM.  The bright
  mass at the crown end of teeth 19, 20, 29 and 30 is a restoration.

WHERE THE MODEL IS LEAST TRUSTWORTHY
  19 and 30 carry large metal restorations (340 and 273 mm3, saturated
  at the scanner ceiling) and metal throws a dark halo that looks like a
  lumen.  If the coronal pulp is unreadable on those, leave it untraced
  and say so -- an honest gap beats a guess.
"""


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    if sys.argv[1] == "export":
        main()
    elif sys.argv[1] == "import":
        do_import(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "axials":
        only = set(int(x) for x in sys.argv[5].split(",")) if len(sys.argv) > 5 else None
        n = int(sys.argv[6]) if len(sys.argv) > 6 else 6
        lo = float(sys.argv[7]) if len(sys.argv) > 7 else 0.45
        hi = float(sys.argv[8]) if len(sys.argv) > 8 else 0.97
        do_axials(sys.argv[2], sys.argv[3], sys.argv[4], only, n, lo, hi)
    else:
        raise SystemExit(__doc__)
