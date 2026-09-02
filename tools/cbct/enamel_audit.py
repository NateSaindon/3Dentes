#!/usr/bin/env python3
"""Measure the enamel shell against published thickness figures, per tooth.

The tune sheets say whether the cap LOOKS right. This says whether it IS the
thickness the literature reports, at the sites the literature reports it, which
is the only way the envelope in enamel.py can be checked rather than believed.

Sites, chosen to match the sources rather than to be convenient:

  1 / 3 / 5 mm coronal to the CEJ
      Mean radial thickness of the enamel annulus at that axial level, computed
      as ring area / tooth perimeter. Compared against the CBCT series on
      maxillary central incisors (PMC11592583): 0.48 / 0.81 / 0.95 mm.
      NOTE THAT SERIES IS LABIAL ONLY and this is a circumferential mean, which
      includes the thicker interproximal enamel, so this figure should read
      somewhat HIGH against it. It is not a discrepancy to tune away.
  cusp tip / incisal edge
      Enamel depth measured DOWN THE TOOTH'S AXIS from the cusp tip to the
      first dentin, which is how the literature defines it (dentine-horn apex
      to enamel cusp tip). The obvious metric -- deepest enamel near the tip --
      is BLIND: depth-from-surface inside a cusp is bounded by the cusp's own
      radius, not by the enamel, so it read 0.48-1.23 mm on a cap that is
      visibly 2 mm thick. Wheeler gives 2.0-2.5 mm over molar and premolar
      cusps and ~2.0 mm at an incisal edge.
  crown fraction
      Enamel as a percentage of CROWN volume -- the tooth coronal to the CEJ.
      Reported this way because the literature convention is enamel over crown,
      and because a fraction of the WHOLE tooth is not comparable between a
      short-rooted molar and a long-rooted canine: it measures root length as
      much as enamel. Both are printed, and the crown figure is the one to read
      across teeth.

Usage: enamel_audit.py <vol.nrrd> <split-dir> <out.json> [cut_over_dentin]
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
import enamel as EN                                        # noqa: E402

# The CBCT series this scan is most comparable to (200 um voxel against 160).
LIT_CERVICAL = {1.0: 0.48, 3.0: 0.81, 5.0: 0.95}
LIT_TIP = {"molar": (2.0, 2.5), "premolar": (2.0, 2.5),
           "canine": (1.8, 2.2), "incisor": (1.8, 2.2)}
# Interproximal enamel at the contact, mean of mesial and distal, by arch and
# type (PMC11235574; first/second are averaged within a type).
LIT_CONTACT = {("upper", "incisor"): 0.77, ("upper", "canine"): 1.09,
               ("upper", "premolar"): 1.12, ("upper", "molar"): 1.31,
               ("lower", "incisor"): 0.68, ("lower", "canine"): 0.99,
               ("lower", "premolar"): 1.17, ("lower", "molar"): 1.35}
LEVELS_MM = (1.0, 3.0, 5.0)


def ring_thickness(cap, solid, z, spacing):
    """Mean radial enamel thickness at one axial level: area / perimeter."""
    m, e = solid[z], cap[z]
    if not m.any() or not e.any():
        return None
    px, py = float(spacing[0]), float(spacing[1])
    area = float(e.sum()) * px * py
    # perimeter of the TOOTH at this level, from its boundary voxel count
    edge = m & ~ndi.binary_erosion(m, np.ones((3, 3)))
    per = float(edge.sum()) * (0.5 * (px + py))
    return None if per <= 0 else area / per


def dej_distance(cap, solid, spacing):
    """Per-voxel distance to the nearest DENTIN voxel, in mm.

    At a surface point of the enamel this IS the enamel thickness there,
    measured perpendicular to the DEJ, which is how every source quotes it.
    Two earlier metrics both measured something else and both were believed for
    a while: depth-from-surface is bounded by a cusp's own radius (it read
    0.5-1.2 mm on a visibly 2 mm cap), and an axial run through an incisal edge
    stays inside enamel for millimetres because the labial and lingual plates
    meet there, so it simply saturated at whatever probe length it was given.
    """
    dentin = solid & ~cap
    if not dentin.any():
        return None
    return ndi.distance_transform_edt(~dentin, sampling=tuple(spacing))


def surface_thickness(cap, dej, z, pct=90):
    """Enamel thickness around one axial ring: percentile over its surface."""
    if dej is None:
        return None
    e = cap[z]
    if not e.any():
        return None
    edge = e & ~ndi.binary_erosion(e, np.ones((3, 3)))
    vals = dej[z][edge if edge.any() else e]
    return None if not vals.size else round(float(np.percentile(vals, pct)), 2)


def audit_tooth(sub, solid, arch, uni, spacing, cut, neighbours=None):
    cap, meta = EN.enamel_mask(sub, solid, arch, uni, spacing, margin_hu=cut,
                               neighbours=neighbours)
    vox = float(np.prod(spacing))
    z_cej, z_tip = meta.get("cej_z"), meta.get("tip_z")
    out = dict(universal=uni, arch=arch, type=meta.get("type"),
               tooth_mm3=round(float(solid.sum()) * vox, 1),
               enamel_mm3=round(float(cap.sum()) * vox, 1),
               restoration_mm3=meta.get("restoration_mm3"),
               inferred_mm3=meta.get("inferred_mm3"),
               obscured=meta.get("obscured"),
               dentin_ref=meta.get("dentin_ref"), abs_cut=meta.get("cut"))
    out["enamel_pct"] = round(100 * out["enamel_mm3"] /
                              max(out["tooth_mm3"], 1e-6), 2)
    if z_cej is None or not cap.any():
        return out
    crown = np.zeros_like(solid)
    lo, hi = min(z_cej, z_tip), max(z_cej, z_tip)
    crown[lo:hi + 1] = solid[lo:hi + 1]
    out["crown_mm3"] = round(float(crown.sum()) * vox, 1)
    out["enamel_pct_crown"] = round(100 * out["enamel_mm3"] /
                                    max(out["crown_mm3"], 1e-6), 2)
    dz = float(spacing[2])
    sign = -1 if arch == "upper" else 1        # coronal direction in index space
    out["cervical_mm"] = {}
    for mm in LEVELS_MM:
        z = int(round(z_cej + sign * mm / dz))
        if 0 <= z < solid.shape[0]:
            t = ring_thickness(cap, solid, z, spacing)
            out["cervical_mm"][str(mm)] = None if t is None else round(t, 2)
    span = abs(z_tip - z_cej)
    out["crown_mm"] = round(span * dz, 2)
    dej = dej_distance(cap, solid, spacing)
    _ = neighbours
    # cusp tip / incisal edge: thickest enamel in the crown-most fifth
    lo5, hi5 = sorted((int(z_tip), int(round(z_tip - sign * 0.20 * span))))
    band = np.zeros_like(solid)
    band[max(lo5, 0):hi5 + 1] = True
    sel = cap & band
    out["tip_mm"] = (round(float(np.percentile(dej[sel], 95)), 2)
                     if dej is not None and sel.any() else None)
    # interproximal: the widest slice of the crown is the contact level, and
    # interproximal enamel is the thickest on the lateral face, so the upper
    # decile of ring thickness there is the figure the tables report.
    lo, hi = min(z_cej, z_tip), max(z_cej, z_tip)
    areas = [(int(solid[z].sum()), z) for z in range(lo, hi + 1)]
    if areas:
        z_contact = max(areas)[1]
        out["contact_mm"] = surface_thickness(cap, dej, z_contact)
        out["contact_z"] = int(z_contact)
    return out


def main():
    vol_path, split_dir, out_path = sys.argv[1:4]
    cut = float(sys.argv[4]) if len(sys.argv) > 4 else EN.DENTIN_MARGIN_HU
    v = Volume.load(vol_path)
    sp = np.array(v.spacing, float)
    roi = v.data.astype(np.float32)
    rep = json.load(open(os.path.join(split_dir, "split.json")))
    rows = []
    for arch in ("upper", "lower"):
        arr = np.load(os.path.join(split_dir, f"{arch}_labels.npy"))
        ids = list(range(1, int(arr.max()) + 1))
        cents = ndi.center_of_mass(arr > 0, arr, ids)
        boxes = ndi.find_objects(arr)
        for t in rep[arch]["teeth"]:
            tgt = np.array(t["world"][:2])
            best = min(ids, key=lambda s: float(np.hypot(
                v.world(cents[s-1][2], cents[s-1][1], cents[s-1][0])[0] - tgt[0],
                v.world(cents[s-1][2], cents[s-1][1], cents[s-1][0])[1] - tgt[1])))
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
            nb = (arr[sl] > 0) & (arr[sl] != best)
            rows.append(audit_tooth(roi[sl], ms, arch, t["universal"], sp, cut, nb))
    rows.sort(key=lambda r: r["universal"])
    hdr = (f"{'Univ':>4} {'type':>9} {'enamel':>7} {'%crown':>6} {'%tooth':>6} "
           f"{'1mm':>5} {'3mm':>5} {'tip':>5} {'contact':>7} {'lit':>5} "
           f"{'crownH':>6} {'infer%':>6}")
    print(f"cut = dentin + {cut:.0f} HU\n")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        c = r.get("cervical_mm", {})
        f = lambda v: f"{v:5.2f}" if isinstance(v, (int, float)) else "    -"
        pc = r.get("enamel_pct_crown")
        print(f"{r['universal']:4d} {r['type']:>9} {r['enamel_mm3']:7.1f} "
              f"{(f'{pc:6.1f}' if pc is not None else '     -')} "
              f"{r['enamel_pct']:6.1f} {f(c.get('1.0'))} {f(c.get('3.0'))} "
              f"{f(r.get('tip_mm'))} {f(r.get('contact_mm')):>7} "
              f"{LIT_CONTACT.get((r['arch'], r['type']), 0):5.2f} "
              f"{r.get('crown_mm', 0):6.2f} "
              f"{(100*(r.get('inferred_mm3') or 0)/max(r['enamel_mm3'],1e-6)):6.1f}"
              + ("  RESTORED" if r.get("obscured") else ""))
    print("\nliterature   1mm 0.48   3mm 0.81   5mm 0.95   (CBCT, maxillary "
          "central incisor, LABIAL only -- a circumferential mean reads high)")
    print("             tip 2.0-2.5 molar/premolar, ~2.0 incisal edge (Wheeler)")
    ok = [(r["contact_mm"], LIT_CONTACT.get((r["arch"], r["type"])))
          for r in rows if r.get("contact_mm") and not r.get("obscured")]
    if ok:
        d = [a_ - b for a_, b in ok if b]
        print(f"contact vs table: mean {float(np.mean(d)):+.2f} mm, "
              f"median {float(np.median(d)):+.2f}, "
              f"within 0.3 mm on {sum(1 for x in d if abs(x) <= 0.3)}/{len(d)}")
    pcts = [r["enamel_pct_crown"] for r in rows
            if r.get("enamel_pct_crown") and not r.get("obscured")]
    print(f"\nenamel / CROWN across the {len(pcts)} unrestored teeth: "
          f"{min(pcts):.1f}-{max(pcts):.1f}%, median {float(np.median(pcts)):.1f}%")
    tot = sum(r["enamel_mm3"] for r in rows)
    inf = sum(r.get("inferred_mm3") or 0 for r in rows)
    print(f"dentition enamel total: {tot:.0f} mm3, of which {inf:.0f} mm3 "
          f"({100*inf/max(tot,1e-6):.0f}%) is interpolated where the scan could "
          f"not resolve the DEJ")
    json.dump(dict(cut_over_dentin=cut, teeth=rows), open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main()
