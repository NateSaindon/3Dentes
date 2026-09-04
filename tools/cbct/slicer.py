#!/usr/bin/env python3
"""A scrollable slice viewer the operator can paint in, served on localhost.

WHY THIS EXISTS. Everything hand-traced in this atlas so far -- 28 pulps over
three rounds, two infraorbital canals, two mental canals over two rounds -- was
marked on STATIC PNG CONTACT SHEETS, because a sheet is a thing the importer can
read. It is not a thing a reader wants. The operator put it plainly: "it's hard
for me to orient the anatomy if I'm not able to slice through actively myself".
He is right, and it has cost accuracy: the mental canal needed a second round,
and the first round of pulp tracing failed outright because axial sheets 1.6 mm
apart cannot represent a canal that wanders (leave-one-out Dice 0.076).

The fix is not a better sheet. It is scrubbing, in three linked planes, with the
brush in the same window as the anatomy.

WHAT IT EMITS is exactly what `trace_canal.py import` emits -- one boolean .npy
per structure on the volume's own grid, plus a `traced.json` summary -- so
everything downstream reads it without knowing which tool produced it:
`io_centreline.py`, `combine_traces.py`, `trace_foramina.py`, all unchanged.
Rule 113 is respected by construction: the mask is in the grid of the exposure
being viewed, and only finished points ever leave it.

NO SMOOTHING, NO INTERPOLATION, NO CLOSING. The sheet importer had to close
across 1 mm gaps because the sections were 1 mm apart; here the operator can
paint every slice, so what is saved is what was painted. If a structure comes
out wrong afterwards, the tracing is what changes -- trace_kit.py's rule, and
it only holds if nothing is added between the brush and the file.

Usage:
    slicer.py <volume.nrrd> <out-dir> --names mental-right,mental-left
              [--mask <dir>[,<dir>...]] [--roi x0,x1,y0,y1,z0,z1]  (world mm)
              [--port 8787]

    slicer.py <volume.nrrd> <out-dir> --tooth 30,31

`--tooth` names the structures `pulp-<n>` and crops to those teeth, which is
what makes the pulp affordable: a whole-volume mask is 134 MB and 28 of them do
not fit in memory, while a tooth-sized crop is about two.

Then open http://127.0.0.1:8787/ . Nothing is written until you press Save.
"""
import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PAD_XY, PAD_Z = 9.0, 14.0   # margin around a tooth centre, in mm

# Plane 0 = axial (constant z), 1 = coronal (constant y), 2 = sagittal (const x).
# The volume is indexed (z, y, x) throughout this project.
PLANES = ("axial", "coronal", "sagittal")


