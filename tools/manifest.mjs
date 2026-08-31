// The structures 3Dentes ships, and how they group into UI layers.
//
// Every mesh is segmented from the operator's own cone-beam CT and lives in
// assets/cbct/stl. There is no second source: the BodyParts3D alpha was removed
// once the CBCT build replaced the last of its geometry, so nothing here carries
// a ShareAlike obligation and there is no build variant to keep in sync.
//
// FMA ids are Foundational Model of Anatomy identifiers -- an anatomy ontology,
// independent of any mesh source. They name the source STL, the node baked into
// the .glb and the teeth.json key, so they are the join key across the whole
// pipeline.
//
// `side` is ANATOMICAL side (the patient's), not the viewer's. The build script
// asserts it against mesh position — see checkLaterality in build-assets.mjs.
//
// For teeth, `position` is the count from the midline: 1 = central incisor,
// 2 = lateral incisor, 3 = canine, 4/5 = premolars, 6/7 = molars, 8 = third
// molar. Universal / FDI / Palmer notation is DERIVED from arch + side +
// position by toothNotation() below, never typed by hand — 28 hand-entered
// tooth numbers is 28 chances to mislabel a tooth.

// The one place meshes come from. Previously this selected between two trees
// whose licences differed; there is only the measured one now.
export const STL_DIR = ['assets', 'cbct', 'stl'];

const tooth = (fma, arch, side, position, type) => ({
  fma, arch, side, position, type, layer: 'teeth',
});

const MEASURED_STRUCTURES = [
  // --- Permanent teeth: 28. Third molars (position 8) are extracted in this
  // patient, so the scan contains 28 teeth and so does the atlas. ---
  // Maxillary right
  tooth('FMA55681', 'maxillary', 'right', 1, 'central incisor'),
  tooth('FMA55680', 'maxillary', 'right', 2, 'lateral incisor'),
  tooth('FMA55798', 'maxillary', 'right', 3, 'canine'),
  tooth('FMA55689', 'maxillary', 'right', 4, 'first premolar'),
  tooth('FMA55688', 'maxillary', 'right', 5, 'second premolar'),
  tooth('FMA55698', 'maxillary', 'right', 6, 'first molar'),
  tooth('FMA55697', 'maxillary', 'right', 7, 'second molar'),
  // Maxillary left
  tooth('FMA55682', 'maxillary', 'left', 1, 'central incisor'),
  tooth('FMA55683', 'maxillary', 'left', 2, 'lateral incisor'),
  tooth('FMA55799', 'maxillary', 'left', 3, 'canine'),
  tooth('FMA55690', 'maxillary', 'left', 4, 'first premolar'),
  tooth('FMA55691', 'maxillary', 'left', 5, 'second premolar'),
  tooth('FMA55699', 'maxillary', 'left', 6, 'first molar'),
  tooth('FMA55700', 'maxillary', 'left', 7, 'second molar'),
  // Mandibular left
  tooth('FMA57143', 'mandibular', 'left', 1, 'central incisor'),
  tooth('FMA57141', 'mandibular', 'left', 2, 'lateral incisor'),
  tooth('FMA55687', 'mandibular', 'left', 3, 'canine'),
  tooth('FMA55693', 'mandibular', 'left', 4, 'first premolar'),
  tooth('FMA55692', 'mandibular', 'left', 5, 'second premolar'),
  tooth('FMA55704', 'mandibular', 'left', 6, 'first molar'),
  tooth('FMA55703', 'mandibular', 'left', 7, 'second molar'),
  // Mandibular right
  tooth('FMA57142', 'mandibular', 'right', 1, 'central incisor'),
  tooth('FMA57140', 'mandibular', 'right', 2, 'lateral incisor'),
  tooth('FMA55686', 'mandibular', 'right', 3, 'canine'),
  tooth('FMA55694', 'mandibular', 'right', 4, 'first premolar'),
  tooth('FMA55695', 'mandibular', 'right', 5, 'second premolar'),
  tooth('FMA55705', 'mandibular', 'right', 6, 'first molar'),
  tooth('FMA55706', 'mandibular', 'right', 7, 'second molar'),

  // --- Bone ---
  { fma: 'FMA52748', name: 'Mandible',            layer: 'mandible', side: 'midline' },
  // DentalSegmentator's "Upper Skull" is cropped here to the alveolar process
  // and palate, and comes out as ONE mesh rather than four named bones. The left
  // maxilla and both palatine bones therefore have no measured geometry and are
  // not listed. See the note on the name in CLAUDE.md's open items.
  { fma: 'FMA53649', name: 'Right maxilla',       layer: 'maxilla',  side: 'right'   },

  // --- Soft tissue ---
  // --- Nerves: CBCT build only. See tools/cbct/nerve.py and nerve_maxilla.py.
  // The mandibular canal is MEASURED; its contents are not. Everything
  // maxillary is SCHEMATIC -- the superior alveolar canals are not reliably
  // visible at 0.16 mm and nothing here was seen in the scan but the foramina.
  { fma: 'FMA59763', name: 'Gingiva of upper jaw', layer: 'gingiva', side: 'midline' },
  { fma: 'FMA59764', name: 'Gingiva of lower jaw', layer: 'gingiva', side: 'midline' },

  // Muscles of mastication were the last thing BodyParts3D supplied, and they
  // left with it. CBCT has no soft-tissue contrast, so there is nothing to
  // segment them from; Phase 3 step 5 fits authored bellies to this patient's
  // measured attachments instead. See docs/phase-3-soft-tissue.md.
];

