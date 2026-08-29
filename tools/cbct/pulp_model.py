#!/usr/bin/env python3
"""Model the pulp cavity of one tooth from the void space inside dentin, and
write it as a surface in LPS millimetres.

Why this is a *model* and not a voxel segmentation
--------------------------------------------------
A root canal is 0.2-1 mm across. At 0.16 mm voxels, and with CBCT's effective
resolution being several times its voxel size, the apical half of the canal is
narrower than the point-spread function. No voxel there ever reaches true pulp
density, so no threshold -- global, local, or hysteresis -- can recover it.
Thresholding either misses the narrow canal or swallows dentin around the wide
chamber; both were tried, and both do exactly that.

What survives sub-resolution blurring is the *integral*. Blurring moves density
around but does not create or destroy it, so the total intensity deficit across
a cross-section is conserved even when the lumen is invisible voxel by voxel:

    area = sum(dentin_local - I) * pixel_area / (dentin_local - pulp_density)

That is measurable well below the resolution limit, and it is what this module
uses. The lumen is tracked plane by plane perpendicular to the tooth's long
axis, its area recovered by the integral above, its cross-sectional shape taken
from the deficit's second moments, and the result swept into a tube.

The two densities are measured from this tooth, not assumed: pulp from the
eroded core of the coronal chamber, where the lumen is wide enough that partial
volume is negligible; dentin from an annulus around the canal on each plane,
with enamel excluded -- include enamel and the crown's reference inflates, which
over-measures the chamber by roughly a factor of two.

Honest limits
-------------
- Cross-sections below ~0.3 mm equivalent diameter are at the noise floor of the
  integral; the apical millimetre is an extrapolation of the taper.
- Lateral canals, apical deltas and isthmuses are not modelled and are not
  present in the data to model.
- A single lumen is assumed. For multi-canal teeth this must be run per canal.

Usage: python3 tools/cbct/pulp_model.py <volume.nrrd> <tooth-key> <out-dir>
"""
import json, os, sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from segment_tooth import TEETH, segment, write_binary_stl

PLANE_HALF_MM = 3.0      # sampled patch half-width
LUMEN_WIN_MM = 1.4       # deficit is integrated inside this radius
ANN_IN, ANN_OUT = 1.2, 2.6
MAX_DRIFT_MM = 0.30      # per-step re-centring limit; the canal curves, it does not jump
MIN_TOOTH_AREA = 1.0     # mm^2; below this the plane has left the tooth


def _densities(roi, solid, dist):
    """Pulp from the eroded chamber core; a starting dentin level from the rest."""
    core = solid & (roi < 800) & (dist > 0.8)
    lab, n = ndi.label(core)
    if n == 0:
        raise SystemExit("no chamber core found; cannot calibrate pulp density")
    sz = ndi.sum(core, lab, range(1, n + 1))
    chamber = lab == (int(np.argmax(sz)) + 1)
    inner = ndi.binary_erosion(chamber, ndi.generate_binary_structure(3, 1))
    pulp = float(roi[inner].mean()) if inner.sum() > 10 else float(roi[chamber].mean())
    return pulp, chamber