class State:
    def __init__(self, vol_path, names, out_dir, roi=None):
        v = Volume.load(vol_path)
        self.origin = np.array(v.origin, float)
        self.spacing = np.array(v.spacing, float)
        self.full_shape = np.array(v.data.shape)          # z, y, x
        self.lo = np.zeros(3, int)
        data = v.data
        if roi is not None:
            # ROI is given in world mm as x0,x1,y0,y1,z0,z1; convert to index
            # slices. Cropping matters for the pulp, where the operator works on
            # one tooth at a time and the rest of the head is noise.
            (x0, x1, y0, y1, z0, z1) = roi
            i0 = np.array([(z0 - self.origin[2]) / self.spacing[2],
                           (y0 - self.origin[1]) / self.spacing[1],
                           (x0 - self.origin[0]) / self.spacing[0]])
            i1 = np.array([(z1 - self.origin[2]) / self.spacing[2],
                           (y1 - self.origin[1]) / self.spacing[1],
                           (x1 - self.origin[0]) / self.spacing[0]])
            self.lo = np.clip(np.floor(np.minimum(i0, i1)), 0,
                              self.full_shape - 1).astype(int)
            hi = np.clip(np.ceil(np.maximum(i0, i1)) + 1, 1,
                         self.full_shape).astype(int)
            data = data[self.lo[0]:hi[0], self.lo[1]:hi[1], self.lo[2]:hi[2]]
        self.data = np.ascontiguousarray(data.astype(np.int16))
        self.shape = np.array(self.data.shape)
        self.names = list(names)
        self.out_dir = out_dir
        self.vol_path = vol_path
        # Masks are held on the CROPPED grid and expanded to the full grid only
        # at save time. On the full grid each is 134 MB, which is fine for the
        # two sides of a canal and hopeless for the pulp: 28 teeth would want
        # 3.7 GB of mostly-empty array. With a per-tooth --roi the same 28 cost
        # a few megabytes each. Allocated lazily, so a name you never touch
        # costs nothing either.
        self.masks = {}
        self.lock = threading.Lock()

    def mask(self, name):
        m = self.masks.get(name)
        if m is None:
            m = self.masks[name] = np.zeros(self.shape, bool)
        return m

    # --- index helpers ------------------------------------------------------
    def full_index(self, plane, i):
        return int(i + self.lo[plane])

    def slice_of(self, arr, plane, i):
        """One slice. Indexed LAZILY, which is the whole point.

        This used to build the tuple `(arr[i], arr[:, i, :], arr[:, :, i])` and
        subscript it, so all three were evaluated whatever plane was asked for.
        On a cube that is merely wasteful. On anything else it is a bug: with a
        185 x 185 x 135 tooth crop, axial slice 135 passes its own bounds check
        and then raises IndexError on the sagittal expression, the handler dies
        without writing a response, and the pane goes black with no message.
        Every plane past the SHORTEST axis was unreachable.

        It survived testing because the only volume tested against was 512^3,
        where all three axes are the same length -- and the `--tooth` flag, whose
        entire purpose is to produce a crop that is not a cube, was added after.
        """
        if plane == 0:
            return arr[i]
        if plane == 1:
            return arr[:, i, :]
        return arr[:, :, i]

    def mask_view(self, name, plane, i):
        """The mask slice matching the image slice, same shape, a live view."""
        return self.slice_of(self.mask(name), plane, i)

    def write_mask_slice(self, name, plane, i, flat):
        if name not in self.names:
            raise KeyError(name)
        h, w = self.slice_of(self.data, plane, i).shape
        painted = np.frombuffer(flat, np.uint8).reshape(h, w).astype(bool)
        with self.lock:
            self.mask_view(name, plane, i)[...] = painted

    def _crop(self):
        return tuple(slice(self.lo[k], self.lo[k] + self.shape[k]) for k in range(3))

    def load_existing(self, spec):
        """Continue from one or more directories of masks, first match wins.

        A comma-separated list, because the masks for one session often come
        from different places: the operator's own tracings in one directory and
        a machine prediction awaiting his correction in another, kept apart on
        purpose so that what was traced and what was guessed never share a
        folder.
        """
        loaded = []
        for n in self.names:
            f = None
            for part in str(spec).split(","):
                part = part.strip()
                if not part:
                    continue
                cand = part if os.path.isfile(part) else os.path.join(part, f"{n}.npy")
                if os.path.exists(cand):
                    f = cand
                    break
            if f is None:
                continue
            m = np.load(f)
            if m.shape != tuple(self.full_shape):
                print(f"  {n}: {f} is {m.shape}, this volume is "
                      f"{tuple(self.full_shape)} — skipped")
                continue
            self.masks[n] = np.ascontiguousarray(m[self._crop()]).astype(bool)
            loaded.append(f"{n} ({int(m.sum())} voxels from {os.path.dirname(f) or f})")
        if loaded:
            print("  continuing from: " + ", ".join(loaded))

    def save(self):
        os.makedirs(self.out_dir, exist_ok=True)
        vox = float(np.prod(self.spacing))
        report = {}
        with self.lock:
            for n in self.names:
                sub = self.masks.get(n)
                if sub is None or not sub.any():
                    continue
                # Written on the FULL grid whatever was cropped for viewing, so
                # the file means the same thing to everything downstream.
                m = np.zeros(self.full_shape, bool)
                m[self._crop()] = sub
                np.save(os.path.join(self.out_dir, f"{n}.npy"), m)
                # How many slices carry paint, per plane — the honest measure of
                # how much of the structure was actually looked at.
                report[n] = dict(
                    voxels=int(m.sum()), mm3=round(float(m.sum()) * vox, 2),
                    slices_axial=int((m.any(axis=(1, 2))).sum()),
                    slices_coronal=int((m.any(axis=(0, 2))).sum()),
                    slices_sagittal=int((m.any(axis=(0, 1))).sum()),
                    source=os.path.basename(self.vol_path), tool="slicer.py")
        with open(os.path.join(self.out_dir, "traced.json"), "w") as fh:
            json.dump(report, fh, indent=1)
        return report


