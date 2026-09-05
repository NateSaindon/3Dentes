# Changelog

Notable changes to the deployed atlas at
<https://natesaindon.github.io/3Dentes/>.

This file records what changed in the **published** app. Every commit on `main`
deploys, so the versions below group those commits into releases rather than
listing them one by one. Engineering detail and the reasoning behind individual
decisions live in [CLAUDE.md](CLAUDE.md); planned work lives in
[docs/wishlist.md](docs/wishlist.md).

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this
project uses [semantic versioning](https://semver.org/) loosely — the minor
number moves when the anatomy or the interface changes in a way a user would
notice, the patch number for fixes and corrections.

**Anatomy provenance is part of the changelog.** When a structure moves between
`measured`, `derived` and `schematic`, or when what it is built from changes,
that is a user-visible change to what the atlas claims and it is recorded here.

## [0.7.0] — 2026-09-05

The teeth get their enamel, and the pulp stops being hollow.

### Added

- **Enamel, 26 caps in one `Enamel` layer.** A depth-limited shell on the
  anatomic crown, bounded outside by the measured crown surface, inside by the
  published thickness envelope, and apically by each tooth's own measured
  cervical ring. **`derived`** — the extent is measured, the thickness is
  literature. Per-tooth enamel VOLUME and enamel-as-%-of-crown are deliberately
  not published as measured quantities: re-cutting the interproximal contacts
  moves them by up to 20% and 14.4 points. The thickness figures at the sites the
  literature reports are robust to that same re-cut, to a median of 0.03 mm.
- **Teeth 19 and 30 have no enamel, and that is the claim.** Both carry zirconia
  crowns, so their natural enamel was prepped away before cementation. They hold
  11.0 and 31.0 mm³ of residue against 215–290 mm³ for every other molar, and
  344.7 and 276.7 mm³ of restoration against ≤0.16 mm³ for every natural tooth.
  Shipping a cap there would assert tissue that is not in the mouth.

### Changed

- **The cementoenamel ring the enamel cap is bounded by is no longer 47%
  constant.** An angle that found no cervical narrowing used to fall back to a
  flat 45% of tooth length, and so did any angle whose reading came out apical of
  it — 43% of 1,008 angles were that constant and only 53% were measured. On the
  upper molars it put a third of the circumference 1.6–2.2 mm too apical, which
  paints enamel down a root. Those angles are now filled from each tooth's own
  measured angles, which can only move the ring coronally, never further down the
  root. 20 of 28 cervical scallops got smaller.
- **The pulp chambers are no longer hollow.** Every machine-segmented pulp was
  carrying roughly half the chamber it should — the operator's finding, by eye,
  before any metric caught it. One growth threshold cannot serve both regions:
  the chamber is a large confidently dark body with nowhere to leak, while a
  canal one or two voxels across bleeds into the dentin around it. The threshold
  is now split at each tooth's own measured cervical ring. On a held-out tooth
  this recovers 78% of the operator's traced chamber volume, against roughly a
  third before.
- **Every upper molar now reaches its palatal canal.** Teeth 2, 3, 14 and 15 each
  missed that canal by 5.5–6.3 mm at any threshold, because every pulp training
  label was mandibular and the model had never seen a palatal root. One corrected
  maxillary molar fixed all four; every canal in the set now lands within 0.23 mm
  of its measured foramen.
- **Tooth 31's pulp is a quarter smaller, and 18 and 3 are new tracings.**
  Retraced 2026-09-04 → 2026-09-05, 97.82 → 72.08 mm³. What came off had a median
  intensity of 1121 against 621 for what stayed: it was dentin that had been
  called pulp. Teeth 18 and 31 — contralateral second molars, independently
  traced — now agree to 10%, against 34% before.
- **Tooth 31 has one canal in its distal root.** The previous model showed two,
  which was a defect and not anatomy; the record had it filed as an open question
  about the tooth rather than a fault in the model.

### Fixed

- **Every machine-segmented pulp was shipping with holes in it.** A mask cropped
  tight to its tooth reaches the edge of its own array, and marching cubes cannot
  close a surface there, so all twelve predicted pulps carried a rim of open
  boundary edges. Triangle counts and component counts both read normal, so
  nothing reported it. The mesher now pads before meshing.
- Teeth 3 and 18 were named in both the hand-traced and the machine-predicted
  provenance lists. The predicted block is spread last, so for two teeth the
  atlas credited a classifier for work the operator did by hand. Nothing failed
  and nothing rendered differently; it was simply wrong about its own sources.

## [0.6.0] — 2026-09-04

The atlas gets a circulation. Sixteen vessel meshes across both arches, every
tooth supplied and drained, and a second ontology because the first one does not
name veins.

### Added

- **Arteries and veins, 17 structures in one `Arteries & veins` layer.**
  Inferior alveolar, mental, incisive, infraorbital, posterior and anterior
  superior alveolar, greater palatine, and the dental branches and tributaries
  of each — 8 complete neurovascular bundles, each with an artery, a vein and a
  nerve. Red arteries and blue veins share one toggle — the colour is carried
  per structure, because nobody wants to switch on arteries and veins separately
  to look at a bundle.
- **Every tooth in both arches now has an arterial supply and a venous
  drainage**, drawn to the same measured apical foramina the nerve branches use.
- **The greater palatine artery**, the one vessel here that runs OUTSIDE the
  bone — forward in its groove on the palate, under the mucosa. Its course is
  found by casting up onto this patient's own palatal vault at each station and
  taking the lateral gutter, so the vessel is schematic but its shape is
  measured.
- **Cross-sectional shape in the traced canal files.** `semi_major_mm`,
  `semi_minor_mm` and `major_axis_lps` per sample in
  `docs/cbct-infraorbital.json` and `docs/cbct-mental.json`.
- **The greater palatine nerve and vein**, on the same measured palatal course
  as the artery — a groove carries a bundle.
- **The mental vein**, leaving the measured foramen with its nerve and artery.
- **Three build checks.** `tools/version.test.mjs` fails when package.json, the
  README and this file disagree about the release. `tools/ontology.test.mjs`
  resolves every FMA and TAH id against a vendored snapshot of the ontologies'
  own labels and fails when a structure carrying a bare id shares no word with
  it. `tools/bundle.test.mjs` fails when an artery, vein or nerve is added
  without its counterparts — the failure is otherwise silent, because an absent
  vessel looks exactly like one you have not switched on.

### Fixed

- **Two FMA ids named the wrong organs, in every release since 0.1.0.**
  `FMA53381` — the inferior alveolar nerve and its two derived meshes — is the
  occipital part of the aponeurosis of epicranius. `FMA53088` — the superior
  dental plexus and its two — is the lateral wall of the right orbit. They are
  now `FMA53243` and `FMA77528`. The teeth and everything tooth-adjacent were
  correct: 40 of 42 ids resolved cleanly.
- **The infraorbital nerve was thickest where it should be thinnest.**
  `IO_RADIUS_MM` is written posterior-to-foramen but was applied down a course
  ordered anterior-first, putting the 1.05 mm end at the foramen. It now tapers
  to 0.80 mm as it emerges. The centreline is unchanged.
- **The README said v0.4.0 through the whole of 0.5.0.** Now checked.
- **The superior alveolar trunk mesh was stale.** It could not be reproduced
  from any input combination and sat 0.613 mm off its own siblings, having been
  built from an earlier code state and never regenerated. The whole maxillary
  set — plexus, branches, trunks and the infraorbital nerve — is now built from
  one input pair, which is also the pair the teeth come from. `nerve_maxilla.py`
  and `vessels.py` now record their inputs in their JSON output, so this cannot
  go quiet again.

### Changed

- **Gingiva and periodontal ligament are on at full opacity by default**, with
  teeth, mandible, maxilla and palate. Nerves and vessels stay off — they are
  interior structures and showing them on load reveals nothing until the teeth
  are faded back.
- **Mid-face and ramus are off by default.** They are excluded from centring
  because they reach far beyond the teeth, and that same reach is what makes
  them wrong on load: they frame the dentition inside a slab of skull and ramus
  that is not what this atlas is about. They remain in the model, with a toggle,
  because they are measured.
- **Veins are named by the IFAA's Terminologia Anatomica Humana**, not the FMA,
  which has 3,741 vein terms and none for the inferior alveolar, infraorbital or
  dental veins. TAH cross-references FMA where both exist, so the two namespaces
  agree rather than compete. The join-key field is still called `fma` and now
  holds TAH ids too; renaming it touches every consumer at once and is deferred.

### Provenance

- Every vessel is `derived` or `schematic`, never `measured`. The canals and the
  apical foramina were measured; their contents were not, at any calibre, so
  every radius and offset is a choice and says so.
- **No vessel travels through dentin.** All 78 courses are routed against the
  tooth labels and confined to measured bone — except the greater palatine
  artery, which belongs outside it. Two courses graze a palatal root by 0.14 mm,
  which is less than the 0.16 mm voxel and so finer than the tooth boundary is
  known; that is reported rather than tuned away.
- The arrangement inside the mandibular canal — vessels superior to the nerve,
  artery lingual to the vein — is sourced. The site-dependent rotation the same
  series report is not modelled, and the provenance says so.

## [0.5.0] — 2026-09-03

The release where the atlas gained its own tracing tool, and where a machine
started doing some of the tracing.


### Added
- **The atlas has its own slice viewer, and it is why the pulp changed.** Every
  tracing in this project until now was marked on static contact sheets — a grid
  of PNGs — because a sheet was what the importer could read. That cost real
  accuracy: the pulp's first automated round scored a leave-one-out Dice of
  0.076 on 1.6 mm sections, and the mental canal needed two rounds. The operator
  named the problem exactly: *"it's hard for me to orient the anatomy if I'm not
  able to slice through actively myself."*

  `tools/cbct/slicer.py` is a localhost server and a page — three linked planes,
  scrub, window, paint, save — that writes exactly what the old importer wrote,
  one boolean mask per structure on the volume's own grid, so everything
  downstream reads it unchanged. It adds nothing between the brush and the file:
  no smoothing, no interpolation, no closing. If a tracing is wrong afterwards,
  the tracing is what changes.

  It is **tooling rather than part of the deployed atlas** — nothing in the app
  links to it — but it is recorded here rather than buried, for two reasons. It
  is the reason two molars could be traced slice by slice, 120 and 103 sections
  each, and those two tracings are what the fourteen machine-made pulps below
  were learned from. And it is reusable: the viewer and the classifier that
  learns from it (`tools/cbct/pulp_learn.py`) are MIT-licensed like the rest of
  the code, depend on nothing in this dataset, and take any NRRD volume. The
  imaging under `assets/cbct/` carries no such grant and is not part of that.

- **Every molar and premolar pulp remade, and 14 of the 16 are machine-made.**
  The operator hand-traced two lower molars in the new slice viewer — every
  slice painted, 120 and 103 of them, against the eleven axial sections the
  atlas's original pulp was built from. A classifier trained on those two then
  predicted the other fourteen, with each canal routed to that tooth's own
  measured apical foramen.

  Pulp volume rose from 36.8 mm³ to 78.1 mm³ on average across these sixteen
  teeth — the old sparse tracing was missing more than half of it. On a
  tooth it had never seen the model scores Dice 0.470 against that tooth's older
  hand-trace — read against 0.563, which is what two careful human tracings of
  the same tooth score against each other. Seven of the eight contralateral
  pairs agree to within 16%.

  Three physical rules are enforced afterwards: the pulp is clipped to its own
  tooth, its radius is capped by an envelope tapering to 0.16 mm at each measured
  foramen, and it is reduced to a single connected body. Before them, 172 mm³ of
  predicted pulp lay outside its tooth and the apical canals were two to three
  times wider than a real foramen.

  **They are `measured`.** Every other machine segmentation in this atlas is —
  the teeth, the mandible and the maxilla all came out of a neural network — and
  the tier records that the scan decided it, not which algorithm read the scan.
  What each one's method does record is that **fourteen of them have not yet been
  reviewed by eye**, and that tooth 18 differs from its traced counterpart by
  32% and is the one to check first.

- **The infraorbital nerve now has its terminal branches into the face.** It
  reached its foramen and stopped, which said nothing about what the nerve is
  for: everything a patient feels in the lower eyelid, the side of the nose and
  the upper lip arrives through these. Eighteen branches in four named groups —
  inferior palpebral, external nasal, internal nasal and superior labial, as
  Gray's names and counts them — each dividing once more near its end.

  **Both ends are measured on this patient.** The foramen and the direction the
  nerve leaves it come from the operator's tracing of the canal. The far end
  comes from his skin: CBCT has poor soft-tissue *contrast* but an excellent
  air/tissue *boundary*, so every branch is run out until it reaches the face
  and stopped 1.2 mm short of it, in the dermis. No branch has a length chosen
  by hand — the shortest is 12.6 mm and the longest 33.0 mm because that is
  where his face is. The foramen itself sits 11.2 mm deep on the right and
  9.6 mm on the left, measured the same way.

  They are `derived`, the same standing as the dental branches: measured
  endpoints, and a path between them that is convention. Three invariants fail
  the build rather than shipping — no branch may re-enter bone, none may end
  anywhere but the outside of the face, and none may cross the dental midline.
  All three caught real errors while this was being built.

  **The mental nerve has the same fan**, six branches a side: two to the skin of
  the chin, two to the lower lip, and two **gingival** branches to the labial
  gingiva of the anterior mandible — the group a mental block is actually aimed
  at, and the one a purely cutaneous account of this nerve leaves out. It hangs
  off a mental canal the operator hand-traced over two rounds, and on a foramen
  found where that canal comes closest to the buccal plate rather than at the
  end of the tracing — the mandibular canal runs on past its own foramen as the
  incisive canal, so the end of a tracing is not the exit. The two foramina come
  out 0.6 mm apart in height and 23.6 and 21.8 mm from the dental midline. `nerve.py` now reads the same file, so the trunk and its facial
  branches leave the bone at one point rather than two 3 mm apart.

  **What is drawn is a stub.** Each branch's termination on the skin was
  measured, and every one is recorded in `docs/cbct-nerve-face.json` — but the
  face they end on is not rendered, so a branch drawn to its full 12–33 mm ends
  in mid-air and reads as a wire rather than as anatomy. They are drawn 5.0 to
  7.5 mm by group, enough to show which way each one goes. The heading is
  measured; the drawn length is a placeholder, and lifting it is one constant
  once there is a surface to land on.

### Fixed
- **No two teeth overlap. Not "less"; none.** Measured by exact voxel
  intersection on all 26 contacts: **4.80 mm³ before, 0.0000 mm³ now**, with the
  crowns clearing each other by 40–203 µm, median 87 — about half a voxel at the
  median and never more than 1.3, so nothing is being claimed that the scan did
  not resolve, and it is invisible at any zoom the viewer allows.

  Two causes, both fixed. The segmentation infers at 0.43 mm, so two crowns in
  contact are a voxel apart and the label BRIDGES them wider than either crown;
  the arch split then divided the bridge, leaving every tooth a lens about 3 mm
  across on its proximal surface and a matching notch where its neighbour's did
  the same. That is trimmed at the label, so the notch goes with the lens, and
  the trim radius is chosen per tooth — a single radius cleared the molars and
  took 8.5% off a lower central incisor.

  **The arch split itself was re-cut**, which is where the proximal nubs came
  from: the contact cut paid least to travel through enamel, so a tooth's
  boundary could run around the OUTSIDE of its neighbour's enamel rim rather
  than through the contact between them, leaving one tooth wearing a rind of the
  other. It now also pays for travelling near a surface, and no voxel may be
  kept by a tooth whose neighbour's core is nearer in a straight line. The
  landmarks, crest, periodontal ligament, gingiva and every pulp were rebuilt on
  the new labels. The nubs are much reduced; they are not entirely gone.

  The rest was the mesher. Each tooth's surface is found from the grey levels,
  independently, so two neighbours could each place their surface a little
  inside the other. Within half a millimetre of a neighbour the segmentation
  now decides the boundary alone, so both teeth read the same one, and each
  stops 40 µm short of it.

- **The pulp is no longer faceted.** The smoothing was tuned for hand-traced
  masks, which are coherent from slice to slice because a person drew them that
  way; a predicted mask carries a step wherever the model changed its mind, and
  the old setting left those visible as jagged canals.

- **Teeth were shipping in pieces.** 23 of the 28 carried a detached second
  lump — about 25 mm³ on each molar and 1–12 mm³ on the premolars. The
  segmentation was never at fault: every
  tooth's mask is a single connected region. The mesher was. It takes each
  tooth's surface from the grey levels rather than from the mask, which is what
  gives the surface its sub-voxel accuracy, and the same isosurface closes a
  second shell around the pulp chamber, since the pulp is not part of the tooth
  label. Two teeth were worse and that was recent: claiming the zirconia halo
  for the crowned molars had left teeth 20 and 29 in 27 and 23 pieces.

  A tooth is one solid, so its surface is one shell. It now is, on all 28, and
  **the build fails if it ever isn't again** — the fourth such check, alongside
  laterality, tooth identity and provenance.

- **The `Mid-face` and `Ramus & inferior border` opacity sliders did nothing
  useful.** Both layers were added in 0.4.0 without an entry in the appearance
  table, and glTF's default for a mesh with no material is white, fully
  METALLIC and single-sided. A rough metal under this lighting happens to look
  like pale bone, so at full opacity nobody noticed; a metal has no diffuse
  term, so the moment either slider moved the layer turned to grey smoke
  instead of translucent bone. Both now carry the same appearance as the
  `Maxilla` and `Mandible` layers they are the same tissue as, and a layer with
  no appearance now fails the build instead of inheriting glTF's default.

- **`export_teeth.py` no longer reports a false laterality failure.** It tested
  whether a tooth sat left of the SCANNER's origin; the arch sits 3.6 mm to the
  operator's left of it, which is head position rather than anatomy. The lower
  right central incisor, which straddles the midline, was reported as being on
  the wrong side while sitting a healthy 3.3 mm on its correct one. It now
  measures against the dental midline, as `build-assets.mjs` always has, and
  fails the run rather than printing a warning.

### Known, not fixed
- **Every posterior contact is bridged in the segmentation.** Isolate an upper
  premolar or molar and there is a rounded lump on its proximal surface; its
  neighbour has a matching one in the same place. That is what the two teeth
  appear to share. It is in the segmentation mask, not in the meshing:
  DentalSegmentator infers at 0.43 mm, two enamel surfaces in contact are one
  voxel apart, and the label bridges them wider than either crown. The arch
  split then divides the bridge between the two teeth instead of removing it.

  **The lump and the contact are the same tissue**, which is the thing that
  makes this unfixable here rather than merely unfixed. Three measurements say
  so. The material a trim removes lies 3.2–4.0 mm below the occlusal end and the
  contacts themselves lie at 2.9–5.6 mm — one band, with no level at which the
  artefact can be cut and the contact spared. Giving a pair its contact back
  after trimming restores the lump exactly, as a peg. And a trim aggressive
  enough to remove it opens every interproximal contact in the mouth from 80 µm
  to 1.68 mm, which is a worse and far more obvious defect.

  It also is not a mislabelling: flooding each tooth from its own core through
  dense tissue leaves nothing unreachable on any of the 28, so the lump really
  does belong to the tooth it is drawn on.

  So the teeth genuinely touch, there is no gap to find at any threshold, and
  shaping the proximal contour by hand would be inventing it. The intraoral
  scan measures the crown surface directly and is what will settle this.

### Changed
- **Every inter-tooth boundary re-cut.** The arch split ended each tooth at its
  contacts by growing eroded seeds under a distance watershed, which has no
  minimum to settle into where two crowns actually touch — so the boundary
  landed as a near-planar chord, sometimes well inside the crown. All 26
  contacts fitted a plane to better than 0.26 mm RMS. They are now cut pairwise
  under an additive cost metric that is cheap through bright tissue and
  expensive through dark, so the boundary follows the interproximal embrasure
  where one is open and degrades to the midsurface between the two tooth bodies
  where none is. Contralateral volume asymmetry improved on 11 of 14 pairs.

  Nothing was lost from the mouth before or after — the wedge cut off one tooth
  was always labelled as its neighbour — so this is a change to the 28 per-tooth
  shapes, not to the assembled dentition. Tooth volumes moved by up to 10.9%
  (tooth 12), and both canines gave proximal tissue back to both first premolars.

- **Restoration-density voxels now belong to the crowned tooth.** The zirconia
  on 19 and 30 saturates this scan, and its halo was being divided between the
  crowned tooth and its neighbour: teeth 20 and 29 each carried about 1% of
  voxels at a density no natural tooth in this mouth reaches. Those are claimed
  by the tooth the crown is cemented onto rather than split.

- **Periodontal ligament and gingiva rebuilt** on the new tooth surfaces, since
  both are lofted from per-tooth measurements. The pulp is unchanged: it is
  hand-traced in volume space, and it still lies entirely inside its own tooth
  under the new masks — 0.00 mm³ outside, all 28.

- **The infraorbital nerve now follows a measured canal.** It was `schematic`:
  a constructed arc placed a fixed 22 mm above the tooth apices, on the recorded
  grounds that "the infraorbital canal does not resolve at 0.16 mm". That was
  wrong — the canal is visible, and five automatic detectors failed to find it
  for five different reasons, none of them the anatomy. It has been hand-traced
  on cross-sections cut perpendicular to its own axis at 1 mm intervals, in the
  maxillary exposure, whose reconstruction covers this region where the centred
  volume's stops 0.6 mm short of the canal's posterior end.

  The nerve is now **`derived`**: it follows the measured centreline, but what is
  drawn is a tube of chosen calibre on it, exactly as for the inferior alveolar
  nerve — the canal carries the nerve, artery and vein together, so the lumen is
  wider than the nerve. The drawn surface lies a median 0.16 mm from the traced
  lumen. Both canals were traced independently and came out within 5% of each
  other by volume (65.9 and 69.6 mm3).

  **The infraorbital nerve is now its own structure** (`FMA52978`), split from
  what was "Infraorbital, PSA, MSA and ASA nerves". One mesh can carry only one
  provenance tier, and PSA, MSA and ASA remain textbook courses. Where MSA and
  ASA leave the trunk is now placed by arc length along the measured canal, so
  their origins sit on measured geometry even though their courses do not.

## [0.4.0] — 2026-09-01

### Added
- **All three CBCT exposures now contribute geometry.** Until now only the
  centred volume did, while the two focused scans — acquired, surveyed and then
  used for nothing — each see substantially more of the structure they are aimed
  at. Both are rigidly registered into the atlas frame on the label they are
  fitted to, and clipped to the bone the centred volume never covered:

  | | centred | focused | new bone |
  |---|---|---|---|
  | Upper skull | 31.3 cm3 | 54.0 cm3 (maxillary) | **23.0 cm3** |
  | Mandible | 21.6 cm3 | 32.1 cm3 (mandibular) | **12.0 cm3** |

  The atlas now spans 75 mm above the occlusal plane where it stopped at 37, and
  61 mm below where it stopped at 44. The mandible's rami, cut through by the
  centred field of view (172 mm2 and 191 mm2 of flat cap on its side walls), are
  no longer truncated.

  Each registration is validated on a label **held out of its own fit** — the
  upper teeth for the maxillary transform, which land at Dice 0.708 against a
  ceiling of 0.728 having never been seen by the optimiser.
- **`Mid-face` and `Ramus & inferior border` layers**, one per focused exposure,
  toggleable separately because each is a different acquisition. Both are
  excluded from the model's centring: they are real anatomy, but letting them
  decide the framing pulls the camera off the teeth.
- **The maxillary nerve trunks are confined to measured bone**, and re-derived
  against Malamed's *Handbook of Local Anesthesia* rather than against the
  Wikipedia articles. They had never been tested against bone: 72% of that mesh
  lay outside it, a median of 3.5 mm and as much as 10.1 mm out, floating in the
  sinus. It is now 0.5 mm median and 1.2 mm maximum — the tube's own radius. The
  test only became meaningful once the maxillary exposure supplied enough
  mid-face to test against. The tier stays `schematic`, because bounded by
  measured bone is not the same as seen in it.
- **The version is shown in the app**, bottom right opposite the credits, and
  links to this file. It is stamped from `package.json` at build time so the
  label and the changelog cannot drift apart.

### Changed
- **`Maxilla and palate` now carries the whole upper skull the centred volume
  measured**, not a crop of it. It had been cut to within 22 mm of the upper
  teeth, discarding 3.6 cm3 of labelled bone — the posterior mid-face and
  pterygoid region, and the infraorbital rim and zygomatic process on both
  sides. That is the bone the maxillary nerves were being drawn beside with
  nothing there. Its boundary is now where the segmentation stops, not where an
  export crop did.

## [0.3.0] — 2026-08-31

The release that made the atlas say where every structure comes from, and
removed the last third-party geometry.

### Added
- **Provenance on every structure**, shown in the detail panel at the point of
  selection: a tier (`measured` / `derived` / `schematic`), the method, and a
  citation where anything is approximated. 58 measured, 32 derived, 4 schematic.
  The build now fails if any structure lacks one.
- **Tooth-identity verification.** Tooth numbering is checked against tooth
  morphology on every build — arch order, molar size and root count, canine
  length — so a mislabelled tooth fails the build rather than shipping. This
  closed the long-standing question of whether the Universal → FMA mapping was
  correct: it is, on all 28 teeth.
- **Field-of-view audit** (`npm run audit:fov`) recording where the measured
  data stops and what the scan never saw.

### Changed
- **BodyParts3D is gone.** Every mesh it supplied had already been replaced by
  measured anatomy, so its source tree, the fetch tooling and the tooth-source
  switch were removed. The atlas is now one model built from one dataset.
- **Licensing follows.** With those meshes went the CC BY-SA 2.1 JP ShareAlike
  obligation they carried. Code is MIT; the anatomy is a named living person's
  medical imaging published with consent and under no reuse grant.
- Long citations wrap in the detail panel instead of scrolling it sideways.
- The `(schematic)` suffixes on structure names are gone — the provenance tier
  carries that distinction now, and the build enforces it.

## [0.2.0] — 2026-08-30

The release where the atlas became this patient's anatomy rather than a generic
model.

### Added
- **28 teeth segmented from the operator's own CBCT** at 0.16 mm, replacing the
  alpha's generic hard tissue.
- **Pulp for all 28 teeth**, hand-traced by the operator across three rounds
  after automatic segmentation could not separate pulp from dentin at any
  threshold on this scan. 723 mm³, every tooth a single connected component.
- **Inferior alveolar nerve** following the measured mandibular canal, with the
  mental and incisive branches, plus a schematic superior alveolar plexus in
  the maxilla. Nerve tissue renders yellow.
- **Gingiva** as a collar lofted from the measured cementoenamel junction, with
  papillae emerging from the interproximal scallop.
- **Periodontal ligament space** built from two measured walls.
- A source-data caveat in the interface, since a tool that looks like a clinical
  reference must say what it omits.

### Fixed
- Teeth are cut apart at their **contacts** rather than on sector planes.
- Bone and neighbouring teeth are kept out of each tooth's surface.
- The deploy no longer publishes a different model from the one reviewed
  locally — there is one model now.

## [0.1.0] — 2026-08-27

Alpha. Interactive 3D atlas of oral anatomy: Vite and Three.js, no framework.

### Added
- 28 permanent teeth, jaws, gingiva and muscles of mastication.
- Click selection, an odontogram with camera flight to the selected tooth,
  per-layer opacity, isolate, and offline install as a PWA.
- Universal, FDI and Palmer notation, derived from arch, side and position
  rather than hand-entered.
- A laterality assertion in the build: anatomical right is negative x, and the
  build fails if any structure labelled left or right sits on the wrong side.

[Unreleased]: https://github.com/NateSaindon/3Dentes/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/NateSaindon/3Dentes/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/NateSaindon/3Dentes/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/NateSaindon/3Dentes/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/NateSaindon/3Dentes/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/NateSaindon/3Dentes/releases/tag/v0.1.0
