#!/usr/bin/env python3
"""Export slices for the operator to shade by hand, and read them back.

Threshold-picking answers "how much radiolucency counts". It cannot answer
"where exactly is the pulp", and for a multi-canal molar that is the harder
question. This exports plain greyscale slices with a sidecar describing exactly
how each pixel maps back to a voxel, so the answer can be painted rather than
described.

  export   writes NN_zNNN.png plus shade.json
  import   reads the painted PNGs back into a mask and reports what changed

To shade: open the PNGs in any editor, paint the pulp in PURE RED (255, 0, 0),
save as PNG. Do not resize, rotate or crop -- the mapping is by pixel position.
Anything that is not pure red is ignored, so pencilled notes in another colour
are safe.

Usage:
  python3 tools/cbct/shade_kit.py export <volume.nrrd> <split-dir> <universal> <out-dir>
  python3 tools/cbct/shade_kit.py import <shade-dir> <out.npy>
"""
import json
import os
import struct
import sys
import zlib

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume

SCALE = 8           # display pixels per voxel; big enough to paint accurately
N_SLICES = 14

# WHOLE-DENTITION HAND SHADING.
# Automatic segmentation was tried at length and could not reliably tell pulp
# from dentin on this scan -- molars lost whole roots, anteriors ran red to the
# incisal edge. The operator identifies it correctly by eye, so the model is
# built from their tracing instead, and the automatic route is not the fallback:
# it is abandoned for the chamber.
#
# The cost is their time, so the slice count per tooth is kept low and the gaps
# are filled by SIGNED-DISTANCE INTERPOLATION, which morphs one shaded outline
# into the next rather than stacking them. That is exact where they shaded and
# smooth in between, and it means a canal needs only a few marks down its length
# instead of one per voxel.
SLICES_PER_TOOTH = 10

# HOW EACH TOOTH IS TRACED, AND WHY IT DIFFERS.
# Two things were measured against the operator's own tooth-14 tracing and
# against known 3-D pulp, before asking them to trace 28 teeth:
#
#   Sparse AXIAL tracing cannot reconstruct a canal. Traced slices sit ~1.6 mm
#   apart and a 1-2 voxel canal wanders laterally by more than its own width in
#   that distance, so consecutive outlines do not overlap. Leave-one-out scored
#   Dice 0.076, and 0.274 even after aligning outlines on their centroids, with
#   the canal in 25 pieces. Tracing every slice would be ~1500 images.
#
#   LONGITUDINAL tracing in two perpendicular planes rebuilds a single-canal
#   tooth well -- Dice 0.79-0.89 on teeth 9 and 24, one component -- because the
#   canal is one continuous stroke in each view. It FAILS on a molar (Dice 0.55,
#   volume 2-3x too large): two silhouettes cannot say which canal is which, so
#   the intersection invents phantom canals where different ones cross.
#
# Hence: single-canal teeth are traced in two perpendicular longitudinal planes;
# multi-rooted teeth get one longitudinal plane PER ROOT, which contains that
# root's canal and so cannot produce a phantom, plus a few axial slices for the
# chamber, whose shape the longitudinal views alone do not pin down.
SINGLE_CANAL = frozenset((6, 7, 8, 9, 10, 11, 20, 21, 22, 23, 24, 25, 26, 27,
                          28, 29, 4, 13))
