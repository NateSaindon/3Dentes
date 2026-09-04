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
  // not listed.
  //
  // It is MIDLINE, and was labelled "Right maxilla" until 2026-08-31: the mesh
  // spans x -41.1 to +40.9, i.e. both sides in full. It passed the laterality
  // assertion only because its area-weighted centroid happens to fall just right
  // of the dental midline -- a near miss, not a check that held. The FMA id is
  // kept because it is the join key everywhere and renaming it would break the
  // .glb, teeth.json and every reference at once; the id is now inexact and the
  // name and side are correct, which is the right way round.
  { fma: 'FMA53649', name: 'Maxilla and palate',  layer: 'maxilla',  side: 'midline' },

  // The rest of the upper skull label. FMA53649 keeps meaning the alveolar
  // process and palate -- what a dental atlas names -- and this is everything
  // else that was measured and then thrown away at export. The two abut and do
  // not overlap, the same arrangement as mandible-minus-teeth.
  // Only the maxillary exposure saw this. Registered in on the upper skull, with
  // the upper teeth held out of the fit as the check.
  { fma: 'FMA53649M', name: 'Mid-face',            layer: 'midface',  side: 'midline' },

  // ...and only the mandibular exposure saw this. The centred volume's mandible
  // is cut through both rami by its field of view (tools/fov-audit.mjs).
  { fma: 'FMA52748M', name: 'Mandibular ramus and inferior border',
    layer: 'ramus', side: 'midline' },

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
  maxilla:  { label: 'Maxilla & palate',       defaultOpacity: 1.0,  visible: true  },
  // The two FOCUSED exposures each see bone the centred volume's field of view
  // cut off, and each gets its own toggleable layer. They are separate from
  // `maxilla` and `mandible` because they are a different ACQUISITION, not a
  // different structure — everything the centred volume measured sits in those
  // two layers regardless of how far from the teeth it reaches.
  //
  // Both are EXCLUDED FROM CENTRING in build-assets.mjs. The mid-face reaches
  // 75 mm above the occlusal plane and the ramus 61 mm below it; leaving either
  // in the framing pulls the model's centre off the teeth, which is the same
  // failure the masseters would cause and the reason muscles are excluded.
  //
  // OFF BY DEFAULT since 0.6.0. They are excluded from centring for a reason —
  // they reach far beyond the teeth — and that same reach is what makes them
  // wrong on load: they frame the dentition inside a slab of skull and ramus
  // that is not what this atlas is about. Their being measured is exactly why
  // they stay in the model and get a toggle rather than being cropped away.
  midface:  { label: 'Mid-face',               defaultOpacity: 1.0,  visible: false },
  ramus:    { label: 'Ramus & inferior border', defaultOpacity: 1.0, visible: false },
  // Gingiva was 0.45 until 0.6.0 BECAUSE at full opacity it hides every root
  // and the app looks broken on load. The operator asked for 1.0 anyway; if it
  // reads wrong on screen, this is the line to move, not the mesh.
  gingiva:  { label: 'Gingiva',                defaultOpacity: 1.0,  visible: true  },
  // Pulp and PDL are off by default: they sit INSIDE the teeth, so showing them
  // on load reveals nothing and costs draw calls. The teeth layer's opacity is
  // what makes them visible.
  pulp:     { label: 'Pulp',                   defaultOpacity: 1.0,  visible: false },
  pdl:      { label: 'Periodontal ligament',   defaultOpacity: 1.0,  visible: true  },
  // Nerves are OFF by default. Two sets of geometry with very
  // different standing share this layer -- the mandibular trunk follows a canal
  // the scan actually resolves, while every maxillary course is textbook. That
  // distinction used to be carried by a "(schematic)" suffix on the display
  // name, which was the only place it lived; it is now a real `provenance` tier
  // (below), enforced on every build, so the names are clean. Do not let a later
  // tidy-up imply the maxillary nerves were measured -- the tier, not the name,
  // is what protects that now.
  nerves:   { label: 'Nerves',                 defaultOpacity: 1.0,  visible: false },
  // Arteries are OFF by default and share the nerves' canals: the inferior
  // alveolar artery runs inside the same measured lumen as the inferior
  // alveolar nerve, a fraction of a millimetre above it, so at full opacity
  // with nerves showing it is largely hidden. That is anatomy, not a bug.
  // THERE IS NO VEINS LAYER. The FMA has no inferior alveolar or infraorbital
  // vein to join on -- see the provenance note on FMA49695.
  // ONE toggle for the whole vascular tree, red and blue inside it. The colour
  // is carried per STRUCTURE (see `material` below and MATERIALS in
  // build-assets.mjs) rather than per layer, because a layer is a thing a user
  // switches on and nobody wants to switch on arteries and veins separately to
  // see a bundle. Veins carry TAH ids, not FMA ones — the FMA has no term for
  // any of them. See tools/ontology.test.mjs.
  vessels:  { label: 'Arteries & veins',       defaultOpacity: 1.0,  visible: false },
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
  { fma: 'FMA53243', name: 'Inferior alveolar nerve',
    layer: 'nerves', side: 'midline', bundle: 'inferior-alveolar' },
  { fma: 'FMA53243B', name: 'Inferior alveolar dental branches',
    layer: 'nerves', side: 'midline', bundle: 'lower-dental' },
  { fma: 'FMA53243T', name: 'Mental and incisive branches',
    layer: 'nerves', side: 'midline', bundle: 'incisive' },
  { fma: 'FMA77528', name: 'Superior dental plexus',
    layer: 'nerves', side: 'midline', bundle: 'superior-alveolar' },
  { fma: 'FMA77528B', name: 'Superior alveolar dental branches',
    layer: 'nerves', side: 'midline', bundle: 'upper-dental' },
  { fma: 'FMA77528T', name: 'PSA, MSA and ASA nerves',
    layer: 'nerves', side: 'midline', bundle: 'superior-alveolar' },
  // Split out of the entry above on 2026-09-02, because the infraorbital canal
  // is now traced and this nerve follows it. One mesh can carry only one tier,
  // so leaving it merged would have meant either promoting PSA/MSA/ASA, which
  // are still textbook courses, or hiding that this one is no longer.
  { fma: 'FMA52978', name: 'Infraorbital nerve',
    layer: 'nerves', side: 'midline', bundle: 'infraorbital' },

  // The terminal fans, added 2026-09-02. Until now both the infraorbital and
  // the mental nerve ended at their foramen with a single short stub, which
  // says nothing about what either nerve is FOR: everything a patient feels in
  // the lower lip, the chin, the upper lip, the side of the nose and the lower
  // eyelid arrives through these. They are what the two blocks a dentist gives
  // most often actually anaesthetise.
  //
  // The ids are the FMA's own for the branch SETS, not for a single branch and
  // not for one side -- fma75534 is 'Set of inferior palpebral branches of
  // infra-orbital nerve', which is exactly what one bilateral mesh of several
  // branches is. Checked against the FMA through EBI OLS, not guessed.
  { fma: 'FMA75534', name: 'Inferior palpebral branches',
    layer: 'nerves', side: 'midline', bundle: 'infraorbital' },
  { fma: 'FMA75535', name: 'External nasal branches',
    layer: 'nerves', side: 'midline', bundle: 'infraorbital' },
  { fma: 'FMA75536', name: 'Internal nasal branches',
    layer: 'nerves', side: 'midline', bundle: 'infraorbital' },
  { fma: 'FMA75537', name: 'Superior labial branches',
    layer: 'nerves', side: 'midline', bundle: 'infraorbital' },

  // The mental nerve's fan, added 2026-09-03 once the operator traced the
  // mental canal. The gingival branches are the ones a dentist is actually
  // aiming at with a mental block, and a purely cutaneous account of this nerve
  // leaves them out.
  { fma: 'FMA75520', name: 'Mental branches to the chin',
    layer: 'nerves', side: 'midline', bundle: 'mental' },
  { fma: 'FMA75521', name: 'Inferior labial branches',
    layer: 'nerves', side: 'midline', bundle: 'mental' },
  { fma: 'FMA75522', name: 'Gingival branches of the mental nerve',
    layer: 'nerves', side: 'midline', bundle: 'mental' },
  { fma: 'FMA52802', name: 'Greater palatine nerve',
    layer: 'nerves', side: 'midline', bundle: 'greater-palatine' },

  // --- Arteries: CBCT build only. See tools/cbct/vessels.py. ---
  //
  // Each shares a MEASURED canal with a nerve the atlas already draws, and is
  // offset within that same lumen. Nothing new was observed to add them: the
  // canal was measured, its contents were not, and the calibres and offsets are
  // chosen. Bilateral, one mesh each, matching the nerve convention.
  //
  { fma: 'FMA49695', name: 'Inferior alveolar artery',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'inferior-alveolar' },
  { fma: 'FMA49701', name: 'Mental artery',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'mental' },
  // No ontology names a mental vein either; it is the mental tributary of the
  // inferior alveolar vein, so it takes that vein's id with a suffix.
  { fma: 'TAHU15802M', name: 'Mental vein',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'mental' },
  { fma: 'FMA49767', name: 'Infraorbital artery',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'infraorbital' },

  // --- Veins: TAH ids, because the FMA does not name one of them ---
  //
  // Same lumens, same reasoning, drawn opposite their artery. The inferior
  // alveolar vein is BUCCAL of its artery, which is the one part of the
  // arrangement the sources fix (Kim: artery lingual to vein).
  { fma: 'TAHU15802', name: 'Inferior alveolar vein',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'inferior-alveolar' },
  { fma: 'TAHU15803', name: 'Dental veins',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'lower-dental' },
  { fma: 'TAHU15485', name: 'Infraorbital vein',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'infraorbital' },

  // --- The rest of the supply and drainage, 0.6.0 ---
  //
  // The incisive vessels are the CONTINUATION of the inferior alveolar ones
  // past the mental foramen, and neither ontology names them: the FMA has no
  // term, and the IFAA lists only dental, peridental, mental and mylohyoid
  // branches under TAH:U3863. They take the repo's derived-mesh suffix off
  // their own parent, which is exactly what the incisive NERVE does as
  // FMA53243T. Without them teeth 22-27 have no supply drawn at all: a chord
  // from the canal to a central incisor is 22-26 mm and runs through bone.
  { fma: 'FMA49695T', name: 'Incisive branch of the inferior alveolar artery',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'incisive' },
  { fma: 'TAHU15802T', name: 'Incisive branch of the inferior alveolar vein',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'incisive' },
  { fma: 'FMA49699', name: 'Inferior alveolar dental branches',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'lower-dental' },

  // Maxillary. PSA and ASA are separate meshes with exact ids because the FMA
  // names them separately and they arise separately — PSA from the maxillary
  // artery in the pterygopalatine fossa, ASA from the infraorbital artery
  // inside its canal. Their dental branches are split the same way rather than
  // filed as one "upper dental" mesh, which would be wrong about half of them.
  { fma: 'FMA49757', name: 'Posterior superior alveolar artery',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'superior-alveolar' },
  { fma: 'FMA49771', name: 'Anterior superior alveolar artery',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'superior-alveolar' },
  { fma: 'FMA49761', name: 'Posterior superior alveolar dental branches',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'upper-dental' },
  { fma: 'FMA49775', name: 'Anterior superior alveolar dental branches',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'upper-dental' },
  { fma: 'TAHU15800', name: 'Posterior superior alveolar veins',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'superior-alveolar' },
  { fma: 'TAHU15800B', name: 'Posterior superior alveolar dental tributaries',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'upper-dental' },
  // The anterior maxillary teeth drain to the INFRAORBITAL vein, not to the
  // posterior superior alveolar one, so their tributaries hang off TAH:U15485
  // rather than U15800. TAH names no anterior superior alveolar vein.
  { fma: 'TAHU15485B', name: 'Anterior superior alveolar tributaries',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'upper-dental' },

  // The one vessel here that belongs OUTSIDE the bone: it runs forward in a
  // groove on the palate, under the mucosa, from the greater palatine foramen
  // to the incisive canal. Its SHAPE is measured even though the vessel is not
  // — the course is found by casting up onto this patient's own palatal vault.
  { fma: 'FMA49795', name: 'Greater palatine artery',
    layer: 'vessels', material: 'artery', side: 'midline', bundle: 'greater-palatine' },
  // A GROOVE CARRIES A BUNDLE. The nerve and vein run the same measured course.
  // Neither the FMA nor the IFAA names a greater palatine vein, so it hangs off
  // TAH:U4540, the pterygoid plexus, which is what it actually drains into —
  // the same reasoning that put the anterior maxillary tributaries on the
  // infraorbital vein rather than under a tidier but wrong parent.
  { fma: 'TAHU4540P', name: 'Greater palatine vein',
    layer: 'vessels', material: 'vein', side: 'midline', bundle: 'greater-palatine' },
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


