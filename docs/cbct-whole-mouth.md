# Whole-mouth segmentation — DentalSegmentator, 28 teeth, and their pulp

2026-08-29, Fedora desktop. Supersedes the per-tooth hand-seeding in
[cbct-pilot.md](cbct-pilot.md) for everything except the method's derivation.

Read [cbct-survey.md](cbct-survey.md) first for the dataset facts, and
[cbct-pilot.md](cbct-pilot.md) for why the pulp is measured rather than
thresholded.

## Why the hand-built approach stopped scaling

The pilot segmented tooth 9 well and teeth 5 and 12 badly, for a reason that
turned out to be measurable rather than a tuning failure:

| | tooth 9 (incisor) | tooth 5 (premolar) |
| --- | --- | --- |
| Root dentin | 1305 HU | **1059 HU** |
| Surrounding PDL / marrow | 588 HU | 640 HU |
| **Tooth-to-bone contrast** | **717 HU** | **419 HU** |

The premolar's roots are thin enough that partial volume drags their own density
down toward the alveolus, costing 42% of the contrast. At that separation no
threshold works: sweeping the isolation cut from 1050 to 880 HU swings tooth 5's
volume by 27%, and 24% of its interior falls below the cut that suited tooth 9.

The operator's reading of this was correct and sharper than the density
framing: what separates a tooth from trabecular bone is not a density but the
**PDL/lamina dura dark ring**, a geometric feature. Sampling radially around
tooth 5's root confirmed it — a 691–1514 HU dip against a 70 HU noise floor,
present at 50–85% of angles. That is roughly three times the signal the density
threshold was working with, and the missing angles are what a smoothness
constraint exists to bridge.

That method (polar dynamic-programming contour following) remains the right
fallback. It was not needed, because a trained model does the same job.

## DentalSegmentator

Run **standalone**, not through 3D Slicer: no GUI, no ~1.5 GB install, no sudo,
and the label map drops straight into the existing Python pipeline. Slicer is in
neither dnf nor Flatpak. Inference is **8 seconds of GPU time**.

Environment (all of it inside `~/projects/3Dentes-cbct/nnunet-venv`, outside the
repo): `torch 2.11.0+cu128` — the RTX 5080 is Blackwell, compute capability
12.0, and an older wheel silently falls back to CPU — plus `nnunetv2`, and the
Dataset112 weights from Zenodo.

**Two corrections to the plan's note.** The model emits **per-class**, not
per-tooth, labels: Upper Skull, Mandible, Upper Teeth, Lower Teeth, Mandibular
canal. And that is still the blocker removed, because the hard half was tooth
versus bone. Recall against the hand-built teeth is **0.96–0.98**, and Dice on
tooth 9 alone is **0.899**.

| Label | Volume |
| --- | --- |
| Upper Skull | 31,343 mm³ |
| Mandible | 21,643 mm³ |
| Upper Teeth | 9,351 mm³ |
| Lower Teeth | 9,108 mm³ |
| **Mandibular canal** | **328.7 mm³** |

The mandibular canal arrives free — the inferior alveolar nerve path as measured
structure, one of the project's stated goals.

The model's masks are also **solid**: only 2.9% of tooth 9's mask lies below
800 HU, and the pulp cavity is inside it. The per-slice fill that the hand-built
watershed needed is therefore unnecessary here.

Licence: **CC BY 4.0** — attribution, no ShareAlike, so meshes derived through it
inherit no copyleft, unlike BodyParts3D. Recorded in `ATTRIBUTION.md`. No weights
are redistributed in this repository.

## Splitting the arch into 28 teeth

Three methods were tried; the two failures are worth recording.

- **Distance-transform watershed** peaks once per *cusp* and once per *root*, not
  once per tooth: 87 fragments for 28 teeth.
- **A fixed axial level** works only for the lower arch, which has a clean
  14-component plateau. The upper arch never plateaus — its molar roots separate
  before the crowns do, so the count climbs 5 → 8 → 13 → 21.
- **Arc position works.** Teeth are sequential along the dental arch. Swept as an
  angle about a centre behind the arch, the voxel histogram has one lobe per
  tooth with a minimum at each interproximal contact, and every root of a
  multi-rooted tooth falls in the same lobe. Both arches produced thirteen
  minima — fourteen teeth — unprompted.

