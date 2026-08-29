# Notes for Claude Code — 3Dentes

Interactive 3D atlas of human oral anatomy. Vite + Three.js, no framework.
Deploys to https://natesaindon.github.io/3Dentes/ from `main` via Actions.

**This repo is public**, and as of 2026-08-29 that includes the operator's own
CBCT-derived anatomy — they have explicitly consented to it. See "Next on the
docket" below. This is not a general licence: no third-party patient data, ever.

## Machines

- **Arch ThinkPad** — where the alpha was built. Fine for app work.
- **Fedora Workstation desktop** — where Phase 2 modelling happens (GPU headroom,
  real mouse). Blender is **not installed there yet**; install when that work
  actually starts, not before.

## Commands

```bash
npm install
npm run fetch:assets   # re-download source STLs + rewrite provenance (rarely needed)
npm run build:assets   # STL -> public/dentition.glb + public/teeth.json
npm run dev            # http://localhost:5173/3Dentes/
npm run dev -- --host  # reachable from the iPad on the same network
npm run build && npm run preview
```

`public/dentition.glb` and `public/teeth.json` are gitignored build products.
Run `build:assets` after cloning or nothing loads.

## Invariants — do not break these

1. **The laterality assertion in `tools/build-assets.mjs`.** Anatomical right is
   negative x. The build fails if any structure labelled left/right sits on the
   wrong side. An atlas that confidently mislabels a side is worse than no atlas.
   If it ever fires, the model is mirrored — fix the pipeline, don't relax the check.
2. **Exact vertex welding.** `weldExact` merges only bitwise-identical vertices.
   Never add a distance tolerance: it would round off cusp tips and occlusal
   fissures, which is precisely the anatomy that matters here.
3. **The dual license split.** Code MIT; anything under `assets/` (and
   `dentition.glb` built from it) is CC BY-SA 2.1 JP from BodyParts3D.
   ShareAlike is inherited by *anything derived from those meshes*, including
   Blender edits. Anatomy authored from scratch is a separate work — keep the two
   physically separate in the tree.
4. **The source-data caveat stays visible in the UI.** The `.caveat` block in
   `index.html`. The user is a dental professional; a tool that looks like a
   clinical reference while omitting pulp and the inferior alveolar nerve must say so.

## Architecture

FMA ids are the join key everywhere — source filename, glTF node name, and
`teeth.json` key are all e.g. `FMA55697`.

`tools/manifest.mjs` is the single source of truth: which structures, their
layer, anatomical side, and the notation derivation. Universal/FDI/Palmer are
**derived** from arch/side/position, never hand-typed — 28 hand-entered tooth
numbers is 28 chances to mislabel a tooth.

Gotchas worth not rediscovering are in the README's "Notes from building it"
(flat-vs-smooth normals, 16-bit indices, see-through picking).

## Status

**Alpha: done and deployed** (2026-08-27). 28 permanent teeth, jaws, gingiva,
muscles of mastication; click selection, odontogram with camera flight, layer
opacity, isolate, PWA offline install.

### Open item

The **Universal → FMA mapping** in `tools/manifest.mjs` is derived and
self-consistent, and was cross-checked against an independently written table —
but consistency is not correctness. The user intends to review it. If they raise
a mislabelled tooth, that's the likely source.

### Next on the docket — CBCT

The plan is to replace BodyParts3D hard tissue with segmented CBCT the user
supplies. This is the main Phase 2 thrust and supersedes several options in
`docs/phase-2-options.md`. **Read [docs/cbct-plan.md](docs/cbct-plan.md) before
starting** — it is authoritative for the dataset, the registration strategy, the
artifact map and the first-session steps.

The four things from it that matter most:

- **There are three volumes, not one** — central, mandible-focused,
  maxilla-focused — and they are **three separate exposures**. They do not share
  a coordinate frame, and the mandible moved between them.
- **Register in voxel space, fuse in mesh space.** CBCT gray values aren't
  calibrated HU, so a spliced volume has two intensity regimes and no threshold
  works across the seam. Two masked rigid transforms onto the central volume;
  segment each arch in its native grid; composite the meshes, not the voxels.
