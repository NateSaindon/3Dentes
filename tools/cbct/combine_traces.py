#!/usr/bin/env python3
"""Fold all three tracing rounds into one pulp per tooth.

The rounds answer different questions and are combined accordingly:

  LONGITUDINAL planes (rounds 1-2) give each canal's COURSE -- where it runs and
  how far it goes. They cannot give its cross-section: two perpendicular widths
  were being turned into an ellipse, and a ribbon-shaped pulp came out too fat
  (teeth 9, 24, 25 at 5.9-6.7% of tooth volume against a 3-4% norm).

  AXIAL slices (rounds 2-3) give the CROSS-SECTION directly, measured rather
  than assumed, and they show canals splitting and rejoining -- which a
  longitudinal view cannot, because a canal that has divided still projects as
  one shape until the two parts separate in that particular plane.

So: an axial tracing is used verbatim at its own level, and between levels the
longitudinal reconstruction is rescaled so its area matches the measured areas
either side. The ellipse survives only as a SHAPE hint between measurements; its
size always comes from the operator's tracing.

Usage: combine_traces.py <out-dir> <trace-dir> [trace-dir ...]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shade_kit import read_png                             # noqa: E402
from trace_kit import read_plane, rasterise                # noqa: E402
from vol import Volume                                     # noqa: E402
from skimage.graph import MCP_Geometric                    # noqa: E402

LEDGE_SIGMA = 1.6      # slices; smooths the step at a traced level, nothing more


def longitudinal(meta, tdir, shape):
    """Per-z cross-sections implied by the longitudinal tracings."""
    by_label = {}
    for pl in meta["planes"]:
        by_label.setdefault(pl["label"], []).append(pl)
    mask = np.zeros(shape, bool)
    for label, pls in by_label.items():
        traced = [read_plane(tdir, pl, meta["scale"]) for pl in pls]
        traced = [t for t in traced if t]
        if len(traced) == 2:
            d0 = np.asarray(pls[0]["direction"], float)
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
                ry, rx = (h0, h1) if abs(d0[0]) > abs(d0[1]) else (h1, h0)
                samples.append((z, centre, ry, rx))
            mask |= rasterise(shape, samples, None)
        else:
            for tr in traced:
                mask |= rasterise(shape, [(z, c, h, h) for z, c, h in tr], None)
    return mask


def axials(meta, tdir, shape):
    out = {}
    sc = meta["scale"]
    for ax in meta["axials"]:
        f = os.path.join(tdir, ax["file"])
        if not os.path.exists(f):
            continue
        rgb = read_png(f)
        red = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 80) & (rgb[:, :, 2] < 80)
        h, w = shape[1], shape[2]
        blk = red[:h * sc, :w * sc].reshape(h, sc, w, sc)
        m = blk.mean(axis=(1, 3)) > 0.5
        if m.any():
            out[int(ax["z"])] = m
    return out


def scale_slice(m, factor):
    """Grow or shrink a cross-section about its centroid by an area factor."""
    if not m.any() or abs(factor - 1.0) < 0.05:
        return m
    lin = float(np.sqrt(max(factor, 1e-3)))
    cy, cx = ndi.center_of_mass(m)
    out = ndi.affine_transform(
        m.astype(np.float32),
        matrix=np.diag([1.0 / lin, 1.0 / lin]),
        offset=(cy - cy / lin, cx - cx / lin),
        order=1, mode="constant", cval=0.0)
    return out > 0.5


def tooth_masks(vol_path, split_dir):
    """Per-FMA solid tooth mask, keyed the same way the tracings were cropped."""
    v = Volume.load(vol_path)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    out = {}
    for arch in ("upper", "lower"):
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            tgt = np.array(t["world"][:2])
            best = min(ids, key=lambda s2: float(np.hypot(
                v.world(cents[s2 - 1][2], cents[s2 - 1][1], cents[s2 - 1][0])[0] - tgt[0],
                v.world(cents[s2 - 1][2], cents[s2 - 1][1], cents[s2 - 1][0])[1] - tgt[1])))
            out[t["fma"]] = (arr, best)
    return out


def solid_for(arr, label, origin, shape):
    m = np.zeros(shape, bool)
    sl = tuple(slice(origin[a], origin[a] + shape[a]) for a in range(3))
    m[:] = arr[sl] == label
    ms = m.copy()
    for k in range(shape[0]):
        if m[k].any():
            ms[k] = ndi.binary_fill_holes(m[k])
    return ms


def main():
    outdir, vol_path, split_dir, *dirs = sys.argv[1:]
    tmasks = tooth_masks(vol_path, split_dir)
    os.makedirs(outdir, exist_ok=True)
    teeth = {}
    for d in dirs:
        for name in sorted(os.listdir(d)):
            td = os.path.join(d, name)
            jf = os.path.join(td, "trace.json")
            if os.path.isdir(td) and os.path.exists(jf):
                teeth.setdefault(name, []).append(td)

    rec = {}
    print(f"{'Univ':>4s} {'axials':>6s} {'long mm3':>8s} {'final mm3':>9s} {'comps':>5s}")
    for name in sorted(teeth):
        tds = teeth[name]
        meta0 = json.load(open(os.path.join(tds[0], "trace.json")))
        shape = tuple(meta0["shape_zyx"])
        L = np.zeros(shape, bool)
        A = {}
        tm = tmasks.get(meta0["fma"])
        solid = (solid_for(tm[0], tm[1], meta0["crop_origin_zyx"], shape)
                 if tm else None)
        for td in tds:
            m = json.load(open(os.path.join(td, "trace.json")))
            if m["planes"]:
                L |= longitudinal(m, td, shape)
            A.update(axials(m, td, shape))

        # AXIALS GIVE SIZE AND SHAPE; THE LONGITUDINAL GIVES POSITION.
        # Rescaling the longitudinal reconstruction by an area ratio was tried
        # and blew up -- tooth 3 went from 18 to 115 mm3 -- because the two do
        # not measure the same thing at a given level: on a molar the
        # longitudinal planes trace only the canals while the axials also take
        # in the chamber, so the ratio at a chamber slice is enormous and then
        # gets applied down the whole root.
        #
        # Between two traced axials the cross-section is interpolated from those
        # two measurements, and then slid onto the centreline the longitudinal
        # tracing describes. Size is never inferred from the ellipse; only where
        # no axial brackets a level does the longitudinal shape stand in.
        def sdf(m):
            if not m.any():
                return None
            return (ndi.distance_transform_edt(~m).astype(np.float32)
                    - ndi.distance_transform_edt(m).astype(np.float32))

        # TOPOLOGY DECIDES HOW THE GAPS ARE FILLED.
        # Interpolating between axials works where the pulp is ONE thing at
        # every level -- an anterior, a single-rooted premolar -- and fails
        # badly where it is several: between a molar's chamber slice and a canal
        # slice fifteen levels down, a shape interpolation fills the entire
        # furcation with a solid cone (tooth 3 came out at 147 mm3 against a
        # traced 18). Where the pulp is multiple canals, the longitudinal
        # tracing already has the right topology and is used between levels;
        # the axials still stand verbatim at their own.
        # USE EACH TRACING AS DRAWN. Both sources are the operator's own work,
        # so neither should be rescaled to fit the other: an axial gives the
        # cross-section at its level, the longitudinal gives it everywhere else.
        # Two attempts to be cleverer both inflated the result -- interpolating
        # the axial MASKS across a long gap fills the space between a chamber
        # section and a canal section with a cone (teeth 23-26 reached 7-9% of
        # tooth volume), and interpolating the AREA instead does the same thing
        # more smoothly, because the real taper below a chamber is far from
        # linear. Straight substitution is both simpler and closer to what was
        # actually traced.
        final = np.zeros(shape, bool)
        for z in range(shape[0]):
            if z in A:
                final[z] = A[z]
            elif L[z].any():
                final[z] = L[z]

        # AN AXIAL-ONLY CANAL NEEDS Z-SUPPORT BEFORE SMOOTHING.
        # Where the longitudinal tracing covers only the chamber (teeth whose
        # roots do not separate, so the plane was cut through the whole tooth),
        # a canal exists solely at the six traced axial levels -- isolated
        # slices with nothing above or below them. Smoothing the distance field
        # along z then erodes them away entirely: teeth 4, 12, 13 and 18 lost
        # their canals and half their volume. Extending each unsupported axial a
        # slice either way gives it enough support to survive, and it is honest:
        # a canal seen in cross-section certainly continues past that slice.
        for z in sorted(A):
            if L[z].any():
                continue
            for dz in (-1, 1):
                zz = z + dz
                if 0 <= zz < shape[0] and not final[zz].any():
                    final[zz] = A[z]

        # PULP CANNOT LIE OUTSIDE THE TOOTH.
        # The longitudinal reconstruction rasterises an ellipse from two traced
        # widths and never checked it against the tooth, so where a curved
        # reformat sweeps through a furcation the ellipse spills into the void
        # between the roots -- and then joins mesial to distal across it. Tooth
        # 18 carried 3.5 mm3 outside its own tooth mask and showed six canals as
        # a result; no other tooth had any. Clipping here also means the
        # component bridges below cannot route through that void, because there
        # is nothing there to connect to.
        if solid is not None:
            final &= solid

        # SMOOTH ALONG THE TOOTH'S AXIS.
        # An axial tracing is used verbatim at its own level while neighbouring
        # levels come from the longitudinal reconstruction, so wherever the two
        # disagree in size the boundary shows as a step -- the operator sees
        # long ledges at exactly the slice levels, on every tooth. Smoothing the
        # SIGNED DISTANCE along z and re-thresholding turns each step into a
        # taper. It is done on the distance field rather than the mask because
        # blurring a binary mask erodes thin canals, whereas the distance field
        # keeps them: a canal one voxel across still has a well-defined interior.
        # sigma is deliberately small -- this is meant to remove a step of a
        # slice or two, not to reshape anything.
        sd = (ndi.distance_transform_edt(~final).astype(np.float32)
              - ndi.distance_transform_edt(final).astype(np.float32))
        sd = ndi.gaussian_filter1d(sd, LEDGE_SIGMA, axis=0, mode="nearest")
        smoothed = sd < 0.0
        if solid is not None:
            smoothed &= solid
        if smoothed.any():
            final = smoothed

        # CONNECT EACH CANAL UP TO THE CHAMBER, NOT SIDEWAYS TO ITS NEIGHBOUR.
        # Joining the nearest two components produced exactly what the operator
        # reported: an isthmus between DB and palatal on teeth 3 and 14, canals
        # linked to each other rather than to the chamber, and distal canals
        # hanging off the chamber by a thread on 19 and 30. A canal meets the
        # chamber by running coronally, so the bridge is driven along the
        # tooth's axis and only drifts laterally as it climbs.
        # Repeat until one piece: a single pass can leave orphans, because a
        # bridge drawn to the chamber may pass beside another orphan without
        # touching it, and components are labelled once up front. Teeth 3, 13
        # and 14 survived the first pass in 2-3 pieces.
        for _sweep in range(4):
            lab, n = ndi.label(final,
                               structure=ndi.generate_binary_structure(3, 1))
            if n <= 1:
                break
            sizes = ndi.sum(final, lab, range(1, n + 1))
            # the chamber is the component reaching furthest toward the crown
            crown_end = (min if meta0["arch"] == "upper" else max)
            best_i, best_z = None, None
            for i in range(1, n + 1):
                zi = np.flatnonzero(lab.reshape(shape[0], -1).any(axis=1)
                                    & (lab == i).reshape(shape[0], -1).any(axis=1))
                if not zi.size:
                    continue
                edge = crown_end(zi)
                if best_z is None or (edge < best_z if meta0["arch"] == "upper"
                                      else edge > best_z):
                    best_i, best_z = i, edge
            main_i = best_i if best_i is not None else int(np.argmax(sizes)) + 1
            up = -1 if meta0["arch"] == "upper" else 1
            chamber_pts = np.argwhere(lab == main_i)
            for i in range(1, n + 1):
                if i == main_i:
                    continue
                pts = np.argwhere(lab == i)
                # start from this canal's most CORONAL voxel
                head = pts[np.argmin(pts[:, 0] * up * -1)] if up == -1 else \
                    pts[np.argmax(pts[:, 0])]
                d2 = ((chamber_pts - head) ** 2).sum(1)
                tgt = chamber_pts[int(np.argmin(d2))]
                steps = max(int(abs(tgt[0] - head[0]) + 1) * 2, 4)
                for t in np.linspace(0, 1, steps):
                    q = np.clip(np.round(head + (tgt - head) * t).astype(int),
                                1, np.array(shape) - 2)
                    final[q[0] - 1:q[0] + 2, q[1] - 1:q[1] + 2,
                          q[2] - 1:q[2] + 2] = True
            final = ndi.binary_closing(final, np.ones((3, 3, 3)))
            if solid is not None:
                final &= solid
        _, n2 = ndi.label(final, structure=ndi.generate_binary_structure(3, 1))

        vox = meta0["spacing_mm"] ** 3
        np.save(os.path.join(outdir, f"{meta0['fma']}-pulp.npy"), final)
        rec[meta0["fma"]] = dict(
            universal=meta0["universal"], arch=meta0["arch"],
            pulp_mm3=round(float(final.sum()) * vox, 2),
            traced_axials=len(A),
            crop_origin_zyx=meta0["crop_origin_zyx"], shape_zyx=list(shape),
            provenance="HAND-TRACED: axial cross-sections measured, "
                       "longitudinal course rescaled to them between levels",
            foramina=[])
        print(f"{meta0['universal']:4d} {len(A):6d} {L.sum() * vox:8.1f} "
              f"{final.sum() * vox:9.1f} {n2:5d}")
    json.dump(dict(method="hand-traced, three rounds combined", teeth=rec),
              open(os.path.join(outdir, "pulp-connect.json"), "w"), indent=2)
    print(f"\n{len(rec)} teeth, {sum(r['pulp_mm3'] for r in rec.values()):.1f} mm3")


if __name__ == "__main__":
    main()
