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
