# 3Dentes

Interactive 3D atlas of human oral anatomy, in the browser. One codebase runs on
Linux, macOS, Windows and iPad — install it to the home screen and it works
offline.

**Live: https://natesaindon.github.io/3Dentes/**

![3Dentes](docs/screenshot.png)

## What it does

- **28 individually selectable permanent teeth**, plus mandible, maxillae,
  palatine bones, upper and lower gingiva, and the muscles of mastication
  (masseter superficial and deep, medial and lateral pterygoid).
- **Clinical notation** — every tooth labelled in Universal, FDI and Palmer, all
  derived from arch/side/position rather than hand-entered.
- **Odontogram** in the standard clinical layout (upper arch on top, patient's
  right on the viewer's left), synced both ways with the 3D view. Selecting a
  tooth on the chart flies the camera to it, approaching from outside the arch
  so the tooth is actually exposed — near-frontal for an incisor, swinging
  buccal for a molar. This is how you reach the posterior teeth, since from a
  frontal view a molar really is hidden behind the premolars in front of it.
- **Layer visibility and opacity**, so you can fade the gingiva and alveolar bone
  back to expose the roots in situ, or isolate a single structure.

## What it is not

The geometry comes from BodyParts3D, which is external morphology of a single
individual. It does **not** contain:

- third molars (28 teeth, not 32)
- enamel, dentin or pulp — no internal tooth structure
- nerves (inferior alveolar, lingual, mental)
- periodontal ligament, tongue, TMJ disc, or salivary glands

Root count and curvature are that one person's, not a textbook composite. This
is a study and visualisation aid, **not a complete clinical reference**. The app
states this on screen; please keep it that way in any fork.

Closing those gaps is the Phase 2 work — see [docs/phase-2-options.md](docs/phase-2-options.md).

## Running it

```bash
npm install
npm run build:assets   # STL -> public/dentition.glb + public/teeth.json
npm run dev            # http://localhost:5173/3Dentes/
```

The source STLs are vendored in `assets/source/stl/`, so `build:assets` works
offline. `npm run fetch:assets` re-downloads them from BodyParts3D and rewrites
`assets/source/provenance.json`; re-running it against an unchanged upstream
should leave `git diff` empty.

To reach the dev server from an iPad on the same network, `npm run dev -- --host`.

## How it fits together

```
tools/manifest.mjs      which structures to use, their layer, anatomical side,
                        and the notation derivation (single source of truth)
tools/fetch-assets.mjs  reproducible download + provenance/checksums
tools/build-assets.mjs  STL -> welded, smooth-shaded, y-up, centred .glb
src/scene.js            renderer, lighting, camera, camera flights
src/picking.js          raycast selection, drag-vs-click, see-through handling
src/odontogram.js       the tooth chart
src/ui.js               layer, notation and detail panels
src/main.js             wiring and selection state
```

FMA identifiers are the join key throughout: a structure is `FMA55697`
everywhere — the source filename, the glTF node name, and the key in
`teeth.json`.

### Notes from building it

A few things that were not obvious and are easy to regress:

- **Binary STL is a triangle soup** with no shared vertices and no vertex
  normals. Converting it naively gives ~1M vertices and hard faceted shading.
  Welding bitwise-identical vertices recovers the original topology exactly
  (1,043,478 → 173,956 vertices, 83% fewer) because these STLs came from an OBJ
  whose shared vertices have identical float bits. Welding with a *tolerance*
  would round off cusp tips and occlusal fissures, so it is deliberately exact.
- `@gltf-transform`'s `normals()` generates **flat** normals, not smooth ones,
  hence the hand-rolled area-weighted `computeSmoothNormals`.
- **Indices dominate the file.** At 32 bits they were larger than positions and
  normals combined; every structure welds to well under 65,536 vertices, so
  16-bit indices cut the build from 8.4MB to 6.3MB for free.
- **The build fails if the model is mirrored.** Anatomical right is negative x in
  this dataset; `checkLaterality` asserts every structure labelled left or right
  sits on the expected side. An atlas that confidently mislabels a side is worse
  than no atlas.
- **See-through structures don't absorb clicks.** With gingiva at its default
  45%, the teeth behind it are plainly visible, so a click there should select
  the tooth. Above 60% opacity a structure reads as solid and does take the
  click.

## Licensing

Two licenses, kept deliberately separate:

- **Code** (`src/`, `tools/`, `data/`) — MIT. See [LICENSE](LICENSE).
- **3D models** (`assets/`, and `public/dentition.glb` built from them) —
  CC BY-SA 2.1 Japan. See [LICENSE-ASSETS](LICENSE-ASSETS).

> BodyParts3D, © The Database Center for Life Science
> licensed under CC Attribution-Share Alike 2.1 Japan

ShareAlike is inherited by anything derived from those meshes, including models
edited in Blender. Anatomy authored from scratch is a separate work. Full detail
in [ATTRIBUTION.md](ATTRIBUTION.md).