def make_handler(st, page):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass                                   # the console is for the tool

        def _send(self, body, ctype="application/octet-stream", code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _fail(self, e):
            # Answer with a 500 instead of dropping the connection. A dead socket
            # reaches the page as a rejected fetch and an unexplained black pane;
            # a 500 reaches it as something it can put on screen.
            import traceback
            traceback.print_exc()
            body = f"{type(e).__name__}: {e}".encode()
            try:
                self._send(body, "text/plain", 500)
            except Exception:
                pass

        def handle_one_request(self):
            try:
                BaseHTTPRequestHandler.handle_one_request(self)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

        def do_GET(self):
            try:
                self._get()
            except Exception as e:
                self._fail(e)

        def do_POST(self):
            try:
                self._post()
            except Exception as e:
                self._fail(e)

        def _get(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/":
                return self._send(page.encode(), "text/html; charset=utf-8")
            if u.path == "/meta":
                m = dict(shape=[int(x) for x in st.shape],
                         full_shape=[int(x) for x in st.full_shape],
                         lo=[int(x) for x in st.lo],
                         spacing=[float(x) for x in st.spacing],
                         origin=[float(x) for x in st.origin],
                         names=st.names, planes=list(PLANES),
                         volume=os.path.basename(st.vol_path),
                         out=st.out_dir)
                return self._send(json.dumps(m).encode(), "application/json")
            if u.path == "/slice":
                p = int(q["plane"][0]); i = int(q["i"][0])
                if not (0 <= p < 3) or not (0 <= i < st.shape[p]):
                    return self._send(b"", code=404)
                a = np.ascontiguousarray(st.slice_of(st.data, p, i))
                return self._send(a.tobytes())
            if u.path == "/mask":
                p = int(q["plane"][0]); i = int(q["i"][0])
                name = q["name"][0]
                if name not in st.names or not (0 <= i < st.shape[p]):
                    return self._send(b"", code=404)
                with st.lock:
                    a = np.ascontiguousarray(st.mask_view(name, p, i)).astype(np.uint8)
                return self._send(a.tobytes())
            if u.path == "/counts":
                with st.lock:
                    c = {n: int(m.sum()) for n, m in st.masks.items()}
                    c.update({n: c.get(n, 0) for n in st.names})
                return self._send(json.dumps(c).encode(), "application/json")
            return self._send(b"not found", "text/plain", 404)

        def _post(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n) if n else b""
            if u.path == "/mask":
                st.write_mask_slice(q["name"][0], int(q["plane"][0]),
                                    int(q["i"][0]), body)
                return self._send(b"ok", "text/plain")
            if u.path == "/save":
                rep = st.save()
                print("saved:", json.dumps(rep))
                return self._send(json.dumps(rep).encode(), "application/json")
            return self._send(b"not found", "text/plain", 404)
    return H


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        raise SystemExit(__doc__)
    vol_path, out_dir = a[0], a[1]
    opt = {}
    i = 2
    while i < len(a) - 1:
        opt[a[i].lstrip("-")] = a[i + 1]
        i += 2
    # --tooth is the pulp workflow in one flag: it names the structures and
    # crops to the teeth, which is what makes 28 of them affordable at once.
    names = [s.strip() for s in opt.get("names", "trace").split(",") if s.strip()]
    if opt.get("tooth"):
        want = [int(x) for x in opt["tooth"].split(",")]
        split = json.load(open(os.path.join(HERE, "..", "..", "docs",
                                            "cbct-teeth-split.json")))
        seen = {t["universal"]: t["world"] for arch in split.values()
                for t in arch["teeth"]}
        missing = [u for u in want if u not in seen]
        if missing:
            raise SystemExit(f"no such tooth in cbct-teeth-split.json: {missing}")
        P = np.array([seen[u] for u in want], float)
        pad = np.array([PAD_XY, PAD_XY, PAD_Z])
        lo_w, hi_w = P.min(0) - pad, P.max(0) + pad
        opt["roi"] = ",".join(f"{v:.1f}" for v in
                              (lo_w[0], hi_w[0], lo_w[1], hi_w[1], lo_w[2], hi_w[2]))
        names = [f"pulp-{u}" for u in want]
        print(f"tooth {want} -> {names}, cropped to their extent + "
              f"{PAD_XY:.0f}/{PAD_Z:.0f} mm")
    for n in names:
        if not NAME_RE.match(n):
            raise SystemExit(f"bad structure name {n!r}: letters, digits, . _ - only")
    roi = None
    if opt.get("roi"):
        roi = [float(x) for x in opt["roi"].split(",")]
        if len(roi) != 6:
            raise SystemExit("--roi needs x0,x1,y0,y1,z0,z1 in world mm")
    port = int(opt.get("port", 8787))

    st = State(vol_path, names, out_dir, roi)
    if opt.get("mask"):
        st.load_existing(opt["mask"])
    page = open(os.path.join(HERE, "slicer.html")).read()

    lo_w = st.origin + st.lo[::-1] * st.spacing
    hi_w = lo_w + (st.shape[::-1] - 1) * st.spacing
    print(f"volume   {os.path.basename(vol_path)}  "
          f"{'x'.join(str(int(n)) for n in st.shape)} voxels at "
          f"{st.spacing[0]:.2f} mm"
          + ("  (cropped from 512x512x512)" if st.shape.tolist()
             != st.full_shape.tolist() else ""))
    print(f"extent   x {lo_w[0]:.1f}..{hi_w[0]:.1f}  y {lo_w[1]:.1f}..{hi_w[1]:.1f}  "
          f"z {lo_w[2]:.1f}..{hi_w[2]:.1f}  (world mm, this volume's own frame)")
    print(f"tracing  {', '.join(names)}")
    print(f"saves to {out_dir}/<name>.npy  (nothing is written until you press Save)")
    print(f"\n  http://127.0.0.1:{port}/\n")
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(st, page))
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped. Unsaved paint is gone; press Save before quitting.")


if __name__ == "__main__":
    main()
