"""Minimal NIfTI-1 reader for nnU-Net's label output. No nibabel dependency."""
import gzip
import struct

import numpy as np

DTYPE = {2: np.uint8, 4: np.int16, 8: np.int32, 16: np.float32, 512: np.uint16}


def read_nifti(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rb") as f:
        buf = f.read()
    if len(buf) < 348:
        raise ValueError("too short for a NIfTI header")
    little = struct.unpack_from("<i", buf, 0)[0] == 348
    e = "<" if little else ">"
    ndim = struct.unpack_from(e + "h", buf, 40)[0]
    # dim[0] is the dimensionality at offset 40; dim[1..] start at 42.
    dims = [struct.unpack_from(e + "h", buf, 42 + 2 * i)[0] for i in range(ndim)]
    code = struct.unpack_from(e + "h", buf, 70)[0]
    if code not in DTYPE:
        raise ValueError(f"unsupported NIfTI datatype {code}")
    # likewise pixdim[0] is the qfac at offset 76; pixdim[1..] start at 80.
    pixdim = [struct.unpack_from(e + "f", buf, 80 + 4 * i)[0] for i in range(3)]
    off = int(struct.unpack_from(e + "f", buf, 108)[0])
    srow = np.array([[struct.unpack_from(e + "f", buf, 280 + 16 * r + 4 * c)[0]
                      for c in range(4)] for r in range(3)])
    n = int(np.prod(dims))
    arr = np.frombuffer(buf, dtype=np.dtype(DTYPE[code]).newbyteorder(e),
                        count=n, offset=off)
    # the file is x-fastest; return (z, y, x) to match Volume
    arr = arr.reshape(dims, order="F").T
    return np.ascontiguousarray(arr), srow, tuple(pixdim)
