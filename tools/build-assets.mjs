#!/usr/bin/env node
// Build assets/source/stl/*.stl into a single public/dentition.glb, plus the
// public/teeth.json metadata the app joins against by FMA id.
//
//   node tools/build-assets.mjs
//
// Binary STL is a flat triangle soup: no shared vertices, no vertex normals.
// Converting it naively gives ~1M unwelded vertices and hard-faceted shading.
// So per structure we weld bitwise-identical vertices (which recovers the
// original mesh topology exactly, because these STLs were converted from an OBJ
// whose shared vertices have identical float bits) and then compute smooth
// area-weighted vertex normals.
//
// NOTE: @gltf-transform's normals() generates FLAT normals, which is not what we
// want, hence computeSmoothNormals below.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Document, NodeIO } from '@gltf-transform/core';
import { STRUCTURES, LAYERS, toothNotation, structureName, SOURCE_DIRS, TOOTH_SOURCE } from './manifest.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const STL_DIR = join(ROOT, 'assets', 'source', 'stl');
const OUT_DIR = join(ROOT, 'public');

// Per-layer appearance. Kept here so the built .glb looks right in any glTF
// viewer, not just in this app.
const MATERIALS = {
  teeth:    { baseColorFactor: [0.925, 0.906, 0.851, 1], roughnessFactor: 0.35, metallicFactor: 0 },
  mandible: { baseColorFactor: [0.898, 0.855, 0.761, 1], roughnessFactor: 0.70, metallicFactor: 0 },
  maxilla:  { baseColorFactor: [0.898, 0.855, 0.761, 1], roughnessFactor: 0.70, metallicFactor: 0 },
  gingiva:  { baseColorFactor: [0.804, 0.451, 0.435, 1], roughnessFactor: 0.75, metallicFactor: 0 },
  muscles:  { baseColorFactor: [0.647, 0.271, 0.259, 1], roughnessFactor: 0.65, metallicFactor: 0 },
  pulp:     { baseColorFactor: [0.804, 0.286, 0.271, 1], roughnessFactor: 0.55, metallicFactor: 0 },
  pdl:      { baseColorFactor: [0.612, 0.784, 0.878, 1], roughnessFactor: 0.80, metallicFactor: 0 },
};

/** Parse a binary STL into a flat, non-indexed Float32Array of positions. */
function parseBinarySTL(buf) {
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const triangles = view.getUint32(80, true);
  const expected = 84 + triangles * 50;
  if (buf.byteLength < expected) {
    throw new Error(`truncated STL: header claims ${triangles} triangles (${expected} bytes), file is ${buf.byteLength}`);
  }
  const positions = new Float32Array(triangles * 9);
  let o = 84;
  for (let t = 0; t < triangles; t++) {
    o += 12; // skip the per-facet normal; we recompute normals anyway
    for (let v = 0; v < 9; v++) {
      positions[t * 9 + v] = view.getFloat32(o, true);
      o += 4;
    }
    o += 2; // attribute byte count
  }
  return positions;
}

/**
 * Merge bitwise-identical vertices into an indexed mesh.
 * Keyed on the raw float bits so no coordinate is ever rounded — welding must
 * not soften cusp tips or occlusal fissures.
 */
