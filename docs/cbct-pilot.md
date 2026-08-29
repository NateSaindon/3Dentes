# CBCT pilot — tooth 9, end to end

2026-08-29, Fedora desktop. Executes plan steps 3, 4 and 7, and validates the
format half of step 8. **Step 6 (registration) was deliberately deferred** — see
below.

Read [cbct-survey.md](cbct-survey.md) first; it establishes the dataset facts
this pilot depends on.

## Laterality: resolved

The operator confirms **the nasal septum deviates to the right**, which matches
what the volumes show under the header's own LPS reading. The volumes are **not
mirrored**. Anatomical right is negative x, as `tools/build-assets.mjs` requires.
The trap flagged in the plan is closed.

## Why registration was deferred

The plan runs registration (step 6) before the pilot (step 7). Survey §03 changed
the reason for the ordering: the pilot has to come from `centered`, because it is
the only volume containing complete crowns — and `centered` is the frame
everything else registers *to*, so it needs no transform. Registration only earns
its keep when mandibular and maxillary geometry is composited in. Doing the pilot
first tests the whole extraction pipeline a day earlier and at lower cost.

## What now exists

Working data (**outside the repo**, see "Repository contents" below):

```
~/projects/3Dentes-cbct/
  usb-mirror/     5.4 GB   read-only mirror of NLSCBCT, chmod a-w
  nrrd/           551 MB   centered/mandibular/maxillary .nrrd + volumes.json
  pilot/          9.0 MB   FMA55682{,-enamel,-dentin,-pulp}.stl + tooth9.json
```

New tooling in the repo:

| File | Does |
| --- | --- |
| `tools/cbct/vol.py` | Loads the gzipped NRRDs; keeps (z,y,x) index order and (x,y,z) world order straight |
| `tools/cbct/prepare.py` | DICOM → de-identified NRRD, with geometry assertions |
| `tools/cbct/segment_tooth.py` | One tooth → enamel / dentin / pulp → binary STL in LPS mm |

### De-identification and conversion (steps 3–4)

`prepare.py` reads the `_3rdparty` export, checks geometry, and writes one
gzipped NRRD per volume. **No de-identified DICOM intermediate is produced** —
NRRD carries only the fields the script writes, none of which are identifiers, so
an intermediate would cost ~780 MB to hold data that gets converted again anyway.
The originals are never modified.

Values are stored as int16 Hounsfield-like units. That rounds away the
`_3rdparty` export's sub-HU precision, which is ~2 orders of magnitude below this
scanner's noise floor (σ ≈ 40–70 HU, measured). It is still the right source: the
12-bit exports *floor* rather than round, carrying a −0.5 HU bias.

Round-trip verified bit-exact against the DICOM for all three volumes.

## The pilot: tooth 9

Universal 9, maxillary left central incisor, `FMA55682`. Located by finding the
deepest interproximal minimum in the anterior enamel x-profile — the dental
midline, at x = +0.96 mm — and taking the segment immediately to the patient's
left. Confirmed against an axial render.

### Isolation is watershed, not thresholding

**A tooth cannot be thresholded out of its socket.** Root dentin and alveolar
bone overlap in density, and neighbouring teeth touch at their contacts. A plain
`> 1050 HU` mask plus connected components returns one 116,000-voxel blob
spanning the whole anterior segment.

What *does* separate them is darkness — the interproximal space and the
periodontal ligament, both 450–870 HU. So the segmentation is a marker-based
watershed on `-intensity`, seeded inside the target tooth, inside each
neighbour, in background, and **in bone**. The bone markers matter: without them
the basins split the alveolus between the teeth and the result leaks up the
socket, giving a 549 mm³ "tooth" whose bounding box overlaps its neighbour's.

### Reconstructing the tooth as a solid

The watershed basin is dentin and enamel only — the pulp is below the isolation
threshold, so it is a **void** in the basin. A 3D `fill_holes` does not close it:
the canal opens to the periapical space through the apical foramen, so the void
is not topologically enclosed. Filling **per axial slice** does close it, because
in an axial cut the canal is a ring of dentin, and it leaves the outer surface
untouched. A small 3D closing afterwards seals the slices where partial volume
breaks that ring.

> This cost an hour of wrong conclusions. Before the per-slice fill was added,
> every measurement of "is the canal resolved" was being run against a mask with
> the canal cut out of it, and reported that no central low-density structure
> existed. It does. Any future analysis that asks about interior anatomy must
> check that the mask is solid first.

