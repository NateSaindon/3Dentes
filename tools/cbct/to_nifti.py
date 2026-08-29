#!/usr/bin/env python3
"""Convert the gzipped NRRDs from prepare.py to NIfTI for nnU-Net inference.

DICOM patient space is LPS; NIfTI's sform/qform convention is RAS. The two
differ by a sign flip on x and y, so the affine written here negates those two
axes. Get this wrong and the volume is mirrored -- which the atlas's laterality
assertion would eventually catch, but only after a model had been run on a
flipped scan and its output silently mislabelled left and right.

Usage: python3 tools/cbct/to_nifti.py <in.nrrd> <out.nii.gz>
"""
import gzip, os, struct, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume


def write_nifti(path, data_zyx, origin_lps, spacing_xyz):
    # nibabel writes x-fastest; our array is (z, y, x), so transpose to (x, y, z)
    arr = np.ascontiguousarray(np.transpose(data_zyx, (2, 1, 0)).astype(np.int16))
    hdr = bytearray(348)
    struct.pack_into("<i", hdr, 0, 348)
    struct.pack_into("<h", hdr, 40, 3)                       # dim[0] = 3 dims
    for i, n in enumerate(arr.shape):
        struct.pack_into("<h", hdr, 42 + 2 * i, n)
    for i in range(len(arr.shape), 7):
        struct.pack_into("<h", hdr, 42 + 2 * i, 1)
    struct.pack_into("<h", hdr, 70, 4)                       # datatype = int16
    struct.pack_into("<h", hdr, 72, 16)                      # bitpix
    struct.pack_into("<f", hdr, 76, 1.0)                     # pixdim[0]
    for i, s in enumerate(spacing_xyz):
        struct.pack_into("<f", hdr, 80 + 4 * i, float(s))
    struct.pack_into("<f", hdr, 108, 352.0)                  # vox_offset
    struct.pack_into("<f", hdr, 112, 1.0)                    # scl_slope
    struct.pack_into("<f", hdr, 116, 0.0)                    # scl_inter
    struct.pack_into("<h", hdr, 252, 1)                      # qform_code
    struct.pack_into("<h", hdr, 254, 1)                      # sform_code
    # LPS -> RAS: negate x and y
    srow = [[-spacing_xyz[0], 0.0, 0.0, -origin_lps[0]],
            [0.0, -spacing_xyz[1], 0.0, -origin_lps[1]],
            [0.0, 0.0, spacing_xyz[2], origin_lps[2]]]
    for r in range(3):
        for c in range(4):
            struct.pack_into("<f", hdr, 280 + 16 * r + 4 * c, srow[r][c])
    hdr[344:348] = b"n+1\x00"
    with gzip.open(path, "wb") as f:
        f.write(bytes(hdr))
        f.write(b"\0" * 4)                                   # pad to vox_offset
        f.write(arr.tobytes(order="F"))


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    v = Volume.load(sys.argv[1])
    write_nifti(sys.argv[2], v.data, v.origin, v.spacing)
    print(f"{sys.argv[2]}  shape(x,y,z)={v.data.shape[::-1]}  "
          f"spacing={tuple(v.spacing)}  origin_lps={tuple(v.origin)}  "
          f"{os.path.getsize(sys.argv[2])/1e6:.0f} MB")


if __name__ == "__main__":
    main()
