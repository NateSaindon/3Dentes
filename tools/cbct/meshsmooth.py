"""Taubin mesh smoothing.

Marching cubes on voxel data terraces at the voxel pitch and carries the
segmentation's noise into the surface. Decimating that directly -- which is what
the first export did -- does not remove the noise, it turns it into facets: a
quadric decimator faithfully preserves the sharp features it is given, and voxel
stair-steps look exactly like sharp features.

So the surface is smoothed BEFORE it is decimated.

Taubin rather than plain Laplacian. Laplacian smoothing shrinks a closed surface
a little on every pass, which over 15 passes visibly thins a tooth and would make
the enamel cap retreat inside the dentin it is supposed to cover. Taubin
alternates a positive step (lambda) with a slightly larger negative one (mu), so
low-frequency shape is preserved while high-frequency noise is removed, and the
volume stays put.
"""
import numpy as np
from scipy import sparse


def _adjacency(n_verts, faces):
    e = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    e = np.vstack([e, e[:, ::-1]])
    data = np.ones(len(e), dtype=np.float32)
    A = sparse.coo_matrix((data, (e[:, 0], e[:, 1])),
                          shape=(n_verts, n_verts)).tocsr()
    A.data[:] = 1.0                      # collapse duplicate edges
    deg = np.asarray(A.sum(axis=1)).ravel()
    deg[deg == 0] = 1.0
    return A, deg


def taubin(verts, faces, iterations=12, lam=0.5, mu=-0.53):
    """Volume-preserving smoothing. Returns new vertices; faces are unchanged."""
    v = np.asarray(verts, dtype=np.float64).copy()
    if len(faces) == 0:
        return v
    A, deg = _adjacency(len(v), np.asarray(faces))
    inv = sparse.diags(1.0 / deg)
    for _ in range(iterations):
        for step in (lam, mu):
            v += step * (inv @ (A @ v) - v)
    return v


def mesh_volume(verts, faces):
    """Signed volume via the divergence theorem, for checking shrinkage."""
    t = np.asarray(verts)[np.asarray(faces)]
    return abs(float(np.einsum("ij,ij->i", t[:, 0],
                               np.cross(t[:, 1], t[:, 2])).sum() / 6.0))


def weld(tri_soup, decimals=6):
    """Triangle soup -> (vertices, faces) with shared vertices.

    Smoothing and decimation both need real connectivity. On a soup -- every
    triangle carrying its own three vertices, which is what a binary STL stores --
    the adjacency graph has no shared edges, so Taubin smoothing pulls each
    triangle toward its own centroid and collapses it to zero area. The mesh
    stays "valid" and renders as nothing.

    Rounding before the unique() is safe here because this welds meshes that were
    just written out as float32 from a common grid; it is not the exact-vertex
    weld in build-assets.mjs, whose whole point is to avoid a tolerance.
    """
    import numpy as np
    v = np.asarray(tri_soup, dtype=np.float64).reshape(-1, 3)
    key = np.round(v, decimals)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    verts = v[idx]
    faces = inv.reshape(-1, 3)
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    return verts, faces[keep]