Choosing *which* thirteen minima took two further attempts, both of which the
operator caught by eye. Ranking by absolute prominence favoured the wide molar
gaps and fused the crowded lower incisors; normalising by local lobe height
fixed the incisors and split a first molar instead. **The same trade, moved.**

Both cuts are now placed together by **dynamic programming over arc length**,
with a cost combining histogram density at each cut against squared deviation
from the expected mesiodistal width sequence. A global optimum cannot make that
trade, because a spurious cut inside a molar and a fused incisor pair both cost
width error. The sweep is converted from angle to arc length first — a molar
sits at a larger radius than an incisor, so equal angles are unequal
millimetres and a prior in mm cannot otherwise be applied.

Disconnected specks are dropped first: one stray voxel far around the arch
stretched the angular range, and the partition spent a whole tooth on it.

Universal numbers follow from arch and order. **FMA ids are read from
`tools/manifest.mjs`**, so it remains the single source of truth.

### Result

Both arches are anatomically coherent throughout. Upper: molars 1067–1100 mm³
with three roots, premolars 470–530, canines 672/705, laterals 296/303, centrals
516/525. Lower: first molars largest at 1276/1283 — correct, and both carry
zirconia crowns — down to centrals at 236/246.

The operator verified both arch maps.

## Pulp

The method is unchanged from the pilot and is described there: a canal is
narrower than the point-spread function over much of its length, so no threshold
recovers it, but the **intensity deficit integrated across a cross-section** is
conserved and remains measurable. What is new is multi-canal support — the
deficit map on each plane is split into basins by watershed, integrated
separately, and linked plane to plane into tracks. A track is one canal, and
bifurcation falls out for free.

Three refinements were needed, each fixing a real defect:

1. **Track-length filtering in millimetres, not voxels.** The first cut was in
   index units, so 0.24 mm fragments survived and a central incisor reported
   fifteen canals.
2. **h-maxima rather than raw local maxima.** Inside one broad chamber, noise
   produces a dozen peaks above any relative cut, each becoming a spurious canal.
3. **A bounded integration region.** Every voxel darker than the dentin
   reference contributes deficit, and half of any real dentin lies below its own
   60th percentile — so an unbounded basin accumulates dentin noise as lumen. It
   inflated the lower premolars and canines two- to threefold, reporting 3–4 mm
   "chambers" where a premolar's is 1.5–2 mm.

**Canal counts are constrained by a per-tooth-type prior**, the same device as
the width prior in the arch split: the lumen is *measured*, the count is
*capped*. Without it the upper molars reported ten or eleven canals. Surplus
tracks are **folded into the nearest retained canal, not discarded** — an earlier
version dropped them and cost tooth 9 a third of its pulp, 13.9 mm³ against a
validated 20.4.

### Validation

Tooth 9 is the only tooth with independent ground truth, from the single-canal
model built in the pilot. Three separate code paths agree:

| Method | Tooth 9 lumen |
| --- | --- |
| Single-canal centreline model (pilot) | 20.39 mm³ |
| Multi-canal tracker, uncapped | 21.04 mm³ |
| Multi-canal tracker, bounded integration | 19.65 mm³ |

Agreement to ~3% on the same tooth by three routes is good evidence the deficit
integration itself is sound.

### Honest limits

- **The canal count is a prior, not a measurement.** A second mesiobuccal canal
  in an upper first molar, or a second canal in a lower incisor, will neither be
  found nor flagged as missed. Verify against the operator.
- **The coronal chamber is under-represented** in multi-canal teeth. It is one
  broad space split between the canal basins, so each takes a share and no single
  volume represents the chamber.
- **The apical millimetre is a taper extrapolation**, not a measurement.
- **Lateral canals, apical deltas and isthmuses** are neither modelled nor
  present in the data to model.
### Where it lands

**28 teeth, 48 canals, 689.9 mm³ of pulp. 18 of 28 fall inside published
pulp-volume ranges for their tooth type.** The ten that do not are not scattered
— they group, and the grouping says what is still wrong:

