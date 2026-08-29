#!/usr/bin/env python3
"""Model the pulp cavity of every tooth, including multi-canal teeth.

Extends the single-lumen method in pulp_model.py. The physics is unchanged: a
root canal is 0.2-1 mm across, narrower than CBCT's point-spread function over
much of its length, so no voxel in the apical half ever reaches pulp density and
no threshold recovers it. What survives sub-resolution blurring is the integral --
the intensity deficit across a cross-section is conserved even where the lumen is
invisible voxel by voxel:

    area = sum(dentin_local - I) * pixel_area / (dentin_local - pulp_density)

What is new here is that a molar has three or four of those lumens and a premolar
two, so each plane perpendicular to the tooth axis may cut several canals. The
deficit map on each plane is therefore split into basins by watershed, each basin
integrated separately, and the basins linked plane to plane by proximity into
tracks. A track is one canal. Bifurcation falls out for free: the chamber is one
basin that becomes two or three as the roots divide.

Tooth masks come from DentalSegmentator via split_teeth.py, which is what makes
this practical for 28 teeth -- and unlike the hand-built watershed basins, those
masks are already solid, so the pulp is inside the mask rather than cut out of it.

Usage: python3 tools/cbct/pulp_all.py <volume.nrrd> <split-dir> <out-dir> [universal...]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage.segmentation import watershed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume
from segment_tooth import write_binary_stl

PLANE_HALF_MM = 5.0
ANN_IN, ANN_OUT = 1.4, 3.2
MAX_DRIFT_MM = 0.35
NOISE_HU = 70.0
MIN_TRACK_MM = 3.0        # a canal shorter than this is noise
MAX_GAP_PLANES = 3        # a canal may fade for a few planes without ending
LINK_MM = 1.1             # basin-to-basin linking radius between planes
LUMEN_CAP_MM = 1.5        # integration radius about each basin peak

# Usual canal count by tooth type. Used the same way as the mesiodistal width
# prior in split_teeth.py: the LUMEN is measured, the COUNT is constrained.
# Without it, detection noise on the upper molars -- whose canals are thin,
# curved and at the resolution limit -- yields ten or eleven "canals" where
# there are four. Tracks are ranked by lumen and the N largest kept.
# Deviations from these counts are real and common (a second mesiobuccal in an
# upper first molar, a second canal in a lower incisor), so this is a ceiling on
# credulity, not a claim about this patient. Verify against the operator.
CANAL_COUNT = {
    # maxillary: central, lateral, canine, PM1, PM2, M1, M2
    2: 3, 3: 4, 4: 1, 5: 2, 6: 1, 7: 1, 8: 1,
    9: 1, 10: 1, 11: 1, 12: 2, 13: 1, 14: 4, 15: 3,
    # mandibular: M2, M1, PM2, PM1, canine, lateral, central
    18: 3, 19: 3, 20: 1, 21: 1, 22: 1, 23: 1, 24: 1,
    25: 1, 26: 1, 27: 1, 28: 1, 29: 1, 30: 3, 31: 3,
}


def tooth_masks(split_dir):
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    out = {}
    for arch in ("upper", "lower"):
        if arch not in rep:
            continue
        lab = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        for t in rep[arch]["teeth"]:
            out[t["universal"]] = (arch, lab, t)
    return rep, out


def densities(roi, mask, dist):
    """Pulp from the widest, unambiguous part of the chamber; enamel cut by Otsu."""
    from skimage.filters import threshold_otsu
    core = mask & (roi < 850) & (dist > 0.8)
    lab, n = ndi.label(core)
    if n == 0:
        return None, None
    sz = ndi.sum(core, lab, range(1, n + 1))
    chamber = lab == (int(np.argmax(sz)) + 1)
    inner = ndi.binary_erosion(chamber, ndi.generate_binary_structure(3, 1))
    pulp = float(roi[inner].mean()) if inner.sum() > 10 else float(roi[chamber].mean())
    hard = roi[mask & (roi > 900)]
    enam = float(threshold_otsu(hard)) if hard.size > 500 else 1600.0
    return pulp, enam


def track_canals(roi, mask, spacing, pulp_hu, enam_hu, max_canals=None,
                 arch="upper"):
    """Return a list of canal tracks; each is a list of per-plane measurements."""
    pts = np.argwhere(mask).astype(float)
    centre0 = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - centre0, full_matrices=False)
    # Orient the long axis so the LAST tracked plane is the apical one -- every
    # "apical_*" field downstream depends on it. Maxillary roots point superiorly
    # and mandibular roots inferiorly, so a single convention is wrong for one
    # arch. Fixing +z for both put the lower teeth's "apex" at the occlusal
    # surface, which only showed up when nerve branches came out 18-24 mm long
    # against a canal that runs a few millimetres below the molar apices.
    ax = vt[0]
    if (ax[0] < 0) if arch == "upper" else (ax[0] > 0):
        ax = -ax
    e2, e3 = vt[1], vt[2]
    sp = spacing[0]
    ng = int(PLANE_HALF_MM / sp)
    gy, gx = np.mgrid[-ng:ng + 1, -ng:ng + 1] * sp
    rad = np.hypot(gy, gx)
    maskf = mask.astype(np.float32)
    proj = (pts - centre0) @ ax
    t_lo, t_hi = float(proj.min()), float(proj.max())

    planes = []
    for t in np.arange(t_lo, t_hi, 1.0):
        c = centre0 + t * ax
        g = (c[None, None, :] + (gy / sp)[:, :, None] * e2[None, None, :]
             + (gx / sp)[:, :, None] * e3[None, None, :])
        co = [g[..., i] for i in range(3)]
        I = ndi.map_coordinates(roi, co, order=1, mode="constant", cval=pulp_hu)
        M = ndi.map_coordinates(maskf, co, order=1, mode="constant", cval=0) > 0.5
        if M.sum() < 60:
            continue
        ann = M & (rad > ANN_IN) & (rad < ANN_OUT) & (I < enam_hu)
        if ann.sum() < 60:
            ann = M & (I < enam_hu)
        if ann.sum() < 30:
            continue
        dent = float(np.percentile(I[ann], 60))
        if dent - pulp_hu < 250:
            continue
        interior = ndi.binary_erosion(M, np.ones((3, 3)), 2)
        D = np.clip(dent - I, 0.0, dent - pulp_hu) * interior
        if D.max() < 2.5 * NOISE_HU:
            continue
        Ds = ndi.gaussian_filter(D, 1.0)
        # h-maxima, not raw local maxima: inside one broad pulp chamber the noise
        # produces a dozen local peaks above any relative cut, and each becomes a
        # spurious canal. Requiring a peak to stand H above its own surroundings
        # counts chambers and canals rather than noise.
        H = max(0.18 * float(Ds.max()), 1.5 * NOISE_HU)
        rec = ndi.grey_erosion(Ds, footprint=np.ones((3, 3)))
        seed = Ds - H
        for _ in range(24):                       # morphological reconstruction
            seed = np.minimum(ndi.grey_dilation(seed, footprint=np.ones((3, 3))), Ds)
        peak = (Ds - seed) > 1e-6
        peak &= Ds > 0.30 * Ds.max()
        markers, nm = ndi.label(peak)
        if nm == 0:
            continue
        # Bound the integration region. Every voxel darker than the dentin
        # reference contributes deficit, and half of any real dentin sits below
        # its own 60th percentile -- so an unbounded basin accumulates dentin
        # noise as lumen. It inflated the lower premolars and canines two- to
        # threefold, reporting 3-4 mm "chambers" where a premolar's is 1.5-2 mm.
        # The validated single-canal model integrated inside a 1.4 mm window; the
        # equivalent here is a floor at the noise level plus a radius cap about
        # each basin's own peak.
        floor = 2.0 * NOISE_HU
        basins = watershed(-Ds, markers, mask=(D > floor) & (D > 0.20 * Ds.max()))
        found = []
        for b in range(1, nm + 1):
            sel = basins == b
            if not sel.any():
                continue
            pk = np.unravel_index(int(np.argmax(np.where(sel, Ds, -1))), Ds.shape)
            near = (np.hypot(gy - gy[pk], gx - gx[pk]) < LUMEN_CAP_MM)
            sel = sel & near
            w = float(D[sel].sum())
            if w <= 0:
                continue
            area = w * sp * sp / (dent - pulp_hu)
            if area < 0.02:
                continue
            wy = float((gy[sel] * D[sel]).sum() / w)
            wx = float((gx[sel] * D[sel]).sum() / w)
            found.append(dict(t=float(t), area=area, dent=dent,
                              uv=(wy, wx), world_c=c + (wy / sp) * e2 + (wx / sp) * e3))
        if found:
            planes.append(found)

    # Link basins between consecutive planes into tracks. A track is one canal:
    # it starts where a basin first appears, follows the nearest basin on each
    # subsequent plane, and ends when nothing is close enough. Bifurcation falls
    # out on its own -- when the chamber divides, the unmatched basin starts a
    # new track at the point of division.
    tracks, open_tracks = [], []          # open_tracks: [measurements, misses]
    for pl in planes:
        used, still_open = set(), []
        for tr, miss in open_tracks:
            last = tr[-1]
            best, bi = None, None
            for i, f in enumerate(pl):
                if i in used:
                    continue
                d = np.hypot(f["uv"][0] - last["uv"][0], f["uv"][1] - last["uv"][1])
                if d < LINK_MM and (best is None or d < best):
                    best, bi = d, i
            if bi is None:
                # A canal can fade below the detection floor for a plane or two
                # where it is narrowest without having ended. Closing on the
                # first miss shatters one canal into a dozen stubs.
                if miss + 1 > MAX_GAP_PLANES:
                    tracks.append(tr)
                else:
                    still_open.append((tr, miss + 1))
            else:
                tr.append(pl[bi])
                used.add(bi)
                still_open.append((tr, 0))
        open_tracks = still_open
        for i, f in enumerate(pl):
            if i not in used:
                open_tracks.append(([f], 0))
    tracks.extend(tr for tr, _ in open_tracks)
    step_mm = spacing[0]
    good = [tr for tr in tracks
            if (tr[-1]["t"] - tr[0]["t"]) * step_mm >= MIN_TRACK_MM]

    # Merge tracks that describe the same canal. Linking is greedy and per plane,
    # so a canal that fades and is re-acquired becomes two tracks running through
    # the same space. Two tracks overlapping in t and staying within LINK_MM of
    # each other are one canal seen twice.
    good.sort(key=lambda tr: tr[0]["t"])
    merged = []
    for tr in good:
        hit = None
        for mt in merged:
            lo, hi = max(tr[0]["t"], mt[0]["t"]), min(tr[-1]["t"], mt[-1]["t"])
            if hi < lo:
                continue
            a = {m["t"]: m["uv"] for m in tr}
            b = {m["t"]: m["uv"] for m in mt}
            common = [t for t in a if t in b and lo <= t <= hi]
            if not common:
                continue
            d = np.mean([np.hypot(a[t][0] - b[t][0], a[t][1] - b[t][1]) for t in common])
            if d < LINK_MM:
                hit = mt
                break
        if hit is None:
            merged.append(list(tr))
        else:
            seen = {m["t"] for m in hit}
            hit.extend(m for m in tr if m["t"] not in seen)
            hit.sort(key=lambda m: m["t"])

    # Keep canals that carry real lumen. A canal runs chamber to foramen and
    # contributes a substantial share; the residue is detection noise on a tooth
    # whose canal is at the resolution limit anyway.
    if merged:
        lum = [sum(m["area"] for m in tr) for tr in merged]
        top = max(lum)
        merged = [tr for tr, l in zip(merged, lum) if l >= 0.12 * top]
    merged.sort(key=lambda tr: -sum(m["area"] for m in tr))
    if max_canals and len(merged) > max_canals:
        # Cap the COUNT without discarding measured lumen. A canal that fragments
        # into two tracks is still one canal carrying one volume; deleting the
        # smaller track loses real signal -- it cost tooth 9 a third of its pulp,
        # 13.9 mm3 against a validated 20.4. So surplus tracks are folded into
        # the nearest retained one instead of dropped.
        keep, extra = merged[:max_canals], merged[max_canals:]
        for tr in extra:
            mid = tr[len(tr) // 2]
            best, bk = None, None
            for k, kt in enumerate(keep):
                near = min(kt, key=lambda m: abs(m["t"] - mid["t"]))
                d = np.hypot(near["uv"][0] - mid["uv"][0], near["uv"][1] - mid["uv"][1])
                if best is None or d < best:
                    best, bk = d, k
            seen = {m["t"] for m in keep[bk]}
            for m in tr:
                if m["t"] in seen:
                    # same level already measured: add the area, keep the centre
                    for q in keep[bk]:
                        if q["t"] == m["t"]:
                            q["area"] += m["area"]
                            break
                else:
                    keep[bk].append(m)
                    seen.add(m["t"])
            keep[bk].sort(key=lambda m: m["t"])
        merged = keep
    return merged, ax, e2, e3


def _smooth(a, k=7):
    if len(a) < k:
        return a
    ker = np.ones(k) / k
    return np.convolve(np.pad(a, k // 2, mode="edge"), ker, mode="valid")


def tube(track, nseg=20):
    """Sweep a circular cross-section of the measured area along a track."""
    area = _smooth(np.array([m["area"] for m in track]))
    cen = np.array([m["world_c"] for m in track], dtype=float)
    cen = np.stack([_smooth(cen[:, i], 5) for i in range(3)], axis=1)
    r = np.sqrt(np.maximum(area, 0.0) / np.pi)
    if len(cen) < 3:
        return None
    tang = np.gradient(cen, axis=0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
    ref = np.array([0.0, 0.0, 1.0])
    rings = []
    phi = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    for i in range(len(cen)):
        t = tang[i]
        u = np.cross(t, ref)
        if np.linalg.norm(u) < 1e-6:
            u = np.cross(t, np.array([0.0, 1.0, 0.0]))
        u /= np.linalg.norm(u)
        w = np.cross(t, u)
        rings.append(cen[i][None, :] + r[i] * (np.cos(phi)[:, None] * u[None, :]
                                               + np.sin(phi)[:, None] * w[None, :]))
    rings = np.array(rings)
    verts = rings.reshape(-1, 3)
    faces = []
    for i in range(len(rings) - 1):
        for j in range(nseg):
            k = (j + 1) % nseg
            p0, p1 = i * nseg + j, i * nseg + k
            q0, q1 = (i + 1) * nseg + j, (i + 1) * nseg + k
            faces.append([p0, q0, q1])
            faces.append([p0, q1, p1])
    capA, capB = len(verts), len(verts) + 1
    verts = np.vstack([verts, rings[0].mean(0)[None, :], rings[-1].mean(0)[None, :]])
    for j in range(nseg):
        k = (j + 1) % nseg
        faces.append([capA, k, j])
        faces.append([capB, (len(rings) - 1) * nseg + j, (len(rings) - 1) * nseg + k])
    return verts, np.array(faces), area, r


def index_to_world(cen_idx, v, origin_idx):
    """ROI-local (z, y, x) index -> world LPS millimetres.

    `origin_idx` is the crop corner as (x0, y0, z0). Omitting it silently places
    every mesh at the wrong point in the volume. The tracking, the volumes and
    the diameters all stay correct, because they are counts and differences, so
    nothing in the numbers looks wrong. It surfaced only when the nerve branches
    were wired to the apices and a lower-LEFT molar's apex came out at x = -35.9,
    on the right side of the head.
    """
    x0, y0, z0 = origin_idx
    w = np.empty_like(cen_idx)
    w[:, 0] = v.origin[0] + (x0 + cen_idx[:, 2]) * v.spacing[0]
    w[:, 1] = v.origin[1] + (y0 + cen_idx[:, 1]) * v.spacing[1]
    w[:, 2] = v.origin[2] + (z0 + cen_idx[:, 0]) * v.spacing[2]
    return w


def main():
    vol_path, split_dir, outdir = sys.argv[1:4]
    wanted = [int(x) for x in sys.argv[4:]] if len(sys.argv) > 4 else None
    os.makedirs(outdir, exist_ok=True)
    v = Volume.load(vol_path)
    roi = v.data.astype(np.float32)
    rep, masks = tooth_masks(split_dir)
    vox = float(np.prod(v.spacing))
    results = {}
    print(f"{'Univ':>4s} {'FMA':>9s} {'tooth':>8s} {'canals':>6s} {'lumen':>8s} "
          f"{'len':>6s} {'maxD':>6s} {'foramina (mm)'}")
    for num in sorted(masks):
        if wanted and num not in wanted:
            continue
        arch, lab, rec = masks[num]
        # locate this tooth's segment by centroid
        target = np.array(rec["world"][:2])
        best = None
        for sid in range(1, int(lab.max()) + 1):
            m = lab == sid
            if not m.any():
                continue
            cz, cy, cx = ndi.center_of_mass(m)
            w = v.world(cx, cy, cz)
            d = float(np.hypot(w[0] - target[0], w[1] - target[1]))
            if best is None or d < best[0]:
                best = (d, sid)
        seg = lab == best[1]
        zz, yy, xx = np.where(seg)
        pad = 8
        z0, z1 = max(0, zz.min() - pad), min(roi.shape[0], zz.max() + pad)
        y0, y1 = max(0, yy.min() - pad), min(roi.shape[1], yy.max() + pad)
        x0, x1 = max(0, xx.min() - pad), min(roi.shape[2], xx.max() + pad)
        sub = roi[z0:z1, y0:y1, x0:x1]
        m = seg[z0:z1, y0:y1, x0:x1]
        dist = ndi.distance_transform_edt(m, sampling=tuple(v.spacing))
        pulp_hu, enam_hu = densities(sub, m, dist)
        if pulp_hu is None:
            print(f"{num:4d} {rec['fma']:>9s} {rec['mm3']:8.1f}  no chamber core found")
            continue
        cap = CANAL_COUNT.get(num)
        tracks, ax, e2, e3 = track_canals(sub, m, tuple(v.spacing), pulp_hu,
                                          enam_hu, max_canals=cap, arch=arch)
        entry = dict(fma=rec["fma"], universal=num, arch=arch,
                     tooth_mm3=rec["mm3"], pulp_density_hu=round(pulp_hu),
                     enamel_threshold_hu=round(enam_hu),
                     canal_count_prior=cap,
                     note="lumen volumes are measured; canal COUNT is capped by "
                          "the usual anatomy for this tooth type -- verify",
                     canals=[])
        allv, allf, off = [], [], 0
        for ti, tr in enumerate(tracks):
            out = tube(tr)
            if out is None:
                continue
            verts_idx, faces, area, r = out
            verts = index_to_world(verts_idx, v, (x0, y0, z0))
            length = (tr[-1]["t"] - tr[0]["t"]) * v.spacing[0]
            lumen = float(area.sum()) * v.spacing[0]
            dia = 2.0 * np.sqrt(np.maximum(area, 0) / np.pi)
            # Keep the centreline and radius profile. The lining and the
            # neurovascular core in pulp_tissue.py are offsets of this curve, and
            # re-deriving them from the tube mesh would mean recovering a
            # centreline that was already computed and thrown away.
            cen = np.array([m["world_c"] for m in tr], dtype=float)
            cen_w = index_to_world(np.stack([_smooth(cen[:, i], 5)
                                             for i in range(3)], axis=1),
                                   v, (x0, y0, z0))
            entry["canals"].append(dict(
                index=ti, length_mm=round(length, 2), lumen_mm3=round(lumen, 2),
                max_diameter_mm=round(float(dia.max()), 3),
                apical_diameter_mm=round(float(dia[-1]), 3),
                apical_position_lps=[round(float(x), 2) for x in verts[-1]],
                centreline_lps=[[round(float(c), 3) for c in pt] for pt in cen_w],
                radius_mm=[round(float(x), 4) for x in r]))
            allv.append(verts)
            allf.append(faces + off)
            off += len(verts)
        if allv:
            write_binary_stl(os.path.join(outdir, f"{rec['fma']}-pulp.stl"),
                             np.vstack(allv), np.vstack(allf))
        tot = sum(c["lumen_mm3"] for c in entry["canals"])
        entry["total_lumen_mm3"] = round(tot, 2)
        results[num] = entry
        fo = " ".join(f"{c['apical_diameter_mm']:.2f}" for c in entry["canals"])
        ln = max((c["length_mm"] for c in entry["canals"]), default=0)
        md = max((c["max_diameter_mm"] for c in entry["canals"]), default=0)
        print(f"{num:4d} {rec['fma']:>9s} {rec['mm3']:8.1f} {len(entry['canals']):6d} "
              f"{tot:8.2f} {ln:6.1f} {md:6.2f}  {fo}")
    with open(os.path.join(outdir, "pulp.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("wrote", os.path.join(outdir, "pulp.json"))


if __name__ == "__main__":
    main()