function weldExact(positions) {
  const bits = new Uint32Array(positions.buffer, positions.byteOffset, positions.length);
  const seen = new Map();
  const out = [];
  const wide = new Uint32Array(positions.length / 3);

  for (let i = 0, n = positions.length / 3; i < n; i++) {
    const key = `${bits[i * 3]},${bits[i * 3 + 1]},${bits[i * 3 + 2]}`;
    let idx = seen.get(key);
    if (idx === undefined) {
      idx = out.length / 3;
      seen.set(key, idx);
      out.push(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
    }
    wide[i] = idx;
  }

  // Indices are the single largest thing in the buffer — bigger than positions
  // and normals combined at 32 bits. Every structure here welds to well under
  // 65536 vertices, so 16-bit indices halve that for free.
  const vertexCount = out.length / 3;
  const indices = vertexCount <= 0xffff ? Uint16Array.from(wide) : wide;

  return { positions: new Float32Array(out), indices };
}

/**
 * Area-weighted smooth vertex normals. The cross product of two edge vectors has
 * magnitude proportional to triangle area, so accumulating un-normalized face
 * normals weights each face by its area for free — which is what keeps large
 * flat regions from being dragged around by clusters of tiny triangles.
 */
function computeSmoothNormals(positions, indices) {
  const normals = new Float32Array(positions.length);
  for (let i = 0; i < indices.length; i += 3) {
    const a = indices[i] * 3, b = indices[i + 1] * 3, c = indices[i + 2] * 3;
    const ax = positions[a], ay = positions[a + 1], az = positions[a + 2];
    const e1x = positions[b] - ax, e1y = positions[b + 1] - ay, e1z = positions[b + 2] - az;
    const e2x = positions[c] - ax, e2y = positions[c + 1] - ay, e2z = positions[c + 2] - az;
    const nx = e1y * e2z - e1z * e2y;
    const ny = e1z * e2x - e1x * e2z;
    const nz = e1x * e2y - e1y * e2x;
    for (const v of [a, b, c]) {
      normals[v] += nx; normals[v + 1] += ny; normals[v + 2] += nz;
    }
  }
  for (let i = 0; i < normals.length; i += 3) {
    const len = Math.hypot(normals[i], normals[i + 1], normals[i + 2]);
    if (len > 0) {
      normals[i] /= len; normals[i + 1] /= len; normals[i + 2] /= len;
    } else {
      normals[i + 1] = 1; // degenerate vertex; point it somewhere valid
    }
  }
  return normals;
}

/**
 * BodyParts3D is z-up with z measured from the floor (the head sits near
 * z=1470mm) and anterior toward -y. Rotate -90 degrees about X, (x,y,z) ->
 * (x, z, -y), to reach glTF/three.js y-up. Anterior then points to +z, so a
 * camera on +z lands on a frontal view with no extra work, and x is untouched
 * so anatomical right stays negative-x.
 */
function toYUp(positions) {
  for (let i = 0; i < positions.length; i += 3) {
    const y = positions[i + 1];
    positions[i + 1] = positions[i + 2];
    positions[i + 2] = -y;
  }
}

function bounds(positions) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i += 3) {
    for (let a = 0; a < 3; a++) {
      const v = positions[i + a];
      if (v < min[a]) min[a] = v;
      if (v > max[a]) max[a] = v;
    }
  }
  return { min, max };
}

/**
 * Guard against a mirrored model — an atlas that confidently labels the wrong
 * side is worse than no atlas. Anatomical right is negative x in this dataset
 * (verified: right upper central incisor at x[-9.1,-0.8]). Any structure whose
 * FMA label says "right" but whose geometry sits on +x means the axes got
 * flipped somewhere, and the build must fail rather than ship it.
 */
/**
 * Laterality is checked against the DENTAL MIDLINE, not the framing centre.
 *
 * Those are different things and conflating them is a real bug, not a
 * technicality. The framing centre is the middle of the model's bounding box,
 * chosen so the camera sits well; the dental midline is anatomy. They coincide
 * only when the subject happened to be centred in the scanner.
 *
 * This surfaced when CBCT teeth were first built alongside BodyParts3D jaws.
 * The operator's arch sits 3.6 mm to their left of the scanner's origin — head
 * position, not anatomy — while the BodyParts3D dentition sits at -0.7 mm, so a
 * bounding box spanning both put the "centre" between two different people. The
 * lower right central incisor, 2.8 mm from its own true midline, fell on the
 * wrong side of it and the check failed. Nothing was mirrored.
 *
 * Measuring the midline from the teeth of the model itself makes the check
 * independent of framing and of how the subject was positioned, which is what it
 * was always meant to test.
 */
function dentalMidline(meshes) {
  const teeth = meshes.filter((m) => m.s.layer === 'teeth');
  if (!teeth.length) return 0;
  let lo = Infinity, hi = -Infinity;
  for (const m of teeth) {
    for (let i = 0; i < m.positions.length; i += 3) {
      if (m.positions[i] < lo) lo = m.positions[i];
      if (m.positions[i] > hi) hi = m.positions[i];
    }
  }
  return (lo + hi) / 2;
}