// --- Provenance -------------------------------------------------------------
//
// How each structure was actually obtained. The atlas has always been careful
// about this in prose -- the README's table, docs/phase-3-soft-tissue.md's
// provenance summary, and the caveat that invariant 4 protects -- but the MODEL
// did not carry it. Provenance survived only as a "(schematic)" suffix inside a
// display name, which cannot be filtered, cannot be styled, cannot be cited, and
// disappears the first time someone tidies the names.
//
// It belongs here, beside layer and side, for the same reason the notation
// derivation does: this file is where a structure's facts live.
//
// The tiers are the ones docs/phase-3-soft-tissue.md already defines:
//
//   measured   Directly from the CBCT. The geometry is this patient's.
//   derived    Generated FROM measured anatomy. Anchored to real landmarks, but
//              its shape involves a choice we made.
//   schematic  Not in the data at any resolution. Drawn from the literature.
//
// A fourth tier, `simulated`, is reserved for the pathology sliders and the
// anaesthetic diffusion on the wishlist. Nothing uses it yet; it exists so those
// features cannot ship without a tier, because geometry that is neither measured
// nor a literature mean is exactly what needs saying out loud.
//
// RULE: `tier` describes the geometry AS DRAWN, not the best evidence behind it.
// The inferior alveolar nerve follows a measured canal, but what is rendered is a
// tube of chosen calibre on that canal's centreline, so it is `derived` and the
// method says which part was measured. Overclaiming a tier because some input was
// measured is the failure this field exists to prevent.

