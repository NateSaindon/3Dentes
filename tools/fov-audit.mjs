#!/usr/bin/env node
// What did the scan actually see, and where does the data stop?
//
//   node tools/fov-audit.mjs
//
// Every mesh here comes from an 81.9 x 81.9 x 81.76 mm cone-beam volume
// (docs/cbct-survey.md §2). Anatomy larger than that box is not partly missing,
// it is CUT, and the cut is detectable: a truncated surface terminates in a
// planar cap where the FOV wall sliced it, while intact anatomy closes over
// smoothly. So for each structure we measure the bounding box AND the area of
// any flat cap sitting on a bounding-box face.
//
// This answers two questions the wishlist leaves open — whether the condyle,
// glenoid fossa and articular eminence were ever measured (they gate both the
// Gow-Gates target and a patient-specific mouth-opening path), and where a
// generated skull would have to take over from measured bone.
//
// Native STL frame, matching tools/cbct/: +x patient LEFT, +y POSTERIOR,
// +z SUPERIOR. build-assets.mjs rotates this to y-up for the .glb; the audit
// stays in the native frame because that is the frame the scan was in.

import { readFile } from 'node:fs/promises';
import { readdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { STRUCTURES, STL_DIR as STL_SUBDIR, structureName } from './manifest.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const STL_DIR = join(ROOT, ...STL_SUBDIR);

// docs/cbct-survey.md §2 — all three volumes, identical geometry.
const FOV = [81.9, 81.9, 81.76];

// A vertex this close to a bounding-box face counts as lying ON it. 0.3 mm is
// just under two voxels: tight enough that curved anatomy grazing the extreme
// does not qualify, loose enough to survive decimation of a real cut face.
const FACE_TOL = 0.3;

const AXIS = [
  { name: 'x', neg: 'right',    pos: 'left'     },
  { name: 'y', neg: 'anterior', pos: 'posterior'},
  { name: 'z', neg: 'inferior', pos: 'superior' },
];

function parseBinarySTL(buf) {
  const n = buf.readUInt32LE(80);
  const tris = new Float32Array(n * 9);
  for (let i = 0; i < n; i++) {
    const o = 84 + i * 50 + 12;   // skip the facet normal
    for (let j = 0; j < 9; j++) tris[i * 9 + j] = buf.readFloatLE(o + j * 4);
  }
  return tris;
}

function triArea(t, i) {
  const ax = t[i+3]-t[i],   ay = t[i+4]-t[i+1], az = t[i+5]-t[i+2];
  const bx = t[i+6]-t[i],   by = t[i+7]-t[i+1], bz = t[i+8]-t[i+2];
  const cx = ay*bz - az*by, cy = az*bx - ax*bz, cz = ax*by - ay*bx;
  return Math.hypot(cx, cy, cz) / 2;
}

/** Bounding box, total area, and the flat-cap area on each of the six faces. */
function analyse(tris) {
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < tris.length; i += 3)
    for (let a = 0; a < 3; a++) {
      if (tris[i+a] < min[a]) min[a] = tris[i+a];
      if (tris[i+a] > max[a]) max[a] = tris[i+a];
    }

  const caps = [[0,0],[0,0],[0,0]];   // [axis][0=min face, 1=max face]
  const capBox = [[emptyBox(),emptyBox()],[emptyBox(),emptyBox()],[emptyBox(),emptyBox()]];
  let area = 0;
  for (let i = 0; i < tris.length; i += 9) {
    const A = triArea(tris, i);
    area += A;
    for (let a = 0; a < 3; a++) {
      // All three vertices on the same bounding-box face => the triangle is
      // part of a flat cap there.
      let onMin = true, onMax = true;
      for (let v = 0; v < 3; v++) {
        const c = tris[i + v*3 + a];
        if (c - min[a] > FACE_TOL) onMin = false;
        if (max[a] - c > FACE_TOL) onMax = false;
      }
      if (onMin) { caps[a][0] += A; growCap(capBox[a][0], tris, i); }
      if (onMax) { caps[a][1] += A; growCap(capBox[a][1], tris, i); }
    }
  }
  return { min, max, area, caps, capBox };
}

/** Where on the structure a cut sits matters as much as how big it is. */
function emptyBox() { return { min: [Infinity,Infinity,Infinity], max: [-Infinity,-Infinity,-Infinity] }; }
function growCap(box, tris, i) {
  for (let v = 0; v < 3; v++)
    for (let a = 0; a < 3; a++) {
      const c = tris[i + v*3 + a];
      if (c < box.min[a]) box.min[a] = c;
      if (c > box.max[a]) box.max[a] = c;
    }
}

const files = new Set(await readdir(STL_DIR));
const seen = new Set();
const results = [];
for (const s of STRUCTURES) {
  if (seen.has(s.fma)) continue;
  seen.add(s.fma);
  if (!files.has(`${s.fma}.stl`)) continue;
  const r = analyse(parseBinarySTL(await readFile(join(STL_DIR, `${s.fma}.stl`))));
  results.push({ s, ...r });
}

const gmin = [0,1,2].map((a) => Math.min(...results.map((r) => r.min[a])));
const gmax = [0,1,2].map((a) => Math.max(...results.map((r) => r.max[a])));

console.log('=== Extent of all measured anatomy (native scan frame, mm) ===\n');
for (let a = 0; a < 3; a++) {
  const span = gmax[a] - gmin[a];
  const pct = (span / FOV[a]) * 100;
  console.log(`  ${AXIS[a].name}  ${gmin[a].toFixed(1).padStart(7)} .. ${gmax[a].toFixed(1).padStart(7)}` +
              `   span ${span.toFixed(1).padStart(5)} mm of ${FOV[a].toFixed(1)} mm FOV  (${pct.toFixed(0)}%)` +
              `   ${AXIS[a].neg} <-> ${AXIS[a].pos}`);
}

console.log('\n=== Per structure: bounding box, and flat caps where the FOV cut it ===\n');
const big = results.filter((r) => r.s.layer !== 'pulp' && r.s.layer !== 'pdl' && r.s.layer !== 'teeth');
for (const r of big) {
  const name = structureName(r.s);
  console.log(`  ${name}`);
  for (let a = 0; a < 3; a++) {
    console.log(`    ${AXIS[a].name}  ${r.min[a].toFixed(1).padStart(7)} .. ${r.max[a].toFixed(1).padStart(7)}` +
                `  (${(r.max[a]-r.min[a]).toFixed(1).padStart(5)} mm)`);
  }
  const cut = [];
  for (let a = 0; a < 3; a++)
    for (const [i, side] of [[0, AXIS[a].neg], [1, AXIS[a].pos]])
      if (r.caps[a][i] > 1) cut.push({ side, area: r.caps[a][i], box: r.capBox[a][i] });
  console.log(`    surface ${r.area.toFixed(0)} mm²` +
              (cut.length ? '' : '   no flat cap — closes smoothly'));
  // A cap over ~50 mm² is a substantial slice through real bone rather than a
  // few triangles grazing the extreme, so say where it runs.
  for (const c of cut) {
    const span = c.area > 50
      ? `  spanning y ${c.box.min[1].toFixed(0)}..${c.box.max[1].toFixed(0)}, z ${c.box.min[2].toFixed(0)}..${c.box.max[2].toFixed(0)}`
      : '';
    console.log(`      cut on ${c.side}: ${c.area.toFixed(0)} mm²${span}`);
  }
  console.log();
}