function checkLaterality(report, midline = 0) {
  const failures = [];
  for (const { fma, name, side, centroidX } of report) {
    const x = centroidX - midline;
    if (side === 'right' && x > 0) failures.push(`${fma} ${name}: side=right but centroid x=${x.toFixed(1)} relative to the dental midline`);
    if (side === 'left' && x < 0) failures.push(`${fma} ${name}: side=left but centroid x=${x.toFixed(1)} relative to the dental midline`);
  }
  return failures;
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const doc = new Document();
  doc.createBuffer();
  const scene = doc.createScene('oral-anatomy');

  const materials = {};
  for (const [layer, spec] of Object.entries(MATERIALS)) {
    materials[layer] = doc.createMaterial(layer)
      .setBaseColorFactor(spec.baseColorFactor)
      .setRoughnessFactor(spec.roughnessFactor)
      .setMetallicFactor(spec.metallicFactor)
      .setDoubleSided(true);
  }

  // Pass 1: load, weld, reorient. Defer centering until we know the extent of
  // the dental content.
  const meshes = [];
  for (const s of STRUCTURES) {
    const dir = s.source ? join(ROOT, ...SOURCE_DIRS[s.source]) : STL_DIR;
    const raw = await readFile(join(dir, `${s.fma}.stl`));
    const soup = parseBinarySTL(raw);
    const rawVerts = soup.length / 3;
    const { positions, indices } = weldExact(soup);
    toYUp(positions);
    meshes.push({ s, positions, indices, rawVerts, weldedVerts: positions.length / 3 });
  }

  // Center on the dentition and its supporting bone, not on the muscles — the
  // masseters reach the zygomatic arch and would pull the framing off the teeth.
  const dental = meshes.filter((m) => m.s.layer !== 'muscles');
  const all = new Float32Array(dental.reduce((n, m) => n + m.positions.length, 0));
  let at = 0;
  for (const m of dental) { all.set(m.positions, at); at += m.positions.length; }
  const b = bounds(all);
  const center = [0, 1, 2].map((a) => (b.min[a] + b.max[a]) / 2);
  const extent = [0, 1, 2].map((a) => b.max[a] - b.min[a]);

  // Pass 2: center, compute normals, emit glTF nodes.
  const report = [];
  const teethJson = {};
  let totalTris = 0;

  for (const { s, positions, indices, rawVerts, weldedVerts } of meshes) {
    for (let i = 0; i < positions.length; i += 3) {
      positions[i] -= center[0];
      positions[i + 1] -= center[1];
      positions[i + 2] -= center[2];
    }

    const normals = computeSmoothNormals(positions, indices);

    const prim = doc.createPrimitive()
      .setAttribute('POSITION', doc.createAccessor(`${s.fma}_P`).setType('VEC3').setArray(positions))
      .setAttribute('NORMAL', doc.createAccessor(`${s.fma}_N`).setType('VEC3').setArray(normals))
      .setIndices(doc.createAccessor(`${s.fma}_I`).setType('SCALAR').setArray(indices))
      .setMaterial(materials[s.layer]);

    // Node name is the FMA id: the join key the app uses to look up metadata.
    const node = doc.createNode(s.fma).setMesh(doc.createMesh(s.fma).addPrimitive(prim));
    scene.addChild(node);

    let cx = 0;
    for (let i = 0; i < positions.length; i += 3) cx += positions[i];
    cx /= positions.length / 3;

    const name = structureName(s);
    const notation = toothNotation(s);
    report.push({ fma: s.fma, name, side: s.side, centroidX: cx, rawVerts, weldedVerts });
    totalTris += indices.length / 3;

    teethJson[s.fma] = {
      fma: s.fma,
      name,
      layer: s.layer,
      side: s.side,
      ...(notation ? { ...notation, arch: s.arch, position: s.position, type: s.type } : {}),
    };
  }

  const midline = dentalMidline(meshes) - center[0];
  const failures = checkLaterality(report, midline);
  if (failures.length) {
    console.error('LATERALITY CHECK FAILED — the model may be mirrored:');
    for (const f of failures) console.error(`  ${f}`);
    process.exit(1);
  }

  await new NodeIO().write(join(OUT_DIR, 'dentition.glb'), doc);
  await writeFile(
    join(OUT_DIR, 'teeth.json'),
    JSON.stringify({ layers: LAYERS, structures: teethJson }, null, 2) + '\n',
  );

  const rawVerts = report.reduce((n, r) => n + r.rawVerts, 0);
  const weldedVerts = report.reduce((n, r) => n + r.weldedVerts, 0);
  const { size } = await import('node:fs').then((fs) => fs.promises.stat(join(OUT_DIR, 'dentition.glb')));

  console.log(`structures      ${report.length}`);
  console.log(`triangles       ${totalTris.toLocaleString()}`);
  console.log(`vertices        ${rawVerts.toLocaleString()} -> ${weldedVerts.toLocaleString()} welded (${(100 - (weldedVerts / rawVerts) * 100).toFixed(1)}% reduction)`);
  console.log(`extent (mm)     ${extent.map((v) => v.toFixed(1)).join(' x ')}  (dental content, centered)`);
  console.log(`laterality      OK — all ${report.filter((r) => r.side !== 'midline').length} sided structures on the expected side`);
  console.log(`teeth           ${Object.values(teethJson).filter((t) => t.layer === 'teeth').length} (third molars absent from source)`);
  console.log(`output          public/dentition.glb  ${(size / 1e6).toFixed(2)} MB`);
}

main().catch((err) => {
  console.error(`build failed: ${err.message}`);
  process.exit(1);
});
