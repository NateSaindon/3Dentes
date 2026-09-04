#!/usr/bin/env python3
"""Learn a canal from the side that was traced and predict the side that was not.

The operator traced both mental canals in slicer.py and could not read all of
one: 39 of 39 sections on the left, 24 of 44 on the right, with several right
slices where nothing was discernable. That is the natural shape of a learning
problem -- one complete example, one with holes, and the two are the same
structure in the same bone on the same day.

IT IS ALSO A REAL HELD-OUT TEST, which the pulp never had. Train on the left
canal alone and predict the right, and the 24 sections he DID manage are a
label the model has never seen. Whatever it scores there is what it is worth.

The features are the pulp module's, for the same reason they worked there: a
canal is dark relative to the bone around it, it is a TUBE rather than a patch,
and it sits away from the cortex. What changes is the reference region -- the
statistics are taken over the mandible rather than over one tooth, and there is
no crown-to-apex axis to speak of, so `along_axis` is measured along the canal's
own principal direction instead of the bone's.

AND THE SAME LESSON APPLIES: classify the wide part, TRACK the thin part. The
mental canal's last few millimetres turn buccally and narrow to nothing, which
is exactly where a voxel classifier gives up; the foramen it has to reach is
known, so that stretch is routed rather than recognised.

Usage: canal_learn.py <vol.nrrd> <pred.nii.gz> <traced-dir> <out-dir>
                      [--train left] [--predict right] [--names mental]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from read_nifti import read_nifti                          # noqa: E402

PAD_MM = 9.0               # corridor around the traced canal to work in
SEED_P, GROW_P = 0.55, 0.22
K_DARK = 14.0
TRACK_P = 0.06
SATURATED = 2500.0
SCALES = (1.0, 2.0, 3.5)


def corridor(mask, spacing, pad_mm=PAD_MM):
    """The region to classify in: everything within pad_mm of the traced canal.

    Deliberately generous and deliberately not a tube. It has to contain the
    parts of the canal the operator could NOT see, which by definition are not
    where his tracing is -- but they are not far from it either.
    """
    d = ndi.distance_transform_edt(~mask, sampling=spacing)
    return d <= pad_mm


def features(D, region, bone, spacing):
    """Per-voxel features over one corridor. Returns (X, names).

    Ranked against the BONE around the canal rather than against the whole
    volume, so a model trained on one side transfers to the other whatever the
    local exposure did.
    """
    ref = D[bone & (D < SATURATED)]
    if ref.size < 500:
        ref = D[bone] if bone.any() else D.ravel()
    qs = np.percentile(ref, np.arange(0, 101))

    def rank(a):
        return np.interp(a, qs, np.linspace(0, 1, 101))

    feats, names = [], []
    for s in SCALES:
        sm = ndi.gaussian_filter(D, s)
        feats.append(rank(sm)); names.append(f"rank_s{s}")
        feats.append((sm - ndi.gaussian_filter(D, s * 3)) / max(ref.std(), 1e-6))
        names.append(f"contrast_s{s}")
    feats.append(rank(D)); names.append("rank_raw")
    for s in (1.0, 2.0):
        sm = ndi.gaussian_filter(D, s)
        H = [[ndi.gaussian_filter(sm, 0, order=[2 if k == a else 0 for k in range(3)])
              if a == b else
              ndi.gaussian_filter(sm, 0, order=[1 if k in (a, b) else 0 for k in range(3)])
              for b in range(3)] for a in range(3)]
        ev = np.linalg.eigvalsh(np.stack([np.stack(r, -1) for r in H], -2))
        feats.append(ev[..., 2] / max(ref.std(), 1e-6)); names.append(f"tube_hi_s{s}")
        feats.append(ev[..., 1] / max(ref.std(), 1e-6)); names.append(f"tube_mid_s{s}")
    # How deep inside the bone, and how close to leaving it: the canal runs in
    # cancellous bone and only meets the cortex at its foramen.
    edt = ndi.distance_transform_edt(bone, sampling=spacing)
    feats.append(edt); names.append("depth_mm")
    feats.append(edt / max(edt.max(), 1e-6)); names.append("depth_norm")
    feats.append(ndi.gaussian_filter(bone.astype(np.float32), 2.0)); names.append("boneness")
    X = np.stack([f[region] for f in feats], 1).astype(np.float32)
    return X, names


def main():
    a = sys.argv[1:]
    if len(a) < 4:
        raise SystemExit(__doc__)
    vol_path, pred_path, traced_dir, out_dir = a[:4]
    opt = {}
    i = 4
    while i < len(a) - 1:
        opt[a[i].lstrip("-")] = a[i + 1]; i += 2
    stem = opt.get("names", "mental")
    train_sides = [x.strip() for x in opt.get("train", "left").split(",") if x.strip()]
    pred_sides = [x.strip() for x in opt.get("predict", "right").split(",") if x.strip()]
    os.makedirs(out_dir, exist_ok=True)

    from sklearn.ensemble import HistGradientBoostingClassifier
    from skimage.graph import MCP_Geometric

    v = Volume.load(vol_path)
    D = v.data.astype(np.float32)
    sp = np.array(v.spacing, float)
    vox = float(np.prod(sp))
    lab, _, _ = read_nifti(pred_path)
    bone = ndi.binary_fill_holes(np.isin(lab, (2, 4, 5)))

    traced = {s: np.load(os.path.join(traced_dir, f"{stem}-{s}.npy"))
              for s in set(train_sides + pred_sides)
              if os.path.exists(os.path.join(traced_dir, f"{stem}-{s}.npy"))}
    for s, m in traced.items():
        print(f"traced {stem}-{s}: {m.sum() * vox:.1f} mm3, "
              f"{int(m.any(axis=(1, 2)).sum())} axial slices")

    cache = {}

    def prep(side):
        if side not in cache:
            m = traced[side]
            box = ndi.find_objects(corridor(m, sp).astype(np.uint8))[0]
            roi = tuple(slice(max(0, b.start - 4), b.stop + 4) for b in box)
            reg = corridor(m[roi], sp)
            X, names = features(D[roi], reg, bone[roi], sp)
            cache[side] = (roi, reg, X, names)
        return cache[side]

    Xs, ys = [], []
    for s in train_sides:
        roi, reg, X, names = prep(s)
        Xs.append(X); ys.append(traced[s][roi][reg])
        print(f"  train on {s}: {X.shape[0]:,} candidate voxels, "
              f"{int(ys[-1].sum()):,} traced ({100 * ys[-1].mean():.2f}%)")
    clf = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.08,
                                         random_state=0).fit(np.vstack(Xs),
                                                             np.concatenate(ys))

    report = {}
    for side in pred_sides:
        roi, reg, X, _ = prep(side)
        prob = np.zeros(reg.shape, np.float32)
        prob[reg] = clf.predict_proba(X)[:, 1]

        seed, weak = prob > SEED_P, prob > GROW_P
        l1, n1 = ndi.label(weak, np.ones((3, 3, 3)))
        ids = np.unique(l1[seed])
        grown = np.isin(l1, ids[ids > 0]) if len(ids) else seed
        FACE = ndi.generate_binary_structure(3, 1)
        lf, nf = ndi.label(grown, FACE)
        if nf:
            sz = ndi.sum(grown, lf, range(1, nf + 1))
            keep = lf == (int(np.argmax(sz)) + 1)
        else:
            keep = grown

        # Route the last stretch to the foramen: the canal's own traced anterior
        # end where there is one, so the prediction cannot stop short of the
        # thing the whole structure exists to reach.
        tgt = traced.get(side)
        if tgt is not None and tgt.any() and keep.any():
            t = tgt[roi]
            pts = np.argwhere(t)
            ant = pts[np.argmin(pts[:, 1])]            # LPS y grows posteriorly
            cost = (1.0 + K_DARK * (1.0 - np.clip(prob, 0, 1))).astype(np.float64)
            cost[~reg] = np.inf
            mcp = MCP_Geometric(cost, sampling=tuple(sp))
            mcp.find_costs(np.argwhere(keep & seed))
            try:
                tr = np.array(mcp.traceback(tuple(ant)))
                path = np.zeros_like(keep)
                path[tr[:, 0], tr[:, 1], tr[:, 2]] = True
                keep |= path | (ndi.binary_dilation(path, np.ones((3, 3, 3)), 1)
                                & (prob > TRACK_P))
            except ValueError:
                print(f"  {side}: could not route to the traced anterior end")
            lf, nf = ndi.label(keep, FACE)
            if nf > 1:
                sz = ndi.sum(keep, lf, range(1, nf + 1))
                keep = lf == (int(np.argmax(sz)) + 1)

        out = np.zeros(D.shape, bool)
        out[roi] = keep
        np.save(os.path.join(out_dir, f"{stem}-{side}.npy"), out)

        r = dict(side=side, mm3=round(out.sum() * vox, 2),
                 axial_slices=int(out.any(axis=(1, 2)).sum()),
                 components=int(nf),
                 inside_bone_pct=round(100 * float((out & bone).sum())
                                       / max(out.sum(), 1), 1))
        if tgt is not None and tgt.any():
            inter = (out & tgt).sum()
            r["dice_vs_traced"] = round(float(2 * inter / (out.sum() + tgt.sum())), 3)
            r["recall_of_traced"] = round(float(inter / tgt.sum()), 3)
            r["traced_mm3"] = round(tgt.sum() * vox, 2)
        report[side] = r
        print(f"  {side}: {r['mm3']} mm3 over {r['axial_slices']} axial slices, "
              f"{r['inside_bone_pct']}% inside bone"
              + (f", Dice {r['dice_vs_traced']} vs his tracing "
                 f"(recall {r['recall_of_traced']})" if "dice_vs_traced" in r else ""))

    with open(os.path.join(out_dir, "traced.json"), "w") as fh:
        json.dump({f"{stem}-{s}": r for s, r in report.items()}, fh, indent=1)
    print(f"-> {out_dir}")


if __name__ == "__main__":
    main()
