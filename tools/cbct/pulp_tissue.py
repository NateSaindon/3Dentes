#!/usr/bin/env python3
"""Build the pulp as TISSUE: measured lumen, authored lining, schematic core.

The geometry from pulp_all.py is the pulp's outer boundary, and it is measured.
The tissue inside it is not, and cannot be from this data: dental pulp is an
odontoblast layer, cell-free and cell-rich zones, and a neurovascular core --
10-100 um structure against 160 um voxels with a worse effective resolution.

So the atlas gets three nested surfaces with their provenance kept distinct:

  MEASURED   the lumen. What the CBCT actually shows.
  AUTHORED   the predentin / odontoblast lining, an offset inside the lumen.
             Its real thickness is 10-40 um, far below anything renderable at
             atlas scale, so it is DELIBERATELY EXAGGERATED for legibility.
  SCHEMATIC  the neurovascular core, a tube along the measured centreline
             entering at the measured apical foramen.

Rendering the three alike would be lying by omission to an audience of
clinicians. Keep them separate meshes so the UI can say which is which.

Usage: python3 tools/cbct/pulp_tissue.py <pulp.json> <out-dir>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nerve import tube
from segment_tooth import write_binary_stl

LINING_FRACTION = 0.88     # exaggerated; real predentin is ~1% of a canal radius
CORE_FRACTION = 0.52
MIN_R_MM = 0.04


def main():
    pulp_path, outdir = sys.argv[1:3]
    os.makedirs(outdir, exist_ok=True)
    pulp = json.load(open(pulp_path))
    report = dict(
        provenance=dict(
            lumen="MEASURED -- intensity-deficit integration on the CBCT",
            lining="AUTHORED -- offset inside the lumen. Real predentin and the "
                   "odontoblast layer are 10-40 um, ~1% of a canal radius; this "
                   "is exaggerated to be renderable and is NOT a measurement.",
            core="SCHEMATIC -- a tube on the measured centreline entering at the "
                 "measured apical foramen. CBCT resolves the canal, not its "
                 "contents."),
        lining_fraction=LINING_FRACTION, core_fraction=CORE_FRACTION, teeth={})

    n_lin = n_core = 0
    for key in sorted(pulp, key=int):
        rec = pulp[key]
        fma = rec["fma"]
        for name, frac in (("lining", LINING_FRACTION), ("core", CORE_FRACTION)):
            vs, fs, off = [], [], 0
            for c in rec["canals"]:
                cen = np.asarray(c.get("centreline_lps", []), dtype=float)
                rad = np.asarray(c.get("radius_mm", []), dtype=float)
                if len(cen) < 4 or len(rad) != len(cen):
                    continue
                r = np.maximum(rad * frac, MIN_R_MM)
                out = tube(cen, r, nseg=16)
                if out is None:
                    continue
                v, f = out
                vs.append(v); fs.append(f + off); off += len(v)
            if vs:
                write_binary_stl(os.path.join(outdir, f"{fma}-pulp-{name}.stl"),
                                 np.vstack(vs), np.vstack(fs))
                if name == "lining":
                    n_lin += 1
                else:
                    n_core += 1
        report["teeth"][key] = dict(
            fma=fma, canals=len(rec["canals"]),
            lumen_mm3=rec.get("total_lumen_mm3"),
            core_mm3=round(float(rec.get("total_lumen_mm3", 0)) * CORE_FRACTION ** 2, 2))
    with open(os.path.join(outdir, "pulp-tissue.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(f"lining meshes: {n_lin}   core meshes: {n_core}")
    tot = sum(t["lumen_mm3"] or 0 for t in report["teeth"].values())
    core = sum(t["core_mm3"] for t in report["teeth"].values())
    print(f"measured lumen {tot:.1f} mm3 -> schematic neurovascular core "
          f"{core:.1f} mm3 ({CORE_FRACTION**2*100:.0f}% by area)")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