- **The laterality assertion does not protect against a globally mirrored
  volume** — it only catches a label on the wrong side. With bilateral crowns on
  19 and 30 and no third molars, there is no asymmetric landmark to fall back on.
  Derive L/R from `ImageOrientationPatient` (DICOM LPS: anatomical right is
  negative x, matching the atlas convention) and confirm with the user.
- **Do not run the vendor `.exe`** that ships alongside the imaging data. It's a
  Windows viewer, irrelevant on Fedora, and unnecessary — DICOM is an open standard.

The privacy question that used to gate this work is **settled: public is
approved.** De-identify headers anyway.

### CBCT: where things actually stand (2026-08-29)

The USB has been surveyed and a pilot tooth segmented. **Two documents now sit
between you and `cbct-plan.md`, and they win where they disagree with it:**

- **[docs/cbct-survey.md](docs/cbct-survey.md)** — what is really on the disc.
  Read it before touching the data. Four of the plan's premises were wrong:
  all three volumes are the *same* 0.16 mm isotropic resolution and FOV (not
  focused, higher-res); the **maxillary volume truncates the upper crowns** and
  is a sinus/root volume, not an upper-arch source; **`centered` is the only
  volume with both complete arches** and should be the primary segmentation
  source, not just the registration anchor; and it was acquired **2025-06-27**,
  fourteen months before the other two.
- **[docs/cbct-pilot.md](docs/cbct-pilot.md)** — tooth 9 segmented end to end,
  what worked, and two traps that cost real time (see below).

**Laterality is resolved.** The operator confirms the septum deviates right,
matching the headers' LPS reading. The volumes are not mirrored.

Working data is in `~/projects/3Dentes-cbct/` and is **not** committed — see the
`.gitignore` note. Regenerate with `tools/cbct/prepare.py`.

Three things worth not rediscovering:

1. **A tooth cannot be thresholded out of its socket.** Root dentin and alveolar
   bone overlap in density and neighbours touch at their contacts. Use the
   marker-based watershed in `tools/cbct/segment_tooth.py`, and seed **bone** as
   its own basin or the result leaks up the socket.
2. **The watershed basin has the pulp cut out of it**, and 3D `fill_holes` will
   not close it, because the canal opens at the apical foramen. Fill **per axial
   slice**. Any analysis of interior anatomy against an unfilled mask will
   confidently report that the canal does not exist. It does.
3. **Mesh from grey levels, not the binary mask.** Marching cubes on a mask
   terraces at 0.16 mm however much you smooth it.
4. **The pulp cannot be thresholded at all**, at any setting — below ~3 voxels
   wide, partial volume means no voxel ever reaches pulp density. Measure the
   lumen by integrating the intensity deficit across each cross-section, which
   survives sub-resolution blurring. `tools/cbct/pulp_model.py` does this and
   recovers tooth 9's canal at 20.4 mm³ with a 0.33 mm apical foramen. Do not
   "fix" it back into a threshold.

### Whole-mouth pipeline (2026-08-29)

**[docs/cbct-whole-mouth.md](docs/cbct-whole-mouth.md)** supersedes the
hand-seeded per-tooth approach. DentalSegmentator runs standalone (no Slicer) in
8 s on the GPU and gives all 28 teeth plus the mandibular canal; the arch is
split by dynamic programming over arc length against a tooth-width prior; pulp is
modelled per canal by intensity-deficit integration. Both arch maps are
operator-verified.

Four things worth not rediscovering:

4. **DentalSegmentator is per-CLASS, not per-instance** — "Upper Teeth" is one
   label. Its masks are already *solid* (pulp inside), so they need no per-slice
   fill.
5. **Do not split the arch by 3D shape.** A distance-transform watershed peaks
   per cusp and per root, not per tooth. Teeth are sequential *along the arch*;
   split by arc position.
6. **When capping a count by an anatomical prior, fold the surplus in, never
   drop it.** Dropping surplus canal tracks cost tooth 9 a third of its pulp.
7. **The pulp count is a prior; the volume is a measurement.** An extra canal
   will be neither found nor flagged.

Node is **not installed** on the Fedora box: `sudo dnf install -y nodejs24
nodejs24-npm`. Python side is `python3-pydicom python3-numpy python3-gdcm
python3-scipy python3-scikit-image dcm2niix dcmtk`.