### Meshing: grey levels, not the binary mask

Marching cubes on a binary mask can only place a vertex on a voxel boundary, so
its surface terraces at 0.16 mm no matter how much it is smoothed afterwards.
Running marching cubes on the **intensity field** (confined to a dilation of the
mask) puts the surface where the density boundary actually falls. The crown
surface goes from visibly stepped to smooth. This is the single biggest quality
win in the pilot and should be the default for every structure.

### Results

| Tissue | Volume | Triangles | Notes |
| --- | --- | --- | --- |
| Tooth (solid) | 466.0 mm³ | 54,480 | Outer surface. Typical central incisor 400–450 mm³ |
| Enamel | 140.3 mm³ | 43,510 | Coronal cap; Otsu split at 1607 HU |
| Dentin | 302.5 mm³ | 77,968 | |
| Pulp | 23.1 mm³ | 12,250 | **Provisional — see below** |

Morphometry sanity: 8.0 mm mesiodistal, 16.4 mm vertical, 18.2 mm along the long
axis, cross-section narrow at the incisal edge, widest at the cervix (54 mm²),
tapering smoothly to the apex. All consistent with a maxillary central incisor.

### Pulp is real, but the extraction is provisional

The cavity is unambiguously present and strongly contrasted — **714 HU inside
against 1481 HU in dentin**, roughly ten times the noise floor. This validates
the project's headline premise: real measured pulp anatomy is in this data.

The *extraction*, though, is not shippable. The canal wall is not consistently
above the isolation threshold, so the recovered space breaks into 5 components
and its cross-section varies more than real canal anatomy does (0.7–3.0 mm
equivalent diameter over adjacent levels). Nothing large is missing — the
unlabelled dark material inside the tooth totals 1.98 mm³ in 118 specks — but the
surface should not ship without review. `tooth9.json` carries this as a `qc`
block.

**This is the strongest argument yet for evaluating DentalSegmentator**, which
the plan already flags. Per-tooth instance masks from a trained model would
remove exactly the fragile step here.

### The apical third is rough

The crown surface is clean. The apical third is spiky, because that is where the
PDL stops being resolved and the tooth–bone boundary genuinely becomes ambiguous
in the data. This is a limit of the imaging, not of the code, and it will affect
every tooth. Expect to either accept it, smooth it, or clip the apices.

## Step 8: format compatibility confirmed

All four STLs parse under the exact header/size logic in
`tools/build-assets.mjs`, and all sit at **positive x — anatomical left**, correct
for tooth 9, so the laterality assertion passes.

DICOM patient space is **LPS**, which is z-up with anterior toward −y — the same
convention BodyParts3D uses. CBCT meshes therefore pass through `toYUp()`
unchanged, with no extra transform. This was luck, not design, and worth knowing.

The build itself has not been run here: **Node is not installed on the Fedora
box.** `sudo dnf install -y nodejs24 nodejs24-npm` when it is wanted.

## Repository contents

Imaging data is deliberately **not** committed:

- `usb-mirror/` (5.4 GB) and `nrrd/` (551 MB) are far past what belongs in a git
  repo, and GitHub's per-file hard limit is 100 MB. They live in
  `~/projects/3Dentes-cbct/` and are reproducible: the mirror from the USB, the
  NRRDs from `prepare.py`.
- The pilot STLs (9.0 MB) are **provisional** and regenerable from
  `segment_tooth.py` in about a minute. Committing a mesh flagged
  "do not ship unreviewed" would be committing a liability.

What is committed: the tooling, these docs, and `tooth9.json` — the numbers,
which are small and are the actual result.

**Invariant 3 still holds.** When CBCT meshes are eventually committed they go in
their own tree — *not* `assets/source/stl/`, which is CC BY-SA BodyParts3D
material. Anatomy measured from the operator's own scan is a separate work and
must stay physically separate.

## Next

1. **Evaluate DentalSegmentator** before hand-building more teeth. The pilot has
   shown exactly which step it would replace.
2. **Second pilot tooth: 5 or 12** (maxillary first premolar) — the multi-canal
   case, still clear of the crown streak fan. The plan's choice, still right.
3. **Registration** (step 6) once a second volume's geometry is actually needed.
4. **Install Node** and run a real `build:assets` with a CBCT mesh in the tree.