const ALL_LAYERS = {
  teeth:    { label: 'Teeth',                  defaultOpacity: 1.0,  visible: true  },
  mandible: { label: 'Mandible',               defaultOpacity: 1.0,  visible: true  },
  maxilla:  { label: 'Maxilla & palatine',     defaultOpacity: 1.0,  visible: true  },
  // Gingiva at full opacity hides every root and the app looks broken on load.
  gingiva:  { label: 'Gingiva',                defaultOpacity: 0.45, visible: true  },
  // Pulp and PDL are off by default: they sit INSIDE the teeth, so showing them
  // on load reveals nothing and costs draw calls. The teeth layer's opacity is
  // what makes them visible.
  pulp:     { label: 'Pulp',                   defaultOpacity: 1.0,  visible: false },
  pdl:      { label: 'Periodontal ligament',   defaultOpacity: 0.85, visible: false },
  // Nerves are OFF by default. Two sets of geometry with very
  // different standing share this layer -- the mandibular trunk follows a canal
  // the scan actually resolves, while every maxillary course is textbook -- so
  // the structure names carry the distinction and the caveat states it. Do not
  // let a later tidy-up imply the maxillary nerves were measured.
  nerves:   { label: 'Nerves',                 defaultOpacity: 1.0,  visible: false },
};


// Quadrant numbers follow the ISO/FDI convention:
//   1 = upper right, 2 = upper left, 3 = lower left, 4 = lower right.
const QUADRANT = { 'maxillary:right': 1, 'maxillary:left': 2, 'mandibular:left': 3, 'mandibular:right': 4 };

// Universal runs 1-32 starting at the upper right third molar, across the upper
// arch to upper left, then down to lower left and back across to lower right.
const UNIVERSAL = {
  1: (p) => 9 - p,   // upper right: central incisor (p1) = 8
  2: (p) => 8 + p,   // upper left:  central incisor (p1) = 9
  3: (p) => 25 - p,  // lower left:  central incisor (p1) = 24
  4: (p) => 24 + p,  // lower right: central incisor (p1) = 25
};

const PALMER_PREFIX = { 1: 'UR', 2: 'UL', 3: 'LL', 4: 'LR' };

// The atlas contains only what the scan resolved, and it is SMALLER than the
// BodyParts3D alpha it replaced rather than a mix of the two. That was always
// deliberate, and it is now structural: BodyParts3D is a whole-body frame with
// the head about 1470 mm off the floor while CBCT is scanner-centred, so naively
// combining them produced a model 1582 mm tall -- and they are different people
// besides, so one individual's teeth do not sit in another's jaws. Any borrowed
// geometry added later has to be registered INTO the patient's frame first.

const NERVE_STRUCTURES = [
  { fma: 'FMA53381', name: 'Inferior alveolar nerve (canal measured)',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53381B', name: 'Inferior alveolar dental branches',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53381T', name: 'Mental and incisive branches (schematic)',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53088', name: 'Superior dental plexus (schematic)',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53088B', name: 'Superior alveolar dental branches (schematic)',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53088T', name: 'Infraorbital, PSA, MSA and ASA nerves (schematic)',
    layer: 'nerves', side: 'midline' },
];

// Pulp and PDL are per-tooth and derived, so they inherit each tooth's arch,
// side and position -- which is what lets the app associate them with their
// tooth and keeps the notation derived rather than retyped. Their ids suffix the
// tooth's FMA id, so FMA55682-pulp belongs unambiguously to FMA55682.
const perTooth = (layer) =>
  MEASURED_STRUCTURES
    .filter((s) => s.layer === 'teeth')
    .map((s) => ({ ...s, fma: `${s.fma}-${layer}`, layer, tooth: s.fma }));

export const STRUCTURES = [
  ...MEASURED_STRUCTURES,
  ...NERVE_STRUCTURES,
  ...perTooth('pulp'),
  ...perTooth('pdl'),
];

// Only expose layers that actually have geometry. A toggle that controls nothing
// reads as a broken feature.
export const LAYERS = Object.fromEntries(
  Object.entries(ALL_LAYERS).filter(([k]) => STRUCTURES.some((s) => s.layer === k)),
);


export function toothNotation(s) {
  if (s.layer !== 'teeth') return null;
  const quadrant = QUADRANT[`${s.arch}:${s.side}`];
  return {
    quadrant,
    universal: String(UNIVERSAL[quadrant](s.position)),
    fdi: String(quadrant * 10 + s.position),
    // True Palmer notation uses a quadrant bracket that has no faithful plain-text
    // form; the UR/UL/LL/LR prefix is the standard unambiguous substitute.
    palmer: `${PALMER_PREFIX[quadrant]}${s.position}`,
  };
}

/** Human-readable name, derived for teeth and explicit for everything else. */
const PER_TOOTH_LABEL = { pulp: 'Pulp of', pdl: 'Periodontal ligament of' };

export function structureName(s) {
  if (s.arch && PER_TOOTH_LABEL[s.layer]) {
    const arch = s.arch === 'maxillary' ? 'upper' : 'lower';
    const side = s.side === 'right' ? 'right' : 'left';
    return `${PER_TOOTH_LABEL[s.layer]} the ${side} ${arch} ${s.type}`;
  }
  if (s.layer !== 'teeth') return s.name;
  const arch = s.arch === 'maxillary' ? 'upper' : 'lower';
  return `${s.side === 'right' ? 'Right' : 'Left'} ${arch} ${s.type}`;
}