def track(roi, solid, enamel_thr, spacing=0.16):
    dist = ndi.distance_transform_edt(solid, sampling=(spacing,) * 3)
    pulp_hu, chamber = _densities(roi, solid, dist)
    solidf = solid.astype(np.float32)

    pts = np.argwhere(solid).astype(float)
    _, _, vt = np.linalg.svd(pts - pts.mean(0), full_matrices=False)
    ax = vt[0]
    if ax[0] < 0:
        ax = -ax                                    # orient toward +z, the apex
    e2, e3 = vt[1], vt[2]

    ng = int(PLANE_HALF_MM / spacing)
    gy, gx = np.mgrid[-ng:ng + 1, -ng:ng + 1] * spacing
    rad = np.hypot(gy, gx)

    def measure(centre):
        g = (centre[None, None, :]
             + (gy / spacing)[:, :, None] * e2[None, None, :]
             + (gx / spacing)[:, :, None] * e3[None, None, :])
        co = [g[..., i] for i in range(3)]
        I = ndi.map_coordinates(roi, co, order=1, mode="constant", cval=pulp_hu)
        M = ndi.map_coordinates(solidf, co, order=1, mode="constant", cval=0) > 0.5
        ann = M & (rad > ANN_IN) & (rad < ANN_OUT) & (I < enamel_thr)
        if ann.sum() < 40:
            ann = M & (rad > 0.8) & (I < enamel_thr)
        if ann.sum() < 20:
            return None
        dent = float(np.percentile(I[ann], 60))
        if dent - pulp_hu < 250:
            return None
        win = M & (rad < LUMEN_WIN_MM)
        if win.sum() < 12:
            return None
        deficit = np.clip(dent - I, 0, dent - pulp_hu) * win
        w = deficit.sum()
        if w < 1e-6:
            return None
        area = float(w) * spacing * spacing / (dent - pulp_hu)
        cy = float((gy * deficit).sum() / w)
        cx = float((gx * deficit).sum() / w)
        # second moments about the deficit centroid -> cross-section anisotropy
        dy, dx = gy - cy, gx - cx
        myy = float((dy * dy * deficit).sum() / w)
        mxx = float((dx * dx * deficit).sum() / w)
        mxy = float((dx * dy * deficit).sum() / w)
        cov = np.array([[myy, mxy], [mxy, mxx]])
        ev, evec = np.linalg.eigh(cov)
        ev = np.clip(ev, 1e-6, None)
        ratio = float(np.sqrt(ev[1] / ev[0]))        # major/minor
        theta = float(np.arctan2(evec[1, 1], evec[0, 1]))
        new = centre + (cy / spacing) * e2 + (cx / spacing) * e3
        return area, dent, new, float(M.sum()) * spacing * spacing, ratio, theta

    start = np.array(ndi.center_of_mass(chamber))
    rows = []
    for direction in (+1, -1):
        centre = start.copy()
        for k in range(1, 200):
            centre = centre + direction * ax
            m = measure(centre)
            if m is None:
                break
            area, dent, newc, tooth_area, ratio, theta = m
            d = newc - centre
            nd = np.linalg.norm(d) * spacing
            if nd > MAX_DRIFT_MM:
                newc = centre + d * (MAX_DRIFT_MM / nd)
            centre = newc
            if tooth_area < MIN_TOOTH_AREA:
                break
            rows.append(dict(t=direction * k * spacing, area=area, dentin=dent,
                             tooth_area=tooth_area, ratio=min(ratio, 3.0),
                             theta=theta, centre=centre.copy()))
    rows.sort(key=lambda r: r["t"])
    return rows, pulp_hu, ax, e2, e3


def _smooth(a, k=9):
    if len(a) < k:
        return a
    ker = np.ones(k) / k
    pad = k // 2
    return np.convolve(np.pad(a, pad, mode="edge"), ker, mode="valid")


