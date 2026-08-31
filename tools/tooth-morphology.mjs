// Does each tooth mesh LOOK like the tooth its number claims it is?
//
// tools/manifest.mjs derives Universal / FDI / Palmer from arch, side and
// position, which guarantees the three notations agree with each other but says
// nothing about whether the underlying position is right. That was the standing
// open item: the mapping is self-consistent and was cross-checked against an
// independently written table, and consistency is not correctness. A premolar
// mesh filed under a molar's number would satisfy every check in the build.
//
// Per-tooth CBCT geometry is the independent test, because tooth morphology is
// unmistakable. Two checks run against it, and they fail differently on purpose:
//
//   1. ARCH ORDER. Order the teeth around each arch geometrically and the
//      sequence must match the Universal numbering. This catches a swap, a
//      transposition, or an arch numbered backwards.
//   2. TOOTH TYPE. Molars and canines are identified from shape alone and must
//      land on the positions that claim them. This catches a whole arch or
//      quadrant shifted by one, which check 1 cannot see because a uniform shift
//      keeps the order intact.
//
// Every test is ORDINAL — largest, longest, most roots — never a threshold in
// millimetres. This is one person's dentition, and a build that asserts their
// molar exceeds 800 mm³ would be asserting something about them rather than
// about the labelling.
//
// Frame: called after toYUp(), so +y is superior, +x is the patient's LEFT and
// +z is anterior. Maxillary crowns point down (-y), mandibular crowns up (+y).

/** Enclosed volume, by signed tetrahedron sum about the origin. */
function volume(positions, indices) {
  let v = 0;
  for (let i = 0; i < indices.length; i += 3) {
    const a = indices[i] * 3, b = indices[i+1] * 3, c = indices[i+2] * 3;
    const ax = positions[a], ay = positions[a+1], az = positions[a+2];
    const bx = positions[b], by = positions[b+1], bz = positions[b+2];
    const cx = positions[c], cy = positions[c+1], cz = positions[c+2];
    v += (ax * (by*cz - bz*cy) - ay * (bx*cz - bz*cx) + az * (bx*cy - by*cx)) / 6;
  }
  return Math.abs(v);
}

/** Area-weighted surface centroid. */
function centroid(positions, indices) {
  let cx = 0, cz = 0, A = 0;
  for (let i = 0; i < indices.length; i += 3) {
    const a = indices[i] * 3, b = indices[i+1] * 3, c = indices[i+2] * 3;
    const ux = positions[b] - positions[a], uy = positions[b+1] - positions[a+1], uz = positions[b+2] - positions[a+2];
    const vx = positions[c] - positions[a], vy = positions[c+1] - positions[a+1], vz = positions[c+2] - positions[a+2];
    const area = Math.hypot(uy*vz - uz*vy, uz*vx - ux*vz, ux*vy - uy*vx) / 2;
    cx += area * (positions[a] + positions[b] + positions[c]) / 3;
    cz += area * (positions[a+2] + positions[b+2] + positions[c+2]) / 3;
    A += area;
  }
  return { x: cx / A, z: cz / A };
}

/**
 * How many separate closed loops the surface makes in the horizontal plane at
 * height y — which, taken below the furcation, is the tooth's root count.
 *
 * Each triangle crossing the plane contributes one segment; joining segments
 * that share an endpoint and counting connected components counts the loops.
 * Endpoints are quantised to a micron so that the two triangles either side of
 * a shared edge agree on where the crossing is.
 */
function loopsAtHeight(positions, indices, y) {
  const key = (x, z) => `${Math.round(x * 1000)},${Math.round(z * 1000)}`;
  const adj = new Map();
  const link = (a, b) => { if (!adj.has(a)) adj.set(a, []); adj.get(a).push(b); };

  for (let i = 0; i < indices.length; i += 3) {
    const idx = [indices[i] * 3, indices[i+1] * 3, indices[i+2] * 3];
    const hits = [];
    for (let e = 0; e < 3; e++) {
      const p = idx[e], q = idx[(e + 1) % 3];
      const py = positions[p+1], qy = positions[q+1];
      if ((py - y) * (qy - y) >= 0) continue;
      const f = (y - py) / (qy - py);
      hits.push([positions[p] + f * (positions[q] - positions[p]),
                 positions[p+2] + f * (positions[q+2] - positions[p+2])]);
    }
    if (hits.length !== 2) continue;
    const a = key(...hits[0]), b = key(...hits[1]);
    link(a, b); link(b, a);
  }

  const seen = new Set();
  let loops = 0;
  for (const n of adj.keys()) {
    if (seen.has(n)) continue;
    loops++;
    const stack = [n];
    seen.add(n);
    while (stack.length) {
      for (const m of adj.get(stack.pop()) || []) if (!seen.has(m)) { seen.add(m); stack.push(m); }
    }
  }
  return loops;
}

// Fraction of the way from the cusp tip to the apex at which root count is read.
// Roots have separated well before this in a multi-rooted tooth, and it is still
// clear of the apical third where a single root may fork. Read at 0.55 the
// furcation has not opened in every molar and canines can read 2 through the
// cervical constriction; at 0.70 all 28 teeth report cleanly.
const ROOT_DEPTH = 0.70;