export const TIERS = {
  measured:  { label: 'Measured',  blurb: 'Segmented directly from the cone-beam CT.' },
  derived:   { label: 'Derived',   blurb: 'Generated from measured anatomy.' },
  schematic: { label: 'Schematic', blurb: 'Not resolved by the scan. Drawn from the literature.' },
  simulated: { label: 'Simulated', blurb: 'Neither measured nor a literature mean.' },
};

const SRC = {
  dentalSegmentator:
    "Dot G. et al., 'DentalSegmentator: robust open source deep learning-based CT and CBCT image segmentation', J Dent (2024)",
  wheeler:
    "Wheeler's Dental Anatomy, Physiology and Occlusion — crown-height and cervical-line tables",
  // These cite what was actually used. Upgrading to a primary anatomical source
  // is on the wishlist -- and is NOT a citation edit: the geometry has to be
  // re-derived against the new reference first, or the citation credits a book
  // for a course it did not produce.
  wikiIAN:
    'en.wikipedia.org/wiki/Inferior_alveolar_nerve, /wiki/Mental_nerve',
  wikiSA:
    'en.wikipedia.org/wiki/Posterior_superior_alveolar_nerve, /wiki/Anterior_superior_alveolar_nerve',
  // Cited only where the geometry was actually re-derived against it. The
  // maxillary trunks were; the rest still say Wikipedia because that is still
  // what produced them.
  malamed:
    'Malamed, Handbook of Local Anesthesia — branching order and the bony relations a block is aimed at',
  gray:
    "Gray's Anatomy — the terminal branches of the infraorbital and mental nerves, and what each supplies",
  // Cited for the ARRANGEMENT of the bundle inside the mandibular canal, which
  // is the only part of the arterial geometry that is not a free choice. Both
  // primary series are reached through this review, so it is what is credited.
  jomrNVB:
    'Juodzbalys, Wang & Sabalys, J Oral Maxillofac Res 2010;1(1):e2 — the inferior alveolar neurovascular bundle in the mandibular canal (Kim et al., Pogrel et al.)',
};