def build_tube(rows, e2, e3, v, origin_idx, nseg=24, spacing=0.16):
    """Sweep an elliptical cross-section along the tracked centreline."""
    area = _smooth(np.array([r["area"] for r in rows]))
    ratio = _smooth(np.array([r["ratio"] for r in rows]), 15)
    # An ellipse's orientation is only defined mod pi, so the eigendecomposition
    # returns an angle that can jump by pi between adjacent planes. Sweeping that
    # directly puts a visible pinch in the tube wherever it flips. Unwrap on
    # period pi (double, unwrap on 2pi, halve), then smooth.
    theta = np.array([r["theta"] for r in rows])
    theta = np.unwrap(2.0 * theta) / 2.0
    theta = _smooth(theta, 11)
    cen = np.array([r["centre"] for r in rows])
    cen = np.stack([_smooth(cen[:, i], 7) for i in range(3)], axis=1)
    area = np.clip(area, 0.0, None)
    # pi*a*b = area with a/b = ratio
    b = np.sqrt(area / (np.pi * np.maximum(ratio, 1e-3)))
    a = ratio * b

    x0, y0, z0 = origin_idx
    def world(idx):
        return np.array([v.origin[0] + (x0 + idx[2]) * v.spacing[0],
                         v.origin[1] + (y0 + idx[1]) * v.spacing[1],
                         v.origin[2] + (z0 + idx[0]) * v.spacing[2]])

    phi = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    rings = []
    for i in range(len(rows)):
        c = world(cen[i])
        u = world(cen[i] + e2) - c
        w = world(cen[i] + e3) - c
        u /= np.linalg.norm(u); w /= np.linalg.norm(w)
        ct, stt = np.cos(theta[i]), np.sin(theta[i])
        maj, mino = ct * u + stt * w, -stt * u + ct * w
        rings.append(c[None, :] + (a[i] * np.cos(phi))[:, None] * maj[None, :]
                                + (b[i] * np.sin(phi))[:, None] * mino[None, :])
    rings = np.array(rings)
    verts = rings.reshape(-1, 3)
    faces = []
    for i in range(len(rings) - 1):
        for j in range(nseg):
            k = (j + 1) % nseg
            p0, p1 = i * nseg + j, i * nseg + k
            q0, q1 = (i + 1) * nseg + j, (i + 1) * nseg + k
            faces.append([p0, q0, q1]); faces.append([p0, q1, p1])
    # caps: one vertex at each end ring's centroid
    capA = len(verts); capB = capA + 1
    verts = np.vstack([verts, rings[0].mean(0)[None, :], rings[-1].mean(0)[None, :]])
    for j in range(nseg):
        k = (j + 1) % nseg
        faces.append([capA, k, j])
        faces.append([capB, (len(rings) - 1) * nseg + j, (len(rings) - 1) * nseg + k])
    return verts, np.array(faces), area, a, b