export function measureTooth({ s, positions, indices }) {
  let lo = Infinity, hi = -Infinity;
  for (let i = 1; i < positions.length; i += 3) {
    if (positions[i] < lo) lo = positions[i];
    if (positions[i] > hi) hi = positions[i];
  }
  // Mandibular crowns point up, maxillary crowns point down.
  const tip = s.arch === 'mandibular' ? hi : lo;
  const apex = s.arch === 'mandibular' ? lo : hi;
  return {
    s,
    length: hi - lo,
    volume: volume(positions, indices),
    roots: loopsAtHeight(positions, indices, tip + (apex - tip) * ROOT_DEPTH),
    ...centroid(positions, indices),
  };
}

/** Order teeth around one arch geometrically, from one free end to the other. */
function archOrder(arch) {
  const mx = arch.reduce((a, t) => a + t.x, 0) / arch.length;
  const mz = arch.reduce((a, t) => a + t.z, 0) / arch.length;
  const withAngle = arch.map((t) => ({ t, a: Math.atan2(t.z - mz, t.x - mx) }));
  withAngle.sort((p, q) => p.a - q.a);

  // A dental arch is a horseshoe, not a ring: the widest angular gap is its open
  // posterior side. Rotate the sequence so that gap falls at the ends, and what
  // is left runs continuously from one second molar round to the other.
  let gap = 0;
  for (let i = 0; i < withAngle.length; i++) {
    const d = withAngle[(i + 1) % withAngle.length].a - withAngle[i].a +
              (i + 1 === withAngle.length ? 2 * Math.PI : 0);
    if (d > gap) { gap = d; var cut = i + 1; }
  }
  return [...withAngle.slice(cut), ...withAngle.slice(0, cut)].map((w) => w.t);
}

/**
 * Both checks. Returns a list of human-readable failures; empty means the
 * geometry agrees with the numbering.
 */
export function checkToothIdentity(measurements) {
  const failures = [];
  const teeth = measurements.filter((m) => m.s.layer === 'teeth');

  for (const arch of ['maxillary', 'mandibular']) {
    const set = teeth.filter((m) => m.s.arch === arch);
    if (set.length < 4) continue;

    // --- Check 1: geometric order around the arch matches Universal order ---
    const ordered = archOrder(set);
    const nums = ordered.map((t) => t.universal);
    const ascending = nums[nums.length - 1] > nums[0];
    for (let i = 1; i < nums.length; i++) {
      const step = nums[i] - nums[i - 1];
      if (ascending ? step <= 0 : step >= 0) {
        failures.push(
          `${arch} arch order: ${ordered[i-1].s.fma} (Universal ${nums[i-1]}) and ` +
          `${ordered[i].s.fma} (Universal ${nums[i]}) are adjacent in the arch but ` +
          `their numbers do not run in sequence — the mapping has them transposed`);
      }
    }

    // --- Check 2: shape identifies molars and canines, per quadrant ---
    for (const side of ['right', 'left']) {
      const q = set.filter((m) => m.s.side === side);
      if (q.length < 5) continue;

      // Molars are the two largest teeth in a quadrant, and the only ones whose
      // roots have divided by ROOT_DEPTH. Both must agree, and both must land on
      // positions 6 and 7.
      const byVolume = [...q].sort((a, b) => b.volume - a.volume);
      const biggest = new Set(byVolume.slice(0, 2).map((t) => t.s.fma));
      const branched = new Set(q.filter((t) => t.roots >= 2).map((t) => t.s.fma));
      const claimed = new Set(q.filter((t) => t.s.position >= 6).map((t) => t.s.fma));

      for (const t of q) {
        const isMolar = claimed.has(t.s.fma);
        if (biggest.has(t.s.fma) !== isMolar) {
          failures.push(
            `${arch} ${side} quadrant: ${t.s.fma} is labelled ${t.s.type} ` +
            `(Universal ${t.universal}) but its volume ${t.volume.toFixed(0)} mm³ ` +
            `${isMolar ? 'is not among the two largest' : 'is among the two largest'} ` +
            `in the quadrant — molars should be`);
        }
        if (branched.has(t.s.fma) !== isMolar) {
          failures.push(
            `${arch} ${side} quadrant: ${t.s.fma} is labelled ${t.s.type} ` +
            `(Universal ${t.universal}) but has ${t.roots} root${t.roots === 1 ? '' : 's'} ` +
            `at ${ROOT_DEPTH * 100}% depth — only molars should divide`);
        }
      }

      // The canine is the longest tooth in the quadrant that is not a molar, in
      // both arches and on both sides. It anchors position 3, which in turn
      // separates the incisors in front of it from the premolars behind.
      const nonMolar = q.filter((t) => !claimed.has(t.s.fma));
      const longest = nonMolar.reduce((a, b) => (b.length > a.length ? b : a));
      const canine = nonMolar.find((t) => t.s.position === 3);
      if (canine && longest.s.fma !== canine.s.fma) {
        failures.push(
          `${arch} ${side} quadrant: the longest non-molar is ${longest.s.fma} ` +
          `(${longest.length.toFixed(1)} mm, labelled ${longest.s.type}), but the canine ` +
          `is ${canine.s.fma} (${canine.length.toFixed(1)} mm) — the canine should be longest`);
      }
    }
  }
  return failures;
}
