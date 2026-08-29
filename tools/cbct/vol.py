"""Load the gzipped NRRDs written by prepare.py. No external NRRD dependency."""
import gzip
import numpy as np


class Volume:
    """(z, y, x) int16 array plus its LPS geometry.

    Index order is (z, y, x); world order is (x, y, z). Keeping the two straight
    is the whole job of this class -- get it wrong and every measurement and
    every laterality check downstream inherits the error.
    """

    def __init__(self, data, origin, spacing):
        self.data = data
        self.origin = np.asarray(origin, dtype=float)    # x, y, z
        self.spacing = np.asarray(spacing, dtype=float)  # x, y, z

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            hdr = {}
            while True:
                line = f.readline()
                if line in (b"\n", b"\r\n", b""):
                    break
                t = line.decode("ascii").strip()
                if t.startswith("#") or t.startswith("NRRD"):
                    continue
                k, v = t.split(":", 1)
                hdr[k.strip()] = v.strip()
            payload = f.read()
        if hdr.get("encoding") != "gzip":
            raise ValueError(f"unsupported encoding {hdr.get('encoding')!r}")
        nx, ny, nz = (int(v) for v in hdr["sizes"].split())
        data = np.frombuffer(gzip.decompress(payload), dtype="<i2").reshape(nz, ny, nx)
        origin = [float(v) for v in hdr["space origin"].strip("()").split(",")]
        dirs = hdr["space directions"].split(") (")
        spacing = [abs(float(d.strip("() ").split(",")[i])) for i, d in enumerate(dirs)]
        return cls(np.array(data), origin, spacing)

    def world(self, ix, iy, iz):
        """Index -> LPS millimetres. Negative x is the patient's right."""
        return (self.origin[0] + ix * self.spacing[0],
                self.origin[1] + iy * self.spacing[1],
                self.origin[2] + iz * self.spacing[2])

    def index(self, x, y, z):
        return (int(round((x - self.origin[0]) / self.spacing[0])),
                int(round((y - self.origin[1]) / self.spacing[1])),
                int(round((z - self.origin[2]) / self.spacing[2])))

    @property
    def shape_zyx(self):
        return self.data.shape
