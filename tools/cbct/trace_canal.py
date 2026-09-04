#!/usr/bin/env python3
"""Export cross-sections for the operator to trace a CANAL on, and read them back.

Same reason as the pulp, and the same answer. Five automatic detectors were
written for the infraorbital canal and the nasolacrimal ducts and every one
failed, each in its own way -- interior voids find air, enclosure fails on a
through-canal, a narrow-width band leaks into the shell around every cavity,
ring closure needs a cortex that does not close at any single threshold, and a
soft-tissue band is the wrong tissue entirely for a duct that carries air. The
structures are plainly visible on the images throughout. So they get traced, and
trace_kit.py's precedent applies: if one is wrong afterwards, the TRACING is
what changes.

Shared with trace_kit deliberately, so tracing feels identical: the same RED
(r>180, g<80, b<80), the same majority rule at import, and a sidecar that maps
every pixel back to an exact sample point with no interpolation of position.

CROSS-SECTIONS, not longitudinal planes, and the difference matters twice.
A longitudinal reformat only works if the plane really contains the canal, so it
inherits every error in the prior axis -- and the priors here range from a solid
measured component to a mirror of the opposite side. A cross-section is
recognisable on its own: a canal is a round hole, and if the prior is a few
millimetres off the hole is simply off-centre in the tile rather than absent.

trace_kit warns that sparse AXIAL tracing cannot rebuild a canal -- 1.6 mm apart,
consecutive outlines of a wandering canal do not overlap, and leave-one-out gave
Dice 0.076. That warning does not carry here, for two reasons: these sections
are PERPENDICULAR to the canal's own axis rather than axial, so they cannot be
cut obliquely by its course, and they are one millimetre apart on a canal three
to five millimetres across, so consecutive outlines overlap heavily.

Geometry is sampled in the MAXILLARY exposure's own grid, which is the exposure
that measured this region -- the centred volume's reconstruction ceiling sits a
few millimetres above the infraorbital canal. Vertices are carried into the
atlas frame afterwards, never voxels (rule 113).

Usage: trace_canal.py export <vol.nrrd> <priors.json> <out-dir>
       trace_canal.py import <vol.nrrd> <trace-dir> <out-dir>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from shade_kit import write_png, read_png                  # noqa: E402

SCALE = 3
STEP_MM = 1.0              # between cross-sections, along the canal axis
MARGIN_MM = 4.0            # extend past the prior at both ends
HALF_MM = 8.0              # context shown either side of the prior axis
COLS = 5
GAP = 8
WIN_HU = (-500.0, 1500.0)


def grey(a):
    lo, hi = WIN_HU
    return (np.clip((a - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


def frame(axis):
    a = np.asarray(axis, float); a /= np.linalg.norm(a)
    ref = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(a, ref)) > 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    u = np.cross(a, ref); u /= np.linalg.norm(u)
    w = np.cross(a, u);   w /= np.linalg.norm(w)
    return a, u, w


def resample(pts, step_mm):
    pts = np.asarray(pts, float)
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    if d[-1] < 1e-6:
        return pts[:1]
    t = np.arange(0.0, d[-1] + 1e-6, step_mm)
    return np.stack([np.interp(t, d, pts[:, i]) for i in range(3)], axis=1)


def smooth_path(pts, passes=4):
    p = np.asarray(pts, float).copy()
    for _ in range(passes):
        if len(p) < 3:
            break
        p[1:-1] = 0.25 * p[:-2] + 0.5 * p[1:-1] + 0.25 * p[2:]
    return p


def extend(pts, margin_mm, step_mm):
    """Run the path on past both ends along its own end tangents."""
    pts = np.asarray(pts, float)
    if len(pts) < 2 or margin_mm <= 0:
        return pts
    n = max(1, int(round(margin_mm / step_mm)))
    a = pts[0] - pts[min(3, len(pts) - 1)]
    a /= max(np.linalg.norm(a), 1e-9)
    b = pts[-1] - pts[max(-4, -len(pts))]
    b /= max(np.linalg.norm(b), 1e-9)
    pre = pts[0] + a * (np.arange(n, 0, -1) * step_mm)[:, None]
    post = pts[-1] + b * (np.arange(1, n + 1) * step_mm)[:, None]
    return np.vstack([pre, pts, post])


def transported_frames(path):
    """A (tangent, u, w) frame per sample that does not SPIN along the path.

    Rebuilding `frame()` independently at each sample gives each tile its own
    arbitrary rotation about the axis, so consecutive sections of the same canal
    appear rotated with respect to one another and the operator has to re-orient
    on every tile. Parallel transport carries one frame along the curve instead,
    rotating it by the minimum needed to stay perpendicular, so the sheet reads
    as a single object turning slowly.
    """
    t = np.gradient(np.asarray(path, float), axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    _, u0, _ = frame(t[0])
    out = []
    u = u0
    for i in range(len(t)):
        u = u - t[i] * float(u @ t[i])            # re-perpendicularise
        n = np.linalg.norm(u)
        u = (u / n) if n > 1e-9 else frame(t[i])[1]
        w = np.cross(t[i], u)
        out.append((t[i], u, w))
    return out


def section(v, centre, u, w, half_mm, step):
    """One plane perpendicular to the canal, sampled nearest-neighbour."""
    ss = np.arange(-half_mm, half_mm + 1e-6, step)
    n = len(ss)
    P = (np.asarray(centre, float)[None, None, :]
         + w[None, None, :] * ss[:, None, None]
         + u[None, None, :] * ss[None, :, None])
    zi = np.clip(np.round((P[..., 2] - v.origin[2]) / v.spacing[2]).astype(int),
                 0, v.data.shape[0] - 1)
    yi = np.clip(np.round((P[..., 1] - v.origin[1]) / v.spacing[1]).astype(int),
                 0, v.data.shape[1] - 1)
    xi = np.clip(np.round((P[..., 0] - v.origin[0]) / v.spacing[0]).astype(int),
                 0, v.data.shape[2] - 1)
    return v.data[zi, yi, xi].astype(np.float32), n


def do_export(vol_path, priors_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    step = float(v.spacing[0])
    priors = json.load(open(priors_path))
    meta = {}
    for name, pr in priors.items():
        if pr is None:
            continue
        half = float(pr.get('half_mm', HALF_MM))
        scale = int(pr.get('scale', SCALE))
        margin = float(pr.get('margin_mm', MARGIN_MM))
        # A CURVED prior when one is given, a straight axis when it is not.
        #
        # A straight chord is only as good as the canal is straight, and the
        # mental canal is not: the operator's own tracing runs 33.9 mm along a
        # 23.1 mm chord. Sections cut perpendicular to that chord meet the real
        # canal obliquely at both ends, which turns a round hole into a smear
        # through trabecular bone -- exactly the thing that made the first
        # sheets hard to read. Given a path, each section is cut perpendicular
        # to the LOCAL tangent instead.
        if pr.get('path'):
            core = smooth_path(resample(np.asarray(pr['path'], float), STEP_MM), 6)
            path = extend(core, margin, STEP_MM)
            frames = transported_frames(path)
            ts = np.concatenate([[0.0], np.cumsum(
                np.linalg.norm(np.diff(path, axis=0), axis=1))]) - margin
        else:
            p0 = np.asarray(pr['p0'], float); p1 = np.asarray(pr['p1'], float)
            a, u, w = frame(p1 - p0)
            L = float(np.linalg.norm(p1 - p0))
            ts = np.arange(-margin, L + margin + 1e-6, STEP_MM)
            path = p0[None, :] + a[None, :] * ts[:, None]
            frames = [(a, u, w)] * len(ts)
        tiles, recs = [], []
        for c, (a, u, w), t in zip(path, frames, ts):
            img, n = section(v, c, u, w, half, step)
            tiles.append(img)
            recs.append(dict(t=round(float(t), 3),
                             centre=[round(float(q), 4) for q in c],
                             u=[round(float(q), 6) for q in u],
                             w=[round(float(q), 6) for q in w],
                             n=int(n)))
        th, tw = tiles[0].shape
        rows = (len(tiles) + COLS - 1) // COLS
        H = rows * (th * scale + GAP) + GAP
        W = COLS * (tw * scale + GAP) + GAP
        sheet = np.zeros((H, W, 3), np.uint8)
        sheet[:] = (18, 18, 20)
        for k, img in enumerate(tiles):
            g = grey(img)
            big = np.repeat(np.repeat(np.dstack([g, g, g]), scale, 0), scale, 1)
            r, cc = divmod(k, COLS)
            y0 = GAP + r * (th * scale + GAP)
            x0 = GAP + cc * (tw * scale + GAP)
            sheet[y0:y0 + th * scale, x0:x0 + tw * scale] = big
            # a one-pixel frame in BLUE: never confusable with the red trace
            sheet[y0 - 1, x0 - 1:x0 + tw * scale + 1] = (40, 90, 200)
            sheet[y0 + th * scale, x0 - 1:x0 + tw * scale + 1] = (40, 90, 200)
            sheet[y0 - 1:y0 + th * scale + 1, x0 - 1] = (40, 90, 200)
            sheet[y0 - 1:y0 + th * scale + 1, x0 + tw * scale] = (40, 90, 200)
            recs[k].update(px=[int(x0), int(y0)], tile=[int(tw), int(th)])
        fn = f'{name}.png'
        write_png(os.path.join(outdir, fn), sheet)
        meta[name] = dict(file=fn, scale=scale, step_mm=step, half_mm=half,
                          along_mm=STEP_MM, cols=COLS, sections=recs,
                          curved=bool(pr.get('path')),
                          p0=[round(float(q), 3) for q in path[0]],
                          p1=[round(float(q), 3) for q in path[-1]],
                          note=pr.get('note', ''))
        print(f'  {fn}  {len(tiles)} sections, {tw}x{th} voxels each, '
              f'sheet {W}x{H} px   [{pr.get("note","")[:44]}]')
    with open(os.path.join(outdir, 'trace-canal.json'), 'w') as f:
        json.dump(dict(volume=os.path.basename(vol_path), structures=meta), f)
    print(f'-> {outdir}')


def do_import(vol_path, tdir, outdir):
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    meta = json.load(open(os.path.join(tdir, 'trace-canal.json')))
    sp = np.array(v.spacing, float)
    report = {}
    for name, st in meta['structures'].items():
        path = os.path.join(tdir, st['file'])
        if not os.path.exists(path):
            continue
        rgb = read_png(path)
        red = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 80) & (rgb[:, :, 2] < 80)
        S = st['scale']
        mask = np.zeros(v.data.shape, bool)
        traced = 0
        for rec in st['sections']:
            x0, y0 = rec['px']; tw, th = rec['tile']
            blk = red[y0:y0 + th * S, x0:x0 + tw * S]
            if not blk.any():
                continue
            # MAJORITY, not ANY -- trace_kit's lesson: counting a voxel traced
            # because any pixel in its block is red fattens every edge by a
            # voxel a side, which on a 3 mm canal is a large fraction of it.
            cell = blk.reshape(th, S, tw, S).mean(axis=(1, 3)) > 0.5
            if not cell.any():
                continue
            traced += 1
            c = np.asarray(rec['centre'], float)
            u = np.asarray(rec['u'], float); w = np.asarray(rec['w'], float)
            n = rec['n']; half = st['half_mm']; stp = st['step_mm']
            ii, jj = np.nonzero(cell)
            ss_w = -half + ii * stp
            ss_u = -half + jj * stp
            P = c[None, :] + w[None, :] * ss_w[:, None] + u[None, :] * ss_u[:, None]
            zi = np.round((P[:, 2] - v.origin[2]) / sp[2]).astype(int)
            yi = np.round((P[:, 1] - v.origin[1]) / sp[1]).astype(int)
            xi = np.round((P[:, 0] - v.origin[0]) / sp[0]).astype(int)
            ok = ((zi >= 0) & (zi < mask.shape[0]) & (yi >= 0)
                  & (yi < mask.shape[1]) & (xi >= 0) & (xi < mask.shape[2]))
            mask[zi[ok], yi[ok], xi[ok]] = True
        if not traced:
            print(f'{name}: nothing traced')
            continue
        # consecutive sections are 1 mm apart on a 3-5 mm canal, so they overlap;
        # a single closing knits the sampled discs into one lumen without
        # inventing course between them
        mask = ndi.binary_closing(mask, np.ones((3, 3, 3)), 2)
        n_vox = int(mask.sum())
        np.save(os.path.join(outdir, f'{name}.npy'), mask)
        report[name] = dict(sections_traced=traced,
                            of_sections=len(st['sections']),
                            voxels=n_vox, mm3=round(n_vox * float(np.prod(sp)), 2))
        print(f'{name}: {traced}/{len(st["sections"])} sections traced, '
              f'{n_vox * float(np.prod(sp)):.1f} mm3')
    with open(os.path.join(outdir, 'traced.json'), 'w') as f:
        json.dump(report, f, indent=1)
    print(f'-> {outdir}')


def main():
    if len(sys.argv) < 5:
        raise SystemExit('export <vol.nrrd> <priors.json> <out-dir>  |  '
                         'import <vol.nrrd> <trace-dir> <out-dir>')
    if sys.argv[1] == 'export':
        do_export(*sys.argv[2:5])
    elif sys.argv[1] == 'import':
        do_import(*sys.argv[2:5])
    else:
        raise SystemExit('export or import')


if __name__ == '__main__':
    main()
