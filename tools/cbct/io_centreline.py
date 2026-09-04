#!/usr/bin/env python3
"""Turn the traced infraorbital canals into centrelines in the ATLAS frame.

The tracing is done in the maxillary exposure, which is the exposure that
measured this region. Rule 113 applies unchanged: the geometry is derived in the
MOVING grid and only the finished POINTS are carried into the atlas frame, never
resampled as voxels -- the exposures sit tens of millimetres apart and a
resample discards precisely the anatomy that only one of them saw.

The canal's own radius is recorded alongside the centreline but is NOT what gets
drawn. The canal carries the infraorbital nerve, artery and vein together, so
its lumen is wider than the nerve; the same reasoning the inferior alveolar
nerve already follows, where a tube of chosen calibre sits on a measured canal
and the result is `derived` rather than `measured`.

Usage: io_centreline.py <maxillary.nrrd> <centred.nrrd> <transform.json>
                        <centred-pred.nii.gz> <traced-dir> <out.json>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402
from read_nifti import read_nifti                          # noqa: E402

SLAB_MM = 1.0          # spacing of centreline samples along the canal


def fixed_index_of(moving_idx, R, t_vox, centre):
    """Moving-grid index (z,y,x) -> fixed-grid index, register.py's convention."""
    return (np.asarray(moving_idx, float) - centre + t_vox) @ R.T + centre


def centreline(mask, vm, slab_mm=SLAB_MM):
    """Ordered points down the canal, in MOVING world mm, with a radius each."""
    sp = np.array(vm.spacing, float)
    zz, yy, xx = np.where(mask)
    P = np.stack([vm.origin[0] + xx * sp[0],
                  vm.origin[1] + yy * sp[1],
                  vm.origin[2] + zz * sp[2]], axis=1)
    c = P.mean(0)
    _, _, Vt = np.linalg.svd(P - c, full_matrices=False)
    ax = Vt[0]
    t = (P - c) @ ax
    out = []
    for lo in np.arange(t.min(), t.max() + 1e-6, slab_mm):
        sel = (t >= lo) & (t < lo + slab_mm)
        if sel.sum() < 8:
            continue
        pts = P[sel]
        area = float(sel.sum()) * float(np.prod(sp)) / slab_mm
        out.append((pts.mean(0), float(np.sqrt(max(area, 1e-6) / np.pi))))
    # orient anterior-first: anterior is -y in LPS
    if len(out) > 1 and out[0][0][1] > out[-1][0][1]:
        out = out[::-1]
    return out


def main():
    # The seventh argument is the tracing's name prefix. It was hardcoded to
    # 'io' when the infraorbital canal was the only thing traced this way; the
    # mental canal is the second, and the module is otherwise identical -- the
    # transform, the exposure and the structure all come in as arguments
    # already, so there was never anything maxillary about the code.
    (mp, cp, tp, pred, tdir, outp) = sys.argv[1:7]
    prefix = sys.argv[7] if len(sys.argv) > 7 else 'io'
    vm = Volume.load(mp)
    vc = Volume.load(cp)
    p = json.load(open(tp))
    R = np.array(p['rotation_matrix'], float)
    fl, _, pix = read_nifti(pred)
    spf = np.array([float(x) for x in pix], float)
    t_vox = np.asarray(p['translation_mm']) / spf
    centre = np.array(ndi.center_of_mass(fl == p['label']))
    spm = np.array(vm.spacing, float)

    out = {}
    for side in ('right', 'left'):
        f = os.path.join(tdir, f'{prefix}-{side}.npy')
        if not os.path.exists(f):
            print(f'{side}: not traced')
            continue
        mask = np.load(f)
        pts = centreline(mask, vm)
        if len(pts) < 3:
            print(f'{side}: too few samples')
            continue
        rows = []
        for w, rad in pts:
            mi = ((w[2] - vm.origin[2]) / spm[2],
                  (w[1] - vm.origin[1]) / spm[1],
                  (w[0] - vm.origin[0]) / spm[0])
            fi = fixed_index_of(mi, R, t_vox, centre)
            wx, wy, wz = vc.world(fi[2], fi[1], fi[0])
            rows.append(dict(p=[round(wx, 3), round(wy, 3), round(wz, 3)],
                             canal_r_mm=round(rad, 3)))
        L = sum(float(np.linalg.norm(np.array(rows[i + 1]['p'])
                                     - np.array(rows[i]['p'])))
                for i in range(len(rows) - 1))
        rr = [r['canal_r_mm'] for r in rows]
        vol = float(mask.sum()) * float(np.prod(spm))
        out[side] = dict(points=rows, length_mm=round(L, 2),
                         canal_mm3=round(vol, 1),
                         canal_r_mm=[round(min(rr), 2), round(max(rr), 2)])
        print(f'{side}: {len(rows)} samples, {L:.1f} mm in the atlas frame, '
              f'canal {vol:.1f} mm3, radius {min(rr):.2f}-{max(rr):.2f} mm')
        a = np.array(rows[0]['p']); b = np.array(rows[-1]['p'])
        print(f'   anterior end (foramen) {np.round(a,1)}  ->  posterior end {np.round(b,1)}')
    meta = dict(
        provenance='MEASURED -- hand-traced by the operator on cross-sections '
                   'cut perpendicular to the canal axis in the '
                   f'{os.path.basename(mp)} exposure, 1 mm apart, then carried '
                   'into the atlas frame as '
                   'points (rule 113).',
        note='canal_r_mm is the CANAL, which carries the nerve, artery and vein '
             'together. It is recorded, not drawn.',
        sides=out)
    json.dump(meta, open(outp, 'w'), indent=1)
    print(f'-> {outp}')


if __name__ == '__main__':
    main()