def voxelize(rows, area, ratio_a, ratio_b, theta, cen, shape, e2, e3, ax):
    """Rasterise the swept ellipse into the ROI grid.

    Each voxel is projected onto the long axis to find its plane, then tested
    against that plane's ellipse. The centreline drifts by at most 0.3 mm per
    step, so projecting onto the straight axis rather than the curved centreline
    costs far less than a voxel.
    """
    zz, yy, xx = np.indices(shape)
    P = np.stack([zz, yy, xx], axis=-1).astype(np.float32)
    origin = cen[0]
    rel = P - origin[None, None, None, :]
    t_idx = (rel @ ax)                                   # position along the axis, in voxels
    k = np.clip(np.rint(t_idx).astype(np.int32), 0, len(rows) - 1)
    near = (t_idx >= -1) & (t_idx <= len(rows))
    c_k = cen[k]                                          # (z,y,x) centre for each voxel
    d = P - c_k
    u = d @ e2
    w = d @ e3
    th = theta[k]
    ct, st_ = np.cos(th), np.sin(th)
    maj = (u * ct + w * st_) * 0.16                       # mm
    mino = (-u * st_ + w * ct) * 0.16
    a = np.maximum(ratio_a[k], 1e-4)
    b = np.maximum(ratio_b[k], 1e-4)
    inside = near & ((maj / a) ** 2 + (mino / b) ** 2 <= 1.0)
    return inside


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    vol_path, key, outdir = sys.argv[1:4]
    spec = TEETH[key]
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    seg = segment(v, spec)
    roi = seg["roi"].astype(np.float32)
    rows, pulp_hu, ax, e2, e3 = track(roi, seg["tooth"], float(seg["otsu"]))
    if len(rows) < 10:
        raise SystemExit(f"tracked only {len(rows)} planes; cannot model")
    verts, faces, area, a, b = build_tube(rows, e2, e3, v, seg["origin_idx"])
    stl = os.path.join(outdir, f"{spec['fma']}-pulp-model.stl")
    write_binary_stl(stl, verts, faces)

    # --- repair the solid and re-split the hard tissue.
    #
    # segment_tooth isolates above 1050 HU, so the lumen is not in its basin, and
    # the per-slice fill only closes it where the dentin ring is unbroken. Where
    # the ring breaks the canal stays outside the "solid" -- 17 of 114 planes for
    # tooth 9. Unioning the modelled lumen back in closes those gaps, and the
    # tissues then partition the tooth exactly.
    ratio = _smooth(np.array([r["ratio"] for r in rows]), 15)
    theta = np.unwrap(2.0 * np.array([r["theta"] for r in rows])) / 2.0
    theta = _smooth(theta, 11)
    cen = np.array([r["centre"] for r in rows])
    cen = np.stack([_smooth(cen[:, i], 7) for i in range(3)], axis=1)
    lumen = voxelize(rows, area, a, b, theta, cen, roi.shape, e2, e3, ax)
    solid_fixed = seg["tooth"] | lumen
    enamel = seg["enamel"] & ~lumen
    dentin = solid_fixed & ~enamel & ~lumen
    vox = float(np.prod(v.spacing))
    from segment_tooth import mesh as _mesh
    extra = {}
    for tis, m, lvl in (("tooth", solid_fixed, None), ("dentin", dentin, None),
                        ("enamel", enamel, float(seg["otsu"]))):
        out = _mesh(m, v, seg["origin_idx"], roi=roi, level=lvl)
        entry = dict(volume_mm3=round(float(m.sum()) * vox, 1))
        if out is not None:
            vv, ff = out
            name = spec["fma"] if tis == "tooth" else f"{spec['fma']}-{tis}"
            write_binary_stl(os.path.join(outdir, f"{name}.stl"), vv, ff)
            entry["triangles"] = int(len(ff))
        extra[tis] = entry
    extra["pulp_voxelised"] = dict(volume_mm3=round(float(lumen.sum()) * vox, 2))

    ts = np.array([r["t"] for r in rows])
    dia = 2 * np.sqrt(np.clip(area, 0, None) / np.pi)
    apical = dict(t_mm=round(float(ts[-1]), 2),
                  diameter_mm=round(float(dia[-1]), 3),
                  area_mm2=round(float(area[-1]), 4),
                  position_lps=[round(float(x), 2) for x in verts[-1]])
    report = dict(
        tooth=key, fma=spec["fma"], name=spec["name"], source=os.path.basename(vol_path),
        method="cross-sectional area by intensity-deficit integration; elliptical sweep",
        pulp_density_hu=round(pulp_hu), planes=len(rows),
        canal_length_mm=round(float(ts[-1] - ts[0]), 2),
        lumen_volume_mm3=round(float(area.sum() * 0.16), 2),
        max_diameter_mm=round(float(dia.max()), 3),
        apical_foramen=apical,
        stl=os.path.basename(stl), triangles=int(len(faces)),
        caveat="apical millimetre is a taper extrapolation; sub-resolution. "
               "Lateral canals and deltas are not modelled.",
        profile=[dict(t=round(float(t), 2), dia_mm=round(float(d), 3))
                 for t, d in list(zip(ts, dia))[::4]],
        repaired_tissues=extra,
    )
    with open(os.path.join(outdir, f"tooth{key}-pulp.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(f"  planes tracked   {len(rows)}")
    print(f"  canal length     {report['canal_length_mm']} mm")
    print(f"  lumen volume     {report['lumen_volume_mm3']} mm3")
    print(f"  max diameter     {report['max_diameter_mm']} mm")
    print(f"  apical foramen   {apical['diameter_mm']} mm at LPS {apical['position_lps']}")
    print(f"  -> {stl} ({len(faces)} tris)")
    print("  repaired solid + re-split hard tissue:")
    for k2, val in extra.items():
        print(f"    {k2:16s} {val['volume_mm3']:8.2f} mm3"
              + (f"  ({val['triangles']} tris)" if "triangles" in val else ""))


if __name__ == "__main__":
    main()
