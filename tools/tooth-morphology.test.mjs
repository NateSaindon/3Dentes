#!/usr/bin/env node
// An invariant that cannot fail is decoration. This corrupts the numbering in
// the ways it could realistically be wrong and asserts the check catches each.
//
//   node tools/tooth-morphology.test.mjs
//
// The mutations are deliberately of two kinds, because the two checks in
// tooth-morphology.mjs cover different failure modes and neither covers both:
// a TRANSPOSITION breaks the geometric order around the arch, while a uniform
// SHIFT preserves order perfectly and is only visible in the shapes.

import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { STRUCTURES, STL_DIR as STL_SUBDIR, toothNotation } from './manifest.mjs';
import { measureTooth, checkToothIdentity } from './tooth-morphology.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const STL_DIR = join(ROOT, ...STL_SUBDIR);

function parseBinarySTL(buf) {
  const n = buf.readUInt32LE(80);
  const tris = new Float32Array(n * 9);
  for (let i = 0; i < n; i++) {
    const o = 84 + i * 50 + 12;
    for (let j = 0; j < 9; j++) tris[i * 9 + j] = buf.readFloatLE(o + j * 4);
  }
  return tris;
}
function toYUp(p) {
  for (let i = 0; i < p.length; i += 3) { const y = p[i+1]; p[i+1] = p[i+2]; p[i+2] = -y; }
}

// Measure once; the mutations relabel the same geometry.
const base = [];
for (const s of STRUCTURES.filter((s) => s.layer === 'teeth')) {
  const tris = parseBinarySTL(await readFile(join(STL_DIR, `${s.fma}.stl`)));
  toYUp(tris);
  const indices = new Uint32Array(tris.length / 3);
  for (let i = 0; i < indices.length; i++) indices[i] = i;
  base.push(measureTooth({ s, positions: tris, indices }));
}
const withNotation = (m) => ({ ...m, universal: +toothNotation(m.s).universal });

/** Relabel: give the tooth at `from` the identity currently at `to`, and vice versa. */
function swap(fromU, toU) {
  const byU = new Map(base.map((m) => [+toothNotation(m.s).universal, m]));
  const a = byU.get(fromU), b = byU.get(toU);
  return base.map((m) => {
    if (m === a) return withNotation({ ...m, s: { ...b.s, fma: m.s.fma } });
    if (m === b) return withNotation({ ...m, s: { ...a.s, fma: m.s.fma } });
    return withNotation(m);
  });
}

/** Shift every tooth in one quadrant one position distally, wrapping round. */
function shiftQuadrant(arch, side) {
  const q = base.filter((m) => m.s.arch === arch && m.s.side === side)
                .sort((x, y) => x.s.position - y.s.position);
  const rotated = new Map();
  q.forEach((m, i) => rotated.set(m.s.fma, q[(i + 1) % q.length].s));
  return base.map((m) => rotated.has(m.s.fma)
    ? withNotation({ ...m, s: { ...rotated.get(m.s.fma), fma: m.s.fma } })
    : withNotation(m));
}

const cases = [
  ['the real mapping',                       base.map(withNotation),           false],
  ['central and lateral incisor swapped',    swap(8, 7),                       true],
  ['first premolar and first molar swapped', swap(5, 3),                       true],
  ['canine and first premolar swapped',      swap(6, 5),                       true],
  ['second molar and canine swapped',        swap(31, 27),                     true],
  ['upper right quadrant shifted one place', shiftQuadrant('maxillary','right'), true],
  ['lower left quadrant shifted one place',  shiftQuadrant('mandibular','left'), true],
];

let bad = 0;
for (const [label, set, shouldFail] of cases) {
  const failures = checkToothIdentity(set);
  const failed = failures.length > 0;
  const ok = failed === shouldFail;
  if (!ok) bad++;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label.padEnd(42)} ` +
              `${failed ? `${failures.length} finding${failures.length === 1 ? '' : 's'}` : 'clean'}` +
              `${ok ? '' : `  <-- expected ${shouldFail ? 'to be caught' : 'to be clean'}`}`);
  if (failed && shouldFail) console.log(`          e.g. ${failures[0]}`);
}
console.log(bad === 0
  ? '\n  All cases behaved as expected — the check bites.'
  : `\n  ${bad} case(s) misbehaved.`);
process.exit(bad === 0 ? 0 : 1);