// Keyed by layer where every member shares a provenance, and by FMA id where they
// do not. Per-tooth pulp and PDL resolve by layer, so all 28 inherit one entry.
const BY_LAYER = {
  teeth: {
    tier: 'measured',
    method: 'Marker-based watershed on the 0.16 mm volume, with bone seeded as its own basin so the segmentation cannot leak up the socket, then cut apart at the interproximal contacts. Meshed from grey levels rather than from the binary mask, which would terrace at the voxel size.',
  },
  pulp: {
    // The twelve ANTERIOR pulps only; every molar and premolar has its own
    // entry below. Splitting them was not optional: 16 of the 28 were remade on
    // 2026-09-03 and 14 of those are machine predictions, which cannot sit
    // under a `measured` claim written for something else.
    tier: 'measured',
    method: 'Traced by hand, slice by slice, over three rounds. No threshold separates pulp from dentin at 0.16 mm — below about three voxels wide, partial-volume averaging means no voxel ever reaches pulp density — so the lumen was calibrated by integrating the intensity deficit across each cross-section instead. Canals under about 0.5 mm and apical deltas are below the voxel size and are not drawn.',
  },
  pdl: {
    tier: 'derived',
    method: 'Both walls are measured — the root surface and the lamina dura — so the ligament space is in its true position and is continuous. It is drawn far THICKER than its real ~0.2 mm, which is barely one voxel and would be invisible.',
  },
  gingiva: {
    tier: 'derived',
    method: 'A collar lofted from the measured cementoenamel junction, one ring per tooth, with the papillae emerging where adjacent collars meet. The CEJ ring is refitted rather than trusted: thin enamel drops below threshold over contiguous runs of the ring, so measured aspects within 1 mm are kept and the rest is voted back to the published cervical-line curvature, anchored on crown height. The gingiva itself was never imaged.',
    sources: [SRC.wheeler],
  },
};

