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

## [Unreleased]

Nothing published since 0.4.0.

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

[Unreleased]: https://github.com/NateSaindon/3Dentes/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/NateSaindon/3Dentes/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/NateSaindon/3Dentes/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/NateSaindon/3Dentes/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/NateSaindon/3Dentes/releases/tag/v0.1.0