| Group | Direction | Teeth | Why |
| --- | --- | --- | --- |
| Upper molars | **low** | 2, 14, 15 | Thin, curved canals; the tracker loses them where they bend out of plane |
| Lower central incisors | **low** | 24, 25 | The smallest pulps in the mouth, at ~8–9 mm³; near the method's floor |
| Lower posterior / canines | **high** | 4, 20, 21, 27, 28 | Residual dentin noise still counted as lumen |

The bounded-integration fix cut the high group substantially — tooth 20 fell from
56.4 to 35.1 mm³ — without disturbing the validated tooth 9. What would close the
rest is a **dentin reference estimated per basin** rather than from a
whole-plane annulus, so that local dentin variation stops contributing deficit.
That is the next obvious improvement and is not done.

Per-tooth numbers are in [cbct-pulp.json](cbct-pulp.json).

## Where the data lives

Unchanged: imaging stays in `~/projects/3Dentes-cbct/`, never in the repo. The
nnU-Net venv (~5 GB) and the model weights live there too, and both are
reproducible from the commands in this document. Committed: the tooling, these
docs, and the JSON results.

---

## Integration — measured anatomy in the actual atlas

Everything above produced files. This is the step that put them in the app.

### The two frames do not meet

Building CBCT teeth alongside BodyParts3D jaws produced a model **1582 mm tall**.
BodyParts3D is a *whole-body* frame with the head about 1470 mm off the floor;
CBCT is scanner-centred at a few tens of millimetres. And even registered, they
are **different people** — one individual's teeth do not sit in another's jaws.

So the "drop-in hard-tissue replacement" the plan describes is not drop-in. The
patient's own anatomy becomes the reference frame, and a CBCT build contains
*fewer* structures rather than a mix: 32 against 45. The ten muscles are absent
because this scan has no soft-tissue contrast at all, and three of the four
maxilla parts because DentalSegmentator's Upper Skull is cropped here to the
alveolar process. Borrowed soft tissue has to be registered **into** the
patient's frame before it can be mixed in, and that is not done.

### The laterality invariant fired, and was right to

`FMA57142 Right lower central incisor: side=right but centroid x=1.5`.

Nothing was mirrored. The check compared centroids against the **framing centre**
— the middle of the model's bounding box — which is not the dental midline. The
operator's arch sits 3.6 mm to their left of the scanner origin (head position,
not anatomy) while the BodyParts3D dentition sits at −0.7 mm, so a box spanning
both put the "centre" between two different people, and a tooth 2.8 mm from its
own midline fell the wrong side of it.

Against the CBCT teeth's own centre, **all 28 teeth were already correct**.

Per CLAUDE.md — *fix the pipeline, don't relax the check* — the fix is that
laterality is now measured from the **dental midline of the model's own teeth**,
which makes it independent of framing and of how the subject was positioned. That
is what it was always meant to test. The BodyParts3D build is byte-identical
after the change.

### Polygon budget

BodyParts3D teeth average 7,101 triangles; raw CBCT teeth were ~70,000, ten times
over. Quadric decimation to ~8,000 keeps cusp tips and the occlusal table while
losing voxel noise.

This does **not** conflict with the exact-welding invariant. Welding merges
bitwise-identical vertices so that no cusp is rounded by a distance tolerance;
decimation happens earlier and is a deliberate, measured reduction. The two
answer different questions.

| | BodyParts3D | CBCT |
| --- | --- | --- |
| Structures | 45 | 32 |
| Triangles | 347,826 | 320,654 |
| Extent | 100.5 × 105.6 × 89.2 mm | 81.6 × 76.7 × 73.3 mm |
| Output | 6.29 MB | 6.89 MB |

Both builds pass laterality. `TOOTH_SOURCE=cbct npm run build:assets` selects the
measured set; the default is unchanged, so the two are a toggle rather than a
migration — which also gives the atlas a generic-versus-patient comparison for
free.

FMA ids remain the join key throughout: `FMA55682` resolves to *Left upper
central incisor, Universal 9, FDI 21, Palmer UL1*, still derived from arch, side
and position rather than typed.