const BY_FMA = {
  FMA52748: {
    tier: 'measured',
    method: 'nnU-Net mandible label on the 0.16 mm volume, from the mandible-focused exposure registered into the centred frame. Cut by the field of view through both rami — see tools/fov-audit.mjs.',
    sources: [SRC.dentalSegmentator],
  },
  FMA53649: {
    tier: 'measured',
    method: "The whole nnU-Net 'upper skull' label on the centred volume, minus the teeth: alveolar process, palate, and the upper facial skeleton around them. It was previously cropped to within 22 mm of the upper teeth, which discarded 3.6 cm3 of measured bone. The boundary here is where the SEGMENTATION stops, not where the field of view does — this mesh is not truncated. What the maxillary exposure adds beyond it is FMA53649M.",
    sources: [SRC.dentalSegmentator],
  },
  FMA52748M: {
    tier: 'measured',
    method: "nnU-Net mandible label on the MANDIBULE-FOCUSED exposure, which sees 32.1 cm3 of mandible against the centred volume's 21.6, rigidly registered into the centred frame on that label and clipped to the 12.0 cm3 the centred volume never covered. It is the bone the centred field of view cut off: 172 mm2 and 191 mm2 of flat cap on its side walls, through both rami. Meshed in its own grid and only then transformed, because resampling onto the centred grid would have discarded exactly this anatomy.",
    sources: [SRC.dentalSegmentator],
  },
  FMA53649M: {
    tier: 'measured',
    method: "nnU-Net 'upper skull' label on the MAXILLARY exposure — a separate acquisition that sees 54.0 cm3 of upper skull against the centred volume's 31.3 — rigidly registered into the centred frame on that label and clipped to the 23.0 cm3 the centred volume never covered. Meshed in its own grid and only then transformed, because the two exposures sit about 35 mm apart and resampling onto the centred grid would have discarded exactly this anatomy. Registration Dice 0.902 on the fitted label; the UPPER TEETH, held out of the fit, land at 0.708 against a ceiling of 0.728.",
    sources: [SRC.dentalSegmentator],
  },

  // Nerves. The canal is measured; nothing inside it is. Keep the mandibular and
  // maxillary sides distinct — the whole point of the split is that one follows
  // anatomy this scan resolved and the other does not.
  FMA53243: {
    tier: 'derived',
    method: 'The mandibular canal was traced from the mandibular foramen to the mental foramen and is MEASURED. What is drawn is a tube of chosen calibre along that centreline: CBCT resolves the canal, not its contents, and the canal carries the inferior alveolar artery and vein alongside the nerve.',
  },
  FMA53243B: {
    tier: 'derived',
    method: 'One branch to each of the 14 lower apices. The apical foramina are measured and the trunk is on the measured canal, so both ends of every branch are real; the path between them is not. Nine arise from the trunk, ten from the incisive branch.',
  },
  FMA53243T: {
    tier: 'schematic',
    method: 'The mental foramen is placed by projecting the measured premolar apices onto the canal centreline, rather than taken from the centreline itself, whose anterior end carries reconstruction spurs. The mental and incisive courses beyond it are inferred.',
    sources: [SRC.wikiIAN],
  },
  // --- Arteries and veins ---
  //
  // DERIVED, not measured, and for the same reason the inferior alveolar nerve
  // is: the canal is measured and its contents are not. Each vessel is a tube of
  // chosen calibre at a chosen offset inside a lumen that was.
  'FMA49695T': {
    tier: 'derived',
    method: 'The incisive branch, the CONTINUATION of the inferior alveolar artery past the mental foramen. Built on the same course nerve.py uses for the incisive nerve — through the measured anterior apices, which are the only evidence of where that canal runs on this patient — and then routed clear of the teeth. Neither ontology names this vessel: the FMA has no term and the IFAA lists only dental, peridental, mental and mylohyoid branches under TAH:U3863, so it carries the repo\'s derived-mesh suffix off its parent, exactly as the incisive NERVE does as FMA53243T. Without it teeth 22–27 have no arterial supply drawn, because a chord from the canal to a central incisor is 22–26 mm and runs through bone.',
    source: SRC.jomrNVB,
  },
  'TAHU15802T': {
    tier: 'derived',
    method: 'The incisive branch of the inferior alveolar vein, on the same course as its artery and built the same way. See FMA49695T for why it carries a suffix rather than an id of its own.',
    source: SRC.jomrNVB,
  },
  FMA49699: {
    tier: 'derived',
    method: 'One arterial branch to each of the 14 lower teeth, from whichever parent is nearer — the inferior alveolar artery in the canal for the posterior teeth, the incisive branch for the anterior ones. Both ends are MEASURED — a trunk on a measured canal or arc, and an apical foramen from the hand-traced pulp — and the path between them is convention. Every branch is then ROUTED OUT OF DENTIN: a straight chord to an apex crosses whatever lies between, which in a crowded arch is usually the neighbouring root. Each course is pushed clear of the tooth labels by its own tube radius plus a margin and re-smoothed, with the push getting the last word, and only the last 1.5 mm is allowed to be inside hard tissue — that is the apical foramen, which is the point. All 76 branches pass: none travels through dentin.',
    source: SRC.jomrNVB,
  },
  FMA49757: {
    tier: 'schematic',
    method: 'The posterior superior alveolar artery, drawn on the SAME arc nerve_maxilla.py builds the superior dental plexus on — a smooth curve through points set 2.6 mm beyond each measured apex, away from that tooth\'s own centre — offset 0.85 mm buccally off it. Sharing the construction is deliberate: three independent guesses at one course would drift apart, and the arc is the only thing here anchored to measured foramina. SCHEMATIC, like the nerve plexus it accompanies: the posterior superior alveolar canals are thin, often dehiscent, and nothing of this vessel was seen in the scan. It carries the premolars as well as the molars — that is MSA territory, present in perhaps half of people and with no separate artery in the FMA. Confined to MEASURED BONE the way nerve_maxilla confines its nerves, and against the same masks: a course laid between apices floats out of the bone wherever the arch is concave. The arc is 100% inside measured bone against 83% unconfined.',
    sources: [SRC.wikiSA, SRC.jomrNVB],
  },
  FMA49771: {
    tier: 'schematic',
    method: 'The anterior superior alveolar artery, the anterior run of the same arc. Arises from the infraorbital artery inside its canal, which is why it is a separate mesh from the posterior one rather than a segment of it. SCHEMATIC for the same reason as FMA49757. Confined to MEASURED BONE the way nerve_maxilla confines its nerves, and against the same masks: a course laid between apices floats out of the bone wherever the arch is concave. The arc is 100% inside measured bone against 83% unconfined.',
    sources: [SRC.wikiSA, SRC.jomrNVB],
  },
  FMA49761: {
    tier: 'derived',
    method: 'Arterial branches to the 8 posterior maxillary teeth. Both ends are MEASURED — a trunk on a measured canal or arc, and an apical foramen from the hand-traced pulp — and the path between them is convention. Every branch is then ROUTED OUT OF DENTIN: a straight chord to an apex crosses whatever lies between, which in a crowded arch is usually the neighbouring root. Each course is pushed clear of the tooth labels by its own tube radius plus a margin and re-smoothed, with the push getting the last word, and only the last 1.5 mm is allowed to be inside hard tissue — that is the apical foramen, which is the point. All 76 branches pass: none travels through dentin. Split from the anterior branches rather than shipped as one "upper dental" mesh, which would have to be filed under either the anterior or the posterior superior alveolar artery and would then be wrong about half its own content.',
    sources: [SRC.wikiSA, SRC.jomrNVB],
  },
  FMA49775: {
    tier: 'derived',
    method: 'Arterial branches to the 6 anterior maxillary teeth. Both ends are MEASURED — a trunk on a measured canal or arc, and an apical foramen from the hand-traced pulp — and the path between them is convention. Every branch is then ROUTED OUT OF DENTIN: a straight chord to an apex crosses whatever lies between, which in a crowded arch is usually the neighbouring root. Each course is pushed clear of the tooth labels by its own tube radius plus a margin and re-smoothed, with the push getting the last word, and only the last 1.5 mm is allowed to be inside hard tissue — that is the apical foramen, which is the point. All 76 branches pass: none travels through dentin.',
    sources: [SRC.wikiSA, SRC.jomrNVB],
  },
  'TAHU15800': {
    tier: 'schematic',
    method: 'The posterior superior alveolar veins, on the shared maxillary arc offset 0.85 mm lingually — the mirror of FMA49757 and schematic for the same reason. TAH:U15800, venae alveolares superiores posteriores, a tributary of the pterygoid plexus; the FMA names no maxillary vein at all. Confined to MEASURED BONE the way nerve_maxilla confines its nerves, and against the same masks: a course laid between apices floats out of the bone wherever the arch is concave. The arc is 100% inside measured bone against 83% unconfined.',
    sources: [SRC.wikiSA, SRC.jomrNVB],
  },
  'TAHU15800B': {
    tier: 'derived',
    method: 'Venous tributaries from the 8 posterior maxillary teeth to the posterior superior alveolar veins. Both ends are MEASURED — a trunk on a measured canal or arc, and an apical foramen from the hand-traced pulp — and the path between them is convention. Every branch is then ROUTED OUT OF DENTIN: a straight chord to an apex crosses whatever lies between, which in a crowded arch is usually the neighbouring root. Each course is pushed clear of the tooth labels by its own tube radius plus a margin and re-smoothed, with the push getting the last word, and only the last 1.5 mm is allowed to be inside hard tissue — that is the apical foramen, which is the point. All 76 branches pass: none travels through dentin.',
    sources: [SRC.wikiSA, SRC.jomrNVB],
  },
  'TAHU15485B': {
    tier: 'derived',
    method: 'Venous tributaries from the 6 anterior maxillary teeth. They hang off TAH:U15485, the INFRAORBITAL vein, and not off the posterior superior alveolar one, because that is where the anterior maxilla actually drains — TAH names no anterior superior alveolar vein, so filing them under U15800 would have asserted the wrong destination for the sake of a tidier id. Both ends are MEASURED — a trunk on a measured canal or arc, and an apical foramen from the hand-traced pulp — and the path between them is convention. Every branch is then ROUTED OUT OF DENTIN: a straight chord to an apex crosses whatever lies between, which in a crowded arch is usually the neighbouring root. Each course is pushed clear of the tooth labels by its own tube radius plus a margin and re-smoothed, with the push getting the last word, and only the last 1.5 mm is allowed to be inside hard tissue — that is the apical foramen, which is the point. All 76 branches pass: none travels through dentin.',
    sources: [SRC.wikiSA, SRC.jomrNVB],
  },
  FMA52802: {
    tier: 'derived',
    method: "The greater palatine nerve, on the same measured palatal course as its artery — the groove carries a bundle, so all three members run it together. The SHAPE is measured: the course is found by casting a ray up onto this patient's own palatal vault at each coronal station, bounded medial to the measured palatal wall of the arch. Which of the three lies medial is CONVENTION — no source was found for the arrangement in this groove, unlike the mandibular canal, where it is Kim and Pogrel. The posterior end is where the traced palate runs out, not the greater palatine foramen, which was not located.",
    sources: [SRC.gray],
  },
  'TAHU4540P': {
    tier: 'derived',
    method: "The greater palatine vein, on the same measured palatal course as its artery and nerve. Neither the FMA nor the IFAA names this vein — checked against an FMA index carrying 3,741 vein terms and against the IFAA's own tributary lists — so it carries TAH:U4540, the PTERYGOID PLEXUS it drains into, with the repo's derived-mesh suffix. That is the most precise identifier that exists for it, and the same reasoning that put the anterior maxillary tributaries on the infraorbital vein rather than under a tidier but wrong parent. It is the LATERAL member of the bundle, so it is the one that meets the alveolar process: at 0.75 mm out it grazed a root, and the bundle was narrowed to 0.62 mm to fit the groove — a constraint on the drawing, not a fact about the patient.",
    sources: [SRC.gray],
  },
  'TAHU15802M': {
    tier: 'derived',
    method: 'The mental vein, leaving the MEASURED mental foramen on the mental nerve and artery\'s own course, because all three emerge together. No ontology names a mental vein either, so it is the mental tributary of the inferior alveolar vein and takes that vein\'s id with a suffix. 7 mm of it is drawn, matching the nerve and artery stubs: where it goes after that is on the face, which this scan does not contain.',
    source: SRC.jomrNVB,
  },
  FMA49795: {
    tier: 'derived',
    method: "The greater palatine artery, running forward in its groove on the hard palate. Unlike every other vessel here it belongs OUTSIDE the bone, under the mucosa, so it is not confined into it: at each coronal station the palatal surface is found by casting a ray UP from the oral cavity — which meets the palatal plate first and can meet nothing else, rule 139's argument for finding skin, used on a different surface — and the course sits 0.7 mm below it. WHICH station is taken is measured too: at every level the palate's LOWEST point on each side is the lateral gutter between the midline ridge and the alveolar process, which is where this groove runs, so the course is scanned for rather than placed at a guessed fraction of the way to the midline. So the vessel is schematic but its SHAPE follows this patient's own vault, which is what a reader will actually check it against. Two things it is NOT: the greater palatine foramen was not located, so the posterior end is where the traced palate runs out rather than a landmark; and the anterior end stops short of the incisive canal, which is not traced either. It grazes a palatal root by 0.14 mm, less than the 0.16 mm voxel and so finer than the tooth boundary is known.",
    sources: [SRC.gray],
  },
  FMA49767: {
    tier: 'derived',
    method: "Drawn inside the operator's own traced infraorbital canal, packed along that canal's MEASURED LONG AXIS rather than against its equivalent-circle radius. This canal is an oval — 2.0:1 on the right and 2.4:1 on the left, semi-major 1.60 and 1.95 mm against semi-minor 0.85 and 0.90 — and io_centreline.py now records the axis per sample, so the direction the vessel is placed along is measured too. Packing against the equivalent circle instead had buried this artery inside the drawn nerve along 100% and 89% of its length. It now clears that nerve everywhere on the left and along 96% of the right, where the remaining overlap is 0.014 mm. CONTEXT FOR THAT RESIDUE: the infraorbital NERVE is drawn at an absolute 1.05 mm calibre and is itself wider than this canal's short semi-axis at 70% and 37% of samples, by up to 0.44 mm, so at the narrow ends there is no arrangement that fits both. Which end of the long axis carries the artery and which the vein is convention: no source was found for the arrangement inside this canal, unlike the mandibular one.",
    source: SRC.jomrNVB,
  },
  'TAHU15802': {
    tier: 'derived',
    method: 'The inferior alveolar vein, in the MEASURED mandibular canal on the same centreline as its artery and the nerve, drawn BUCCAL of the artery — which is the one part of the arrangement the sources actually fix (Kim: the vessels lie superior to the nerve, with the artery lingual to the vein). Radius 0.15 of the canal\'s own local radius against the artery\'s 0.13, since the vein is the larger of the two. Every point is checked to lie inside the canal wall, clear of the nerve, and clear of the artery: worst clearances 0.015, 0.030 and 0.032 mm, with nothing touching. Named by TAH because the FMA has no term for this vein.',
    source: SRC.jomrNVB,
  },
  'TAHU15803': {
    tier: 'derived',
    method: "The dental veins, drawn from the inferior alveolar vein to the same MEASURED apical foramina the nerve's dental branches use, so both ends of every branch are real and the path between them is convention — the venous counterpart of FMA53243B, and the same tier for the same reason. 17 of the 19 recorded apices are drawn; teeth 24 and 25 are not, because they lie more than 25 mm from a vein that stops at the mental foramen and their drainage is by the incisive vein, which is not built. TAH:U15803 is a child of TAH:U15802 in the IFAA hierarchy, which is exactly the relationship these branches have to the trunk.",
    source: SRC.jomrNVB,
  },
  'TAHU15485': {
    tier: 'derived',
    method: 'The infraorbital vein, at the opposite end of the traced canal\'s measured long axis from its artery, built by the same rule and checked the same way. Which vessel takes which end is convention — see FMA49767. Named by TAH because the FMA has no term for this vein.',
    source: SRC.jomrNVB,
  },

  FMA49695: {
    tier: 'derived',
    method: 'Drawn inside the MEASURED mandibular canal, on the identical centreline as the inferior alveolar nerve — it is read through the same function, so the two cannot drift apart. Radius and offset are fractions of the canal\'s own local radius (0.13 and 0.80 of it), so the vessel narrows where the canal does instead of bursting out of it; every point is checked to lie inside the canal wall and clear of the nerve, and all 209 do, by 0.02–0.06 mm and 0.04–0.11 mm at worst. The ARRANGEMENT — superior to the nerve, lingual of the vein — is sourced. What is NOT modelled is that the same series report the position rotating along the canal (buccal in the pterygomandibular space, superior at the molars, lingual at the premolars, in 77.4%); one constant offset runs the whole length, because the review\'s own conclusion is that there is no consistent pattern for the entire canal and a rotating course would assert one patient\'s variant. Its accompanying vein is TAHU15802, drawn buccal of it in the same lumen; the FMA has no term for that vein, so it carries an IFAA TAH id instead.',
    source: SRC.jomrNVB,
  },
  FMA49701: {
    tier: 'derived',
    method: 'The terminal branch of the inferior alveolar artery, leaving the MEASURED mental foramen — the one the operator\'s own tracing placed — on the same course out of the bone as the mental nerve, because the two emerge together. 7 mm of it is drawn, matching the nerve\'s stub, and the calibre tapers 0.22 to 0.10 mm. Where it goes after that is on the face, which this scan does not contain (the anterior reconstruction wall sits 15.8 mm in front of the upper incisors), so the run stops rather than being invented across skin that was never imaged.',
    source: SRC.jomrNVB,
  },

  FMA77528: {
    tier: 'schematic',
    method: 'The superior alveolar canals are thin, often dehiscent, and not reliably visible at 0.16 mm. Nothing of this plexus was seen in the scan.',
    sources: [SRC.wikiSA],
  },
  FMA77528B: {
    tier: 'schematic',
    method: 'Drawn to the measured maxillary apices, so the endpoints are real and the courses are not.',
    sources: [SRC.wikiSA],
  },
  FMA77528T: {
    tier: 'schematic',
    method: "Textbook branching order: PSA leaves V2 directly in the pterygopalatine fossa, while MSA and ASA descend from the infraorbital nerve inside its canal. Re-derived against Malamed 2026-09-01 and CONFINED TO MEASURED BONE — the centred volume's hard tissue union the maxillary exposure registered in. Before that these courses were never tested against bone and 72% of this mesh lay outside it, a median of 3.5 mm and up to 10.1 mm out, floating in the sinus; it is now 0.5 mm and 1.2 mm, which is the tube's own radius. Where MSA and ASA LEAVE the infraorbital nerve is placed by arc length along the measured canal — anterior for ASA, midway for MSA — so their origins sit on measured geometry while the courses beyond remain textbook. Still SCHEMATIC: the superior alveolar canals themselves are thin, often dehiscent, and were not resolved.",
    source: SRC.malamed,
  },
  // The four terminal groups of the infraorbital nerve share one method: both
  // ends measured on this patient, the path between them convention. They are
  // DERIVED for the same reason the dental branches are, and they sit at that
  // tier rather than schematic because the scan really does decide where each
  // one stops -- not a figure, and not a length someone chose.
  ...Object.fromEntries(['FMA75534', 'FMA75535', 'FMA75536', 'FMA75537',
                         'FMA75520', 'FMA75521', 'FMA75522'].map((f) => [f, {
    tier: 'derived',
    method: "Terminal branches of the infraorbital and mental nerves. Each leaves a MEASURED foramen — both canals were hand-traced by the operator, the infraorbital in the maxillary exposure and the mental in the mandibular one — and heads across a MEASURED face: the outward normal of the skin at each foramen, and how deep the foramen lies beneath it, come from the air/tissue boundary in the scan. CBCT has poor soft-tissue CONTRAST but an excellent air/tissue BOUNDARY, and that boundary is the only soft-tissue measurement used here. WHICH branches exist, how many, and where each group heads is Gray's. WHAT IS DRAWN IS A STUB, 5.0–7.5 mm by group: each branch's true termination on the skin was measured and is recorded in docs/cbct-nerve-face.json, but the face it ends on is not rendered yet, so a branch drawn to its full 12–33 mm ends in mid-air and reads as a wire rather than as anatomy. The heading is measured; the drawn length is a placeholder and will be lifted when there is a surface to land on. Two invariants fail the build: no branch may re-enter bone, and none may cross the dental midline.",
    sources: [SRC.gray, SRC.malamed],
  }])),

  // --- Pulp, molars and premolars, remade 2026-09-03 --------------------------
  // Two teeth the operator traced densely in slicer.py, every slice painted.
  // This is the same tier as the anterior pulps and a better instance of it:
  // 120 and 103 painted axial slices against the eleven-section tracings the
  // rest of the atlas was built from.
  ...Object.fromEntries(['FMA55705-pulp', 'FMA55706-pulp'].map((f) => [f, {
    tier: 'measured',
    method: 'Hand-traced by the operator in tools/cbct/slicer.py — three linked planes, every slice painted, 120 and 103 axial slices respectively. Nothing is interpolated between slices and nothing is smoothed before meshing: what is drawn is what was painted. This replaces a 2026-08-30 tracing of the same tooth built from ELEVEN axial sections with the course interpolated between them; the two agree at Dice 0.563, which is a fair measure of how much that method was costing.',
  }])),

  // The other fourteen were segmented by a classifier rather than by hand.
  //
  // They are `measured` on the operator's ruling, and he is right that the
  // alternative was inconsistent: the teeth, the mandible and the maxilla are
  // all `measured` and every one of them came out of a neural network. Calling
  // nnU-Net's output measured and a gradient-boosted classifier's output
  // derived was a distinction about which algorithm, not about whether the
  // scan decided it. Both read this CBCT and nothing else.
  //
  // The tier says the SCAN decided it. The method below says how, and says
  // plainly which of these no human has yet looked at.
  ...Object.fromEntries(['FMA55697-pulp', 'FMA55698-pulp', 'FMA55688-pulp', 'FMA55689-pulp', 'FMA55690-pulp', 'FMA55691-pulp', 'FMA55699-pulp', 'FMA55700-pulp', 'FMA55703-pulp', 'FMA55704-pulp', 'FMA55692-pulp', 'FMA55693-pulp', 'FMA55694-pulp', 'FMA55695-pulp'].map((f) => [f, {
    tier: 'measured',
    method: "Segmented by a gradient-boosted classifier (tools/cbct/pulp_learn.py) from this CBCT, trained on the operator's two densely hand-traced molars and six earlier tracings. Every canal is then routed to that tooth's own MEASURED apical foramen through the model's probability field, which brings each within 0.36 mm of its apices bar three upper-molar canals. Three physical rules are enforced afterwards: the pulp is clipped to its own tooth, its radius is capped by an envelope tapering to 0.16 mm at each measured foramen, and it is reduced to a single connected body. Held out on a tooth it had never seen the classifier scores Dice 0.470 against that tooth's older hand-trace — against 0.563, which is what two careful human tracings of one tooth score against each other. Contralateral pairs agree to within 19% on seven of eight. NOT YET REVIEWED BY EYE; tooth 18 differs from its traced counterpart by 32% and is the one to check first.",
    sources: [SRC.dentalSegmentator],
  }])),

  FMA52978: {
    tier: 'derived',
    method: 'Follows the MEASURED infraorbital canal. The canal was hand-traced by the operator on cross-sections cut perpendicular to its own axis at 1 mm intervals in the maxillary exposure — the exposure that saw it, the posterior end reaching 0.6 mm above the centred volume\'s reconstruction ceiling — and the centreline was carried into the atlas frame as points, never resampled as voxels. What is DRAWN is a tube of chosen calibre on that centreline, exactly as for the inferior alveolar nerve: the canal carries the infraorbital nerve, artery and vein together, so the lumen is wider than the nerve. The drawn surface lies a median 0.16 mm and at most 0.99 mm from the traced lumen. Derived, not measured: the canal was observed, its contents were not.',
    source: SRC.malamed,
  },
};

/** Provenance for a structure: which tier, by what method, on whose authority. */
export function provenance(s) {
  const p = BY_FMA[s.fma] ?? BY_LAYER[s.layer];
  if (!p) return null;
  return { ...p, ...TIERS[p.tier], tier: p.tier };
}
