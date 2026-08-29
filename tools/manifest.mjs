// The BodyParts3D structures 3Dentes uses, and how they group into UI layers.
//
// FMA ids are Foundational Model of Anatomy identifiers; they are the filenames
// in the BodyParts3D distribution (FMA55697.stl) and the node names we bake into
// the built .glb, so they are the join key across the whole pipeline.
//
// `side` is ANATOMICAL side (the patient's), not the viewer's. The build script
// asserts it against mesh position — see checkLaterality in build-assets.mjs.
//
// For teeth, `position` is the count from the midline: 1 = central incisor,
// 2 = lateral incisor, 3 = canine, 4/5 = premolars, 6/7 = molars, 8 = third
// molar. Universal / FDI / Palmer notation is DERIVED from arch + side +
// position by toothNotation() below, never typed by hand — 28 hand-entered
// tooth numbers is 28 chances to mislabel a tooth.

export const SOURCE_BASE =
  'https://raw.githubusercontent.com/Kevin-Mattheus-Moerman/BodyParts3D/main/assets/BodyParts3D_data/stl';

// Where a structure's mesh comes from. Two trees, kept physically separate
// because their licences differ and ShareAlike is inherited by anything derived
// from BodyParts3D meshes (invariant 3 in CLAUDE.md):
//
//   bodyparts3d  assets/source/stl  -- CC BY-SA 2.1 JP, external morphology of
//                                      a different individual
//   cbct         assets/cbct/stl    -- measured from the operator's own scan,
//                                      unencumbered
//
// Teeth exist in both, under the SAME FMA ids, which is what makes the CBCT set
// a drop-in replacement rather than a schema change. TOOTH_SOURCE selects which
// one the build uses; everything else (jaws, gingiva, muscles) has no CBCT
// equivalent and always comes from BodyParts3D.
export const TOOTH_SOURCE =
  process.env.TOOTH_SOURCE === 'cbct' ? 'cbct' : 'bodyparts3d';

export const SOURCE_DIRS = {
  bodyparts3d: ['assets', 'source', 'stl'],
  cbct: ['assets', 'cbct', 'stl'],
};

const tooth = (fma, arch, side, position, type) => ({
  fma, arch, side, position, type, layer: 'teeth', source: TOOTH_SOURCE,
});

const BODYPARTS3D_STRUCTURES = [
  // --- Permanent teeth: 28. Third molars (position 8) are absent from BodyParts3D. ---
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
  { fma: 'FMA53649', name: 'Right maxilla',       layer: 'maxilla',  side: 'right'   },
  { fma: 'FMA53650', name: 'Left maxilla',        layer: 'maxilla',  side: 'left'    },
  { fma: 'FMA53655', name: 'Right palatine bone', layer: 'maxilla',  side: 'right'   },
  { fma: 'FMA53656', name: 'Left palatine bone',  layer: 'maxilla',  side: 'left'    },

  // --- Soft tissue ---
  { fma: 'FMA59763', name: 'Gingiva of upper jaw', layer: 'gingiva', side: 'midline' },
  { fma: 'FMA59764', name: 'Gingiva of lower jaw', layer: 'gingiva', side: 'midline' },

  // --- Muscles of mastication ---
  { fma: 'FMA49001', name: 'Right masseter, superficial part',    layer: 'muscles', side: 'right' },
  { fma: 'FMA49002', name: 'Left masseter, superficial part',     layer: 'muscles', side: 'left'  },
  { fma: 'FMA49004', name: 'Right masseter, deep part',           layer: 'muscles', side: 'right' },
  { fma: 'FMA49005', name: 'Left masseter, deep part',            layer: 'muscles', side: 'left'  },
  { fma: 'FMA49012', name: 'Right medial pterygoid',              layer: 'muscles', side: 'right' },
  { fma: 'FMA49013', name: 'Left medial pterygoid',               layer: 'muscles', side: 'left'  },
  { fma: 'FMA49024', name: 'Right lateral pterygoid, upper head', layer: 'muscles', side: 'right' },
  { fma: 'FMA49025', name: 'Left lateral pterygoid, upper head',  layer: 'muscles', side: 'left'  },
  { fma: 'FMA49022', name: 'Right lateral pterygoid, lower head', layer: 'muscles', side: 'right' },
  { fma: 'FMA49023', name: 'Left lateral pterygoid, lower head',  layer: 'muscles', side: 'left'  },
];

export const LAYERS = {
  teeth:    { label: 'Teeth',                  defaultOpacity: 1.0,  visible: true  },
  mandible: { label: 'Mandible',               defaultOpacity: 1.0,  visible: true  },
  maxilla:  { label: 'Maxilla & palatine',     defaultOpacity: 1.0,  visible: true  },
  // Gingiva at full opacity hides every root and the app looks broken on load.
  gingiva:  { label: 'Gingiva',                defaultOpacity: 0.45, visible: true  },
  // Muscles enclose the whole jaw; visible by default they hide everything else.
  muscles:  { label: 'Muscles of mastication', defaultOpacity: 0.9,  visible: false },
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

/** Derive clinical notation for a tooth. Returns null for non-tooth structures. */
// Structures that exist as measured CBCT meshes. Everything else in the
// BodyParts3D set -- the muscles, and three of the four maxilla parts -- has no
// equivalent, because this scan has no soft-tissue contrast at all and because
// DentalSegmentator's "Upper Skull" is cropped here to the alveolar process.
//
// A CBCT build therefore contains FEWER structures rather than a mix. That is
// deliberate: BodyParts3D is a whole-body frame with the head about 1470 mm off
// the floor, while CBCT is scanner-centred, so combining them naively produced a
// model 1582 mm tall. They are also different people -- one individual's teeth
// do not sit in another's jaws. Borrowed soft tissue has to be registered INTO
// the patient's frame before it can be mixed in, and that is not done yet.
const CBCT_AVAILABLE = new Set([
  ...BODYPARTS3D_STRUCTURES.filter((s) => s.layer === 'teeth').map((s) => s.fma),
  'FMA52748',   // mandible
  'FMA53649',   // maxilla -- alveolar process and palate
  'FMA59763', 'FMA59764',   // gingiva, upper and lower
]);

export const STRUCTURES =
  TOOTH_SOURCE === 'cbct'
    ? BODYPARTS3D_STRUCTURES
        .filter((s) => CBCT_AVAILABLE.has(s.fma))
        .map((s) => ({ ...s, source: 'cbct' }))
    : BODYPARTS3D_STRUCTURES;

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
export function structureName(s) {
  if (s.layer !== 'teeth') return s.name;
  const arch = s.arch === 'maxillary' ? 'upper' : 'lower';
  return `${s.side === 'right' ? 'Right' : 'Left'} ${arch} ${s.type}`;
}
