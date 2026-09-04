#!/usr/bin/env node
// Every ontology id must name the structure the manifest says it does.
//
//   node tools/ontology.test.mjs
//
// The README calls FMA ids "the join key throughout", and nothing checked them.
// Two were pointing somewhere else entirely: FMA53381, carried by the inferior
// alveolar nerve and its two derived meshes, is the OCCIPITAL PART OF THE
// APONEUROSIS OF EPICRANIUS, and FMA53088, carried by the superior dental
// plexus and its two, is the LATERAL WALL OF THE RIGHT ORBIT. Both shipped from
// 0.1.0. They are now FMA53243 and FMA77528.
//
// This is invariant 5's failure mode one level up. That check catches a tooth
// at the wrong POSITION; the notation cannot reveal it because all three
// notations derive from one triple and agree with each other whatever it says.
// An FMA id is the same shape of problem: it is self-consistent with nothing,
// so a wrong one is invisible forever unless something resolves it against the
// ontology.
//
// TWO NAMESPACES, and the second is not a fallback for convenience. The FMA has
// no inferior alveolar vein, no infraorbital vein and no dental vein -- checked
// four ways against an index carrying 3,741 vein terms -- so those three carry
// IFAA Terminologia Anatomica Humana unit ids instead. TAH cross-references FMA
// wherever both exist, so the namespaces agree rather than compete. A TAH id is
// written TAHU15802 in the manifest (it becomes a filename) and TAH:U15802 in
// the label table, which is how the IFAA writes it.
//
// Labels are vendored in tools/ontology-labels.json so this runs offline. Where the
// manifest's display name legitimately differs from the ontology's, the
// difference is recorded in ALIASES with its reason -- ONE PLACE, reviewed, and
// not a tolerance that quietly widens.

import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { STRUCTURES } from './manifest.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const { labels } = JSON.parse(
  await readFile(join(ROOT, 'tools', 'ontology-labels.json'), 'utf8'));

// Manifest name vs ontology label, where the two differ for a stated reason.
// Where a manifest display name legitimately shares no word with the ontology
// label, record it here WITH ITS REASON. It is deliberately EMPTY: every case
// that looked like it needed an exemption -- "Gingiva of upper jaw" against
// "Maxillary gingiva", "Maxilla and palate" against "Right maxilla", the
// mid-face and ramus meshes -- passes on its own once the check is group-aware,
// so none was added. An exemption list is a place for a wrong id to hide, and
// an empty one is the strongest state for it to be in. Do not pre-populate it.
const ALIASES = {
  // The greater palatine vein. Neither the FMA nor the IFAA names one — checked
  // against an FMA index carrying 3,741 vein terms and against the IFAA's own
  // tributary lists — so it carries the id of what it DRAINS INTO, the
  // pterygoid plexus, with the repo's derived-mesh suffix. The parent is not
  // itself drawn, so unlike every other suffixed mesh there is no bare sibling
  // to agree with the label, and the group cannot clear itself. Recorded here
  // rather than fixed, because the id is the most precise one that exists.
  'TAH:U4540': 'suffix-only group: TAHU4540P is the greater palatine vein, a '
             + 'tributary of the pterygoid plexus, which is not drawn',
};

const norm = (s) => s.toLowerCase()
  .replace(/infra-orbital/g, 'infraorbital')
  .replace(/[^a-z0-9]+/g, ' ').trim();
const tokens = (s) => new Set(norm(s).split(' ').filter((w) => w.length > 2));
// Teeth carry no `name`; their identity is arch + side + position + type, which
// is what the ontology label spells out too ("Right second upper molar tooth").
const display = (s) => s.name
  ?? [s.side, s.arch === 'maxillary' ? 'upper' : 'lower', s.type, 'tooth']
     .filter(Boolean).join(' ');

// Manifest id -> the form the ontology writes it in. The repo's own B / T / M /
// -pulp suffixes are stripped; everything else must match exactly.
function canonical(fma) {
  let m = /^FMA(\d+)/.exec(fma);
  if (m) return `FMA${m[1]}`;
  m = /^TAHU(\d+)/.exec(fma);
  if (m) return `TAH:U${m[1]}`;
  return null;
}

const fail = [];
const groups = new Map();           // canonical id -> structures carrying it
for (const s of STRUCTURES) {
  const id = canonical(s.fma);
  if (!id) {
    fail.push(`${s.fma} (${display(s)}) is not an FMA or TAH id`);
    continue;
  }
  if (!groups.has(id)) groups.set(id, []);
  groups.get(id).push(s);
}

// AN FMA ID CLAIMS ONE STRUCTURE; the repo's own B / T / M / -pulp suffixes
// carve that structure into meshes, so a suffixed mesh's display name is free
// ("Mental and incisive branches" is a part of the inferior alveolar nerve, not
// another name for it). What must hold is that the ID names the right thing, so
// the GROUP is checked: at least one mesh carrying the id has to agree with the
// ontology label. That is what would have caught FMA53381, whose whole group
// was nerve anatomy under an id meaning a scalp aponeurosis.
for (const [id, members] of groups) {
  const label = labels[id];
  if (!label) {
    fail.push(`${id} (${display(members[0])}) is not in `
            + 'tools/ontology-labels.json — resolve it against the ontology '
            + 'and add it, do not guess');
    continue;
  }
  const b = tokens(label);
  const agrees = (s) => [...tokens(display(s))].some((w) => b.has(w));
  // A mesh carrying the BARE id claims to BE that structure, so it must agree
  // on its own. Only the suffixed derived meshes get a free name -- and one of
  // them agreeing is NOT enough to clear the group, or a wrong id hides behind
  // a right sibling. That is exactly what an earlier version of this check did:
  // FMA52978 pinned onto "Mandible" passed, because the real infraorbital nerve
  // shared the id and vouched for it.
  const bare = members.filter((s) => canonical(s.fma) === id
                              && !/[A-Z]$|-pulp$/.test(s.fma.replace(/^TAHU/, '')));
  const offenders = bare.filter((s) => !agrees(s));
  if (!ALIASES[id] && (offenders.length || (!bare.length && !members.some(agrees)))) {
    const who = (offenders.length ? offenders : members)
      .map((s) => `"${display(s)}"`).join(', ');
    fail.push(`${id} is "${label}" in the ontology, but ${who} shares no word `
            + 'with it. Either the id is wrong or the difference belongs in '
            + 'ALIASES with its reason.');
  }
}

const seen = new Set(groups.keys());
const unused = Object.keys(labels).filter((id) => !seen.has(id));
if (unused.length) {
  console.log(`note: ${unused.length} vendored label(s) no longer used: `
            + unused.join(', '));
}

if (fail.length) {
  console.error('ONTOLOGY CHECK FAILED:');
  for (const f of [...new Set(fail)]) console.error(`  - ${f}`);
  process.exit(1);
}
const nTah = [...seen].filter((i) => i.startsWith('TAH')).length;
console.log(`ontology ids: ${seen.size} distinct (${seen.size - nTah} FMA, `
          + `${nTah} TAH) across ${STRUCTURES.length} structures, all naming `
          + 'what the manifest says they do');
