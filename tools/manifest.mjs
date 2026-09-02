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
  midface:  { label: 'Mid-face',               defaultOpacity: 1.0,  visible: true  },
  ramus:    { label: 'Ramus & inferior border', defaultOpacity: 1.0, visible: true  },
  // Gingiva at full opacity hides every root and the app looks broken on load.
  gingiva:  { label: 'Gingiva',                defaultOpacity: 0.45, visible: true  },
  // Pulp and PDL are off by default: they sit INSIDE the teeth, so showing them
  // on load reveals nothing and costs draw calls. The teeth layer's opacity is
  // what makes them visible.
  pulp:     { label: 'Pulp',                   defaultOpacity: 1.0,  visible: false },
  pdl:      { label: 'Periodontal ligament',   defaultOpacity: 0.85, visible: false },
  // Nerves are OFF by default. Two sets of geometry with very
  // different standing share this layer -- the mandibular trunk follows a canal
  // the scan actually resolves, while every maxillary course is textbook. That
  // distinction used to be carried by a "(schematic)" suffix on the display
  // name, which was the only place it lived; it is now a real `provenance` tier
  // (below), enforced on every build, so the names are clean. Do not let a later
  // tidy-up imply the maxillary nerves were measured -- the tier, not the name,
  // is what protects that now.
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
  { fma: 'FMA53381', name: 'Inferior alveolar nerve',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53381B', name: 'Inferior alveolar dental branches',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53381T', name: 'Mental and incisive branches',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53088', name: 'Superior dental plexus',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53088B', name: 'Superior alveolar dental branches',
    layer: 'nerves', side: 'midline' },
  { fma: 'FMA53088T', name: 'Infraorbital, PSA, MSA and ASA nerves',
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
};

// Keyed by layer where every member shares a provenance, and by FMA id where they
// do not. Per-tooth pulp and PDL resolve by layer, so all 28 inherit one entry.
const BY_LAYER = {
  teeth: {
    tier: 'measured',
    method: 'Marker-based watershed on the 0.16 mm volume, with bone seeded as its own basin so the segmentation cannot leak up the socket, then cut apart at the interproximal contacts. Meshed from grey levels rather than from the binary mask, which would terrace at the voxel size.',
  },
  pulp: {
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
  FMA53381: {
    tier: 'derived',
    method: 'The mandibular canal was traced from the mandibular foramen to the mental foramen and is MEASURED. What is drawn is a tube of chosen calibre along that centreline: CBCT resolves the canal, not its contents, and the canal carries the inferior alveolar artery and vein alongside the nerve.',
  },
  FMA53381B: {
    tier: 'derived',
    method: 'One branch to each of the 14 lower apices. The apical foramina are measured and the trunk is on the measured canal, so both ends of every branch are real; the path between them is not. Nine arise from the trunk, ten from the incisive branch.',
  },
  FMA53381T: {
    tier: 'schematic',
    method: 'The mental foramen is placed by projecting the measured premolar apices onto the canal centreline, rather than taken from the centreline itself, whose anterior end carries reconstruction spurs. The mental and incisive courses beyond it are inferred.',
    sources: [SRC.wikiIAN],
  },
  FMA53088: {
    tier: 'schematic',
    method: 'The superior alveolar canals are thin, often dehiscent, and not reliably visible at 0.16 mm. Nothing of this plexus was seen in the scan.',
    sources: [SRC.wikiSA],
  },
  FMA53088B: {
    tier: 'schematic',
    method: 'Drawn to the measured maxillary apices, so the endpoints are real and the courses are not.',
    sources: [SRC.wikiSA],
  },
  FMA53088T: {
    tier: 'schematic',
    method: "Textbook branching order: PSA leaves V2 directly in the pterygopalatine fossa, while MSA and ASA descend from the infraorbital nerve inside its canal. Re-derived against Malamed 2026-09-01 and now CONFINED TO MEASURED BONE — the centred volume's hard tissue union the maxillary exposure registered in. Before that these courses were never tested against bone and 72% of this mesh lay outside it, a median of 3.5 mm and up to 10.1 mm out, floating in the sinus; it is now 0.5 mm and 1.2 mm, which is the tube's own radius. Still SCHEMATIC: the infraorbital canal does not resolve at 0.16 mm, so the course is bounded by measured bone but was never observed in it.",
    sources: [SRC.malamed, SRC.wikiSA],
  },
};

/** Provenance for a structure: which tier, by what method, on whose authority. */
export function provenance(s) {
  const p = BY_FMA[s.fma] ?? BY_LAYER[s.layer];
  if (!p) return null;
  return { ...p, ...TIERS[p.tier], tier: p.tier };
}