CHAMBER_AXIALS = 3


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\0" + rgb[y].tobytes() for y in range(h))
    def chunk(t, d):
        return (struct.pack(">I", len(d)) + t + d
                + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    open(path, "wb").write(png)


def read_png(path):
    d = open(path, "rb").read()
    pos, w, h, idat = 8, None, None, b""
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        body = d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", body[:10])
            if bd != 8 or ct not in (2, 6):
                raise SystemExit(f"{path}: need 8-bit RGB or RGBA, got bd={bd} ct={ct}")
            nch = 3 if ct == 2 else 4
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    stride = w * nch
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.int32)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = np.frombuffer(raw[p:p + stride], np.uint8).astype(np.int32).copy()
        p += stride
        if f == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 255
        elif f == 2:
            line = (line + prev) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                cc = prev[i - nch] if i >= nch else 0
                pa, pb, pc = abs(prev[i] - cc), abs(a - cc), abs(a + prev[i] - 2 * cc)
                pr = a if (pa <= pb and pa <= pc) else (prev[i] if pb <= pc else cc)
                line[i] = (line[i] + pr) & 255
        # keep prev as int32: the Paeth predictor subtracts these values and
        # uint8 wraps, silently corrupting every row that uses filter 4
        prev = line
        out[y] = line.astype(np.uint8)
    return out.reshape(h, w, nch)[:, :, :3]


def locate(v, split_dir, universal):
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    for arch in ("upper", "lower"):
        for t in rep[arch]["teeth"]:
            if t["universal"] != universal:
                continue
            arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
            ids = list(range(1, int(arr.max()) + 1))
            cents = ndi.center_of_mass(arr > 0, arr, ids)
            boxes = ndi.find_objects(arr)
            best = min(ids, key=lambda s: float(np.hypot(
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[0] - t["world"][0],
                v.world(cents[s - 1][2], cents[s - 1][1], cents[s - 1][0])[1] - t["world"][1])))
            box = boxes[best - 1]
            pad = 10
            sl = tuple(slice(max(0, b.start - pad), min(n, b.stop + pad))
                       for b, n in zip(box, arr.shape))
            m = np.zeros(tuple(x.stop - x.start for x in sl), bool)
            m[tuple(slice(b.start - x.start, b.stop - x.start)
                    for b, x in zip(box, sl))] = arr[box] == best
            return arch, t, sl, m
    raise SystemExit(f"tooth {universal} not found")


