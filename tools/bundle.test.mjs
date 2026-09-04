#!/usr/bin/env node
// A NEUROVASCULAR BUNDLE IS BUILT WHOLE OR NOT AT ALL.
//
//   node tools/bundle.test.mjs
//
// The operator's rule, 2026-09-04: where an artery, a vein and a nerve run
// together, all three go in at the same time. It is an anatomical claim as much
// as a tidiness one — a canal or a groove carries a bundle, and drawing one
// member of it tells the reader that is what is there.
//
// It is a CHECK rather than a note because the failure is silent. The greater
// palatine artery shipped alone and nothing said so; the mental artery had no
// vein for a whole release. Neither is visible in a render — an absent vessel
// looks exactly like a vessel you have not switched on.
//
// Every structure that belongs to a bundle names it. A bundle must carry at
// least one artery, one vein and one nerve; the counts need not match, because
// the meshes are cut by territory and by tier, not one-to-one (one nerve mesh
// covers PSA, MSA and ASA while the arteries are split by exact id).
//
// EXEMPTIONS carry a reason and an anatomical one, not a scheduling one. "Not
// built yet" is what this check exists to catch.

import { STRUCTURES } from './manifest.mjs';

const EXEMPT = {
  // (none — every bundle in the atlas is complete)
};

const roleOf = (s) => (s.layer === 'nerves' ? 'nerve' : s.material ?? null);

const bundles = new Map();
for (const s of STRUCTURES) {
  if (!s.bundle) continue;
  if (!bundles.has(s.bundle)) bundles.set(s.bundle, new Map());
  const role = roleOf(s);
  if (!role) continue;
  const m = bundles.get(s.bundle);
  if (!m.has(role)) m.set(role, []);
  m.get(role).push(s.fma);
}

// Anything vascular or neural that names no bundle at all is also a gap: it
// means nobody asked whether it has counterparts.
const untagged = STRUCTURES.filter(
  (s) => (s.layer === 'vessels' || s.layer === 'nerves') && !s.bundle);

const fail = [];
for (const [name, roles] of [...bundles].sort()) {
  const missing = ['artery', 'vein', 'nerve'].filter((r) => !roles.has(r));
  if (missing.length && !EXEMPT[name]) {
    fail.push(`bundle "${name}" has no ${missing.join(' and no ')} — `
            + `it carries ${[...roles.keys()].sort().join(', ')}. Build the `
            + 'missing member, or add an ANATOMICAL reason to EXEMPT.');
  }
}
for (const s of untagged) {
  fail.push(`${s.fma} (${s.name}) is vascular or neural but names no bundle — `
          + 'say which bundle it belongs to, so its counterparts are checked.');
}

if (fail.length) {
  console.error('BUNDLE CHECK FAILED:');
  for (const f of fail) console.error(`  - ${f}`);
  process.exit(1);
}
const n = bundles.size;
console.log(`neurovascular bundles: ${n} complete — each carries an artery, a `
          + 'vein and a nerve');