def do_export(vol_path, split_dir, universal, outdir):
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    arch, t, sl, m = locate(v, split_dir, universal)
    sub = v.data[sl].astype(np.float32)
    zs = np.where(m.any(axis=(1, 2)))[0]
    picks = np.linspace(zs.min(), zs.max(), N_SLICES).astype(int)
    meta = dict(universal=universal, fma=t["fma"], arch=arch, scale=SCALE,
                crop_origin_zyx=[int(x.start) for x in sl],
                shape_zyx=[int(x.stop - x.start) for x in sl],
                spacing_mm=float(v.spacing[0]),
                instructions="Paint pulp in PURE RED (255,0,0). Do not resize or "
                             "crop. Other colours are ignored.",
                slices=[])
    for z in picks:
        g = np.clip((sub[z] + 500) * 255 / 2600, 0, 255).astype(np.uint8)
        rgb = np.dstack([g, g, g])
        edge = m[z] ^ ndi.binary_erosion(m[z])
        rgb[edge] = (60, 130, 200)          # tooth outline, for orientation only
        big = np.repeat(np.repeat(rgb, SCALE, 0), SCALE, 1)
        name = f"{universal:02d}_z{int(z):03d}.png"
        write_png(os.path.join(outdir, name), big)
        meta["slices"].append(dict(file=name, z=int(z)))
    with open(os.path.join(outdir, "shade.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"tooth {universal} ({t['fma']}, {arch}) -> {outdir}")
    print(f"  {len(picks)} slices at {SCALE}x, {meta['shape_zyx'][1]*SCALE}x"
          f"{meta['shape_zyx'][2]*SCALE} px each")
    print("  paint pulp PURE RED (255,0,0), save as PNG, keep the filenames")


def interpolate_stack(shaded, shape):
    """Fill between traced slices, following the pulp's POSITION as well as its
    shape.

    Plain signed-distance morphing fails here and it is worth saying why: traced
    slices sit ~1.6 mm apart and a canal WANDERS laterally between them, so the
    two outlines being morphed often do not overlap at all. Interpolating their
    distance fields in place then produces something between two disjoint blobs
    -- a leave-one-out test against the operator's own tooth-14 tracing scored
    Dice 0.076 and left 15 disconnected pieces.

    Aligning the outlines on their centroids first, morphing the shape, and then
    translating the result along the centroid path fixes it: the shape morphs and
    the position slides, which is what a canal actually does.
    """
    out = np.zeros(shape, bool)
    zs = sorted(shaded)
    if not zs:
        return out
    for z in zs:
        out[z] = shaded[z]

    def sdf(m):
        if not m.any():
            return None
        if m.all():
            return np.full(m.shape, -50.0, np.float32)
        return (ndi.distance_transform_edt(~m).astype(np.float32)
                - ndi.distance_transform_edt(m).astype(np.float32))

    for a, b in zip(zs, zs[1:]):
        if b - a <= 1:
            continue
        ma, mb = shaded[a], shaded[b]
        if not ma.any() or not mb.any():
            continue                      # a canal that starts or ends here
        ca = np.array(ndi.center_of_mass(ma))
        cb = np.array(ndi.center_of_mass(mb))
        # bring both outlines to a common centre before morphing
        aa = ndi.shift(ma.astype(np.float32), -(ca - cb) / 2.0, order=0) > 0.5
        bb = ndi.shift(mb.astype(np.float32), (ca - cb) / 2.0, order=0) > 0.5
        da, db = sdf(aa), sdf(bb)
        if da is None or db is None:
            continue
        for z in range(a + 1, b):
            t = (z - a) / (b - a)
            blend = ((1.0 - t) * da + t * db) < 0.0
            # slide it to where the pulp actually is at this level
            centre = ca + (cb - ca) * t
            mid = (ca + cb) / 2.0
            out[z] = ndi.shift(blend.astype(np.float32),
                               centre - mid, order=0) > 0.5
    return out


def do_import(shade_dir, out_npy):
    meta = json.load(open(os.path.join(shade_dir, "shade.json")))
    sc = meta["scale"]
    mask = np.zeros(meta["shape_zyx"], bool)
    painted = 0
    for s in meta["slices"]:
        p = os.path.join(shade_dir, s["file"])
        if not os.path.exists(p):
            continue
        rgb = read_png(p)
        red = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 80) & (rgb[:, :, 2] < 80)
        if not red.any():
            continue
        # average the SCALE x SCALE block back down to one voxel
        h, w = red.shape[0] // sc, red.shape[1] // sc
        blk = red[:h * sc, :w * sc].reshape(h, sc, w, sc).mean(axis=(1, 3))
        mask[s["z"], :h, :w] = blk > 0.5
        painted += 1
    shaded = {s["z"]: mask[s["z"]] for s in meta["slices"]
              if os.path.exists(os.path.join(shade_dir, s["file"]))}
    full = interpolate_stack(shaded, tuple(meta["shape_zyx"]))
    np.save(out_npy, full)
    vox = meta["spacing_mm"] ** 3
    print(f"{painted} of {len(meta['slices'])} slices had shading; "
          f"{mask.sum() * vox:.1f} mm3 on those slices, "
          f"{full.sum() * vox:.1f} mm3 after interpolation")
    print(f"-> {out_npy}   (crop origin {meta['crop_origin_zyx']}, "
          f"tooth {meta['universal']})")
    return full


def do_export_all(vol_path, split_dir, outdir, n_slices=SLICES_PER_TOOTH):
    """One folder per tooth, plus a map showing where each slice sits."""
    global N_SLICES
    N_SLICES = n_slices
    v = Volume.load(vol_path)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    os.makedirs(outdir, exist_ok=True)
    order = []
    for arch in ("upper", "lower"):
        for t in rep[arch]["teeth"]:
            order.append(t["universal"])
    for u in sorted(order):
        sub = os.path.join(outdir, f"tooth-{u:02d}")
        do_export(vol_path, split_dir, u, sub)
        _write_slice_map(v, split_dir, u, sub)
    with open(os.path.join(outdir, "README.txt"), "w") as f:
        f.write(SHADE_README.format(n=n_slices, total=len(order) * n_slices))
    print(f"\n{len(order)} teeth exported to {outdir}")


def _write_slice_map(v, split_dir, universal, outdir):
    """A longitudinal view with the exported slice levels drawn on it."""
    arch, t, sl, m = locate(v, split_dir, universal)
    sub = v.data[sl].astype(np.float32)
    meta = json.load(open(os.path.join(outdir, "shade.json")))
    cy = int(np.argmax(m.sum(axis=(0, 2))))
    g = np.clip((sub[:, cy, :] + 500) * 255 / 2600, 0, 255).astype(np.uint8)
    rgb = np.dstack([g, g, g])
    for s in meta["slices"]:
        rgb[s["z"], :, 0] = 255
        rgb[s["z"], :, 1] = 200
        rgb[s["z"], :, 2] = 60
    big = np.repeat(np.repeat(rgb, 4, 0), 4, 1)
    write_png(os.path.join(outdir, "_slice-map.png"), big)


def do_import_all(shade_root, outdir):
    os.makedirs(outdir, exist_ok=True)
    done = []
    for name in sorted(os.listdir(shade_root)):
        d = os.path.join(shade_root, name)
        if not os.path.isdir(d) or not os.path.exists(os.path.join(d, "shade.json")):
            continue
        meta = json.load(open(os.path.join(d, "shade.json")))
        out = os.path.join(outdir, f"{meta['fma']}-pulp.npy")
        full = do_import(d, out)
        vox = meta["spacing_mm"] ** 3
        done.append((meta["universal"], meta["fma"], float(full.sum()) * vox,
                     meta["crop_origin_zyx"], list(full.shape), meta["arch"]))
    rec = {fma: dict(universal=u, arch=ar, pulp_mm3=round(mm, 2),
                     crop_origin_zyx=co, shape_zyx=sh,
                     provenance="HAND-TRACED by the operator on CBCT slices; "
                                "interpolated between traced slices",
                     foramina=[])
           for u, fma, mm, co, sh, ar in done}
    json.dump(dict(method="hand-traced", teeth=rec),
              open(os.path.join(outdir, "pulp-connect.json"), "w"), indent=2)
    print(f"\n{len(done)} teeth imported, "
          f"{sum(d[2] for d in done):.1f} mm3 total -> {outdir}")


SHADE_README = """HAND-TRACING THE PULP
=====================

One folder per tooth: tooth-NN/.  In each:

  NN_zNNN.png    {n} slices, crown -> apex, at 8x zoom.
                 Paint the pulp PURE RED (255, 0, 0).
  _slice-map.png A longitudinal view with the slice levels marked in
                 yellow, so you can see where each one sits.
  shade.json     The pixel-to-voxel mapping. Do not edit.

RULES
  - Pure red (255,0,0) only. Any other colour is ignored, so you can
    pencil notes in blue or green safely.
  - Do not resize, rotate or crop. The mapping is by pixel position.
  - Keep the filenames.
  - A slice with no pulp on it: leave it unpainted.

YOU DO NOT HAVE TO BE EXHAUSTIVE DOWN THE CANAL.
The gaps between traced slices are filled by interpolating the shape
from one to the next, so a canal needs its outline at a few levels,
not every level. Trace densely where the shape CHANGES (the chamber,
the furcation, a canal splitting) and sparsely where it just tapers.

{total} slices in total across 28 teeth. Do them in any order; import
handles whatever is finished.
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "export":
        do_export(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif sys.argv[1] == "import":
        do_import(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "export-all":
        do_export_all(sys.argv[2], sys.argv[3], sys.argv[4],
                      int(sys.argv[5]) if len(sys.argv) > 5 else SLICES_PER_TOOTH)
    elif sys.argv[1] == "import-all":
        do_import_all(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
