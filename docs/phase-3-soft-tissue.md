# Phase 3 — soft tissue

Agreed 2026-08-29. Follows [cbct-whole-mouth.md](cbct-whole-mouth.md), which
delivered 28 teeth, their pulp, and the mandibular canal.

**Pulp is soft tissue**, and the most important soft tissue in this atlas. It is
listed first here, not as an afterthought to the hard-tissue work it came out of.

---

## Two measurements that set the boundaries

**There is no usable soft-tissue contrast in this scan.** Outside the bone
labels, 302.8 cm³ of soft tissue forms a single unimodal distribution: p25 = 100,
p50 = 195, p75 = 263 HU. In calibrated CT, fat (~−100) and muscle (~+40) separate
by about 140 HU; here everything sits in one lump. **No muscle, gland, mucosa or
tongue boundary is segmentable from this data at any threshold.** This is
measured, not assumed, and it is what forces tiers 2 and 3 below.

**The mandibular canal is incomplete.** 328.7 mm³ in five disconnected pieces,
with the left canal running to x = +40.8 mm against an FOV edge at +40.96 — it is
truncated. The `centered` volume cannot hold the full foramen-to-foramen path.
This is the first concrete reason to register the `mandibular` volume, and it is
step 1 below.

---

## The organising principle

Soft tissues divide by **whether the hard tissue determines their form**. That
decides where each comes from, and it also decides its licence.

| Tier | How it is obtained | Structures |
| --- | --- | --- |
| **1. Measured** | Directly from the CBCT | Pulp lumen, mandibular canal, apical foramina |
| **2. Derived** | Generated from measured hard tissue | Gingiva, PDL, pulp lining |
| **3. Authored** | Not in the data at any resolution | Tongue, muscles, mucosa, vessels |

---

## Tier 1 — measured

### Pulp, as tissue rather than as a cavity

What exists today is the **cavity boundary**: 28 teeth, 48 canals, 689.9 mm³,
with a measured apical foramen per canal. The pulp tissue fills exactly that
surface, so the geometry is already right — but the claim is not, and the label
must change from *cavity* to *pulp*.

What cannot be measured is the tissue's internal architecture. Dental pulp is an
odontoblast layer, cell-free and cell-rich zones, and a neurovascular core:
10–100 µm structure against 160 µm voxels with worse effective resolution. So
model it as three nested objects and **label their provenance separately**:

1. **Measured lumen** — what we have.
2. **Authored predentin / odontoblast lining** — a thin offset shell inside the
   lumen surface. Derived, not measured.
3. **Schematic neurovascular core** — a centreline tube entering at the measured
   apical foramen. Schematic.

Only the first is data. An atlas that renders all three identically is lying by
omission, and the user is a clinician who will notice.

### The nerve chain

The one genuinely measurable neural pathway, and the atlas's clearest
differentiator over a generic model:

**mandibular foramen → inferior alveolar nerve through the canal → mental
foramen**, with branches to each lower tooth's apical foramen.

The canal and the foramina are measured; the branches are inferred. **Render the
two differently.** A dental professional can then see at a glance which parts of
the path are this patient's anatomy and which are anatomical convention.

The maxilla has no reliable equivalent — posterior superior alveolar canals are
sometimes visible in CBCT but should not be assumed. Worth a look, not a
commitment.

---

## Tier 2 — derived from measured hard tissue

### Gingiva: generate it, do not borrow it

Gingival form is determined by the **cementoenamel junction** and the **alveolar
crest**, and both are now available per tooth. So gingiva can be generated to fit
this patient rather than morphing a generic mesh onto them:

- Free gingival margin roughly 1 mm coronal to the CEJ, scalloped, higher
  interproximally.
- Interdental papillae filling to the contact point.
- Attached gingiva following the bone to the mucogingival junction.

Two benefits beyond fidelity. It is **patient-specific**, and it **removes a
BodyParts3D dependency**, so the result carries no ShareAlike obligation.

**Caveat that must reach the UI:** this models *health*. Real margins vary with
recession, inflammation and biotype, none of which CBCT can see. Label it as an
idealised reconstruction, in the same spirit as the existing `.caveat` block.

### Periodontal ligament

Semi-measured. The PDL was measured *as a signal* — the 691–1514 HU dark ring
that made per-tooth isolation possible. As a structure it is 0.15–0.25 mm, below
resolution, but its **location is measured**, so it can be generated as a shell
between the root surface and the lamina dura.

---

## Tier 3 — authored

Nothing here is in the data. The honest options are BodyParts3D (CC BY-SA) or
authoring from scratch.

**Muscles of mastication** have a middle path worth taking: their *attachments*
are measurable — coronoid process, angle of the mandible, zygomatic arch — so a
generic belly can be fitted to this patient's actual attachment geometry rather
than dropped in unmodified. Partly patient-specific, at modest cost.

**Tongue** is entirely authored, and its position is arbitrary in any case; a
neutral rest posture is as defensible as anything else.

**Mucosa** can be offset from bone where it is bound down, and authored elsewhere.

---

## Licence architecture

Invariant 3 makes this structural, not cosmetic. Three trees, kept physically
separate:

| Tree | Contents | Licence |
| --- | --- | --- |
| Measured | Teeth, pulp, canal | The operator's own data — unencumbered |
| Derived | Gingiva, PDL, pulp lining | Derived from measured data — our own work |
| Atlas-derived | Muscles, tongue if sourced | **CC BY-SA**, inherited |

Anything Blender touches downstream of a BodyParts3D mesh stays ShareAlike. Part
of the appeal of generating gingiva is that it moves a whole structure out of the
third tree.

## Where Blender fits

Its precondition is met — a pilot segmentation succeeded, so the plan's
"not before then" no longer applies. But most of what is described above is
procedural and scripted, which is reproducible and fits the existing pipeline.
**Reserve Blender for what needs a human hand:** retopologising the apical
spikes, and authoring the tongue and muscle bellies. Not for anything a script
can derive.

---

## Order of work

1. ~~**Register the `mandibular` volume onto `centered`**~~ — **done**, see below.
2. ~~**Pulp as tissue**~~ — **done**, see below.
3. **Generate gingiva** from CEJ and alveolar crest — *landmarks done, surface incomplete; see below.*
4. **PDL shell.**
5. **Muscles fitted to measured attachments; tongue authored.** Blender, and last.

See [wishlist.md](wishlist.md) for what this anatomy would later enable.

---

## Step 1 as executed — registration and the canal

**The plan called for Mattes mutual information**, chosen because CBCT gray
values are uncalibrated and shift between exposures. A better option existed once
DentalSegmentator was in place: register **mandible label to mandible label**,
which never looks at intensities at all. That removes the intensity-scaling
problem rather than tolerating it, and it is the plan's "mask the metric to
mandibular structure only" taken to its limit — the mask *is* the signal.

Coarse-to-fine Powell over 6 DOF, 93 seconds. Result: rotation 3.96° / 1.76° /
−0.50°, translation −34.88 / 1.59 / 3.46 mm — dominated by a 35 mm shift along z,
which is simply that the mandibular scan was aimed lower.

### Validation

Raw Dice understates this: the two mandible masks differ in volume because the
fields of view differ, capping achievable Dice. Reported against its ceiling:

| Label | Dice | Ceiling | Note |
| --- | --- | --- | --- |
| Mandible | 0.870 | 0.974 | fitted on this |
| **Lower Teeth** | **0.956** | 1.000 | **held out — never seen by the optimiser** |
| Mandibular canal | 0.722 | 0.971 | thin structure, unforgiving of small error |
| Upper Teeth | 0.742 | 0.947 | *expected* to disagree |

Surface distance from the fixed mandible boundary to the transformed moving one:
median **0.23 mm**, 82.2% within 0.5 mm, against 0.16 mm voxels.

The held-out test is the one that matters. The transform was fitted to the
mandible alone, so the lower teeth — rigidly attached to it but never seen by the
optimiser — are independent evidence, and they land at 0.956.

**The upper teeth at 0.742 against the lower teeth at 0.956 is not a failure; it
is a measurement.** That gap is the maxilla having moved relative to the mandible
between exposures, and it confirms the plan's central claim that no single rigid
transform can align both jaws.

An unplanned cross-check fell out of segmenting both volumes: the lower teeth
measure 9108.2 mm³ in `centered` and 9106.2 mm³ in `mandibular` — **two
independent exposures, segmented separately, agreeing to 0.02%.**

### The canal

Fused on an **expanded grid**, not the fixed volume's own. The transform is
dominated by that 35 mm z-shift, so resampling into the centered grid pushed a
third of the mandibular canal off the end — throwing away exactly the coverage
the registration existed to gain. Growing the grid to hold the union first
recovered it.

| | Volume | Pieces |
| --- | --- | --- |
| `centered` alone | 328.7 mm³ | 5 |
| `mandibular`, transformed | 542.7 mm³ | 4 |
| Union, closed | **618.9 mm³** | **2 — one per side** |

Right canal 335.1 mm³ over 47.2 mm; left 283.8 mm³ over 42.4 mm. Both run
continuously from the anterior loop at the mental foramen back to the ramus, and
both extend beyond the `centered` field of view — to x = +45.4 mm against a
boundary at +40.96, and down to z = −49.2 against a floor at −44.5.

**The inferior alveolar nerve now has a measured course**, which is what item 2
of the order of work needs to wire the apical foramina to.


---

## Step 2 as executed — pulp as tissue, and the nerve chain

Three surfaces per tooth, provenance kept distinct in separate meshes:

| Surface | Provenance | Note |
| --- | --- | --- |
| Lumen | **MEASURED** | 695.0 mm³ across 48 canals |
| Predentin / odontoblast lining | **AUTHORED** | Real thickness 10–40 µm, ~1% of a canal radius — **deliberately exaggerated** to be renderable |
| Neurovascular core | **SCHEMATIC** | 187.9 mm³; a tube on the measured centreline entering at the measured apical foramen |

The nerve chain, likewise tiered: the **canal is measured** (618.9 mm³), the
**trunk inside it is schematic** — CBCT resolves the canal, not its contents —
and the **branches are inferred**, with both endpoints measured and only the path
between them convention. Trunks run 60.8 mm right and 54.6 mm left at ~0.6 mm
radius. **20 branches** reach 12 of the 14 lower teeth, trunk-to-apex 3.2–24.6 mm,
median 9.2 mm.

Teeth 24 and 25 have no branch, and that is correct rather than a gap: the canal
ends at the mental foramen, and the lower centrals are supplied by the incisive
branch, which this data does not resolve.

### Two orientation bugs, both found by building the nerve

Neither could have been caught by the pulp numbers, because both left every
volume and diameter correct.

1. **The ROI crop offset was never added back** when converting tracked indices
   to world coordinates, so all 28 pulp meshes sat at the wrong point in the
   volume. Volumes and diameters are counts and differences, so nothing in the
   numbers looked wrong. It surfaced when a lower-**left** molar's apex came out
   at x = −35.9 — the right side of the head.
2. **The long axis was oriented toward +z for every tooth.** Maxillary roots
   point superiorly and mandibular roots inferiorly, so for the whole lower arch
   the "apical" end was actually the occlusal surface. This showed up as nerve
   branches 18–24 mm long against a canal that runs a few millimetres below the
   molar apices.

After the fix, **28 of 28 teeth have their apex on the anatomically correct
side** — upper apices above their crowns, lower apices below.

**The lesson worth keeping:** when a geometry bug cannot change any scalar you
are printing, print a coordinate. Both bugs were invisible to volume-based
validation and obvious the moment a position was checked against anatomy.


---

## Step 3 as executed — landmarks solid, surface not yet

### The CEJ is measurable. The alveolar crest is not.

This is the substantive finding, and it revises the plan above.

**The cementoenamel junction is reliable.** It is found as the apical edge of the
enamel cap, per tooth, at 24 angular aspects. The check that matters is crown
height, because the CEJ is exactly where the enamel ends: detected enamel extent
matches published crown heights to **within 0.6 mm** across incisors, canines and
molars. All 28 teeth yielded a full 24-aspect CEJ curve — which is what carries
the scallop, since the CEJ rises interproximally and dips mid-facially.

**The alveolar crest was not reliable by the first methods tried** — since
fixed, see "Making the crest trustworthy" below. Two definitions
disagreed by roughly 8 mm *in opposite directions*:

| Crest definition | CEJ-to-crest, tooth 9 | What goes wrong |
| --- | --- | --- |
| 95th percentile of bone within a 9.6 mm angular sector | +4.2 mm | Catches bone belonging to neighbouring teeth |
| Bone contacting the root within 0.6 mm | −4.2 mm | Catches the neighbours' *crowns* instead |

> An earlier draft reported a 4.50 mm median CEJ-to-crest across all 28 teeth,
> which would be generalised periodontitis. **It was an artefact of the crest
> definition, not a finding**, and the uniformity across every tooth — including
> teeth that would have to be independently affected — was the tell.

### The gingival margin is correct and patient-specific

Built from the measured CEJ, offset 1 mm coronally along each tooth's own axis.
Verified: **0 of 28 margin rings sit more than 6 mm from their tooth**, with
sampled teeth 0.6–1.9 mm from their centroids, and the rings span the full arch.
This is the part worth keeping — it is genuinely this patient's gingival margin
geometry rather than a generic curve.

### The gingival surface is a first attempt and is not usable

Upper 3666 mm³, lower 4633 mm³. The upper has the right form — a scalloped
margin with teeth emerging through their sockets — but the lower renders as a
flat slab rather than following the alveolar ridge, both are terraced, and 738k
triangles for one arch means the bone envelope is being taken far too
generously. **Do not ship this.** What it needs:

- The coronal/apical band to follow the ridge rather than a smoothed height field
  over (x, y), which is what flattens the lower arch.
- Interdental papillae, currently stubbed out at zero rise.
- The mucogingival junction placed from anatomy rather than a fixed 7 mm.

### The same coordinate bug, a third time

`landmarks.py` stored each tooth's centroid as a **sub-volume** index, so every
margin point collapsed into a 12 mm patch of the anterior right instead of
following the arch. This is the third appearance of one bug class in this
pipeline — after `pulp_all.py`'s missing crop offset and its +z axis convention
— and it was reintroduced *two steps after being written into CLAUDE.md*.

The lesson stands and needs enforcing rather than restating: **any function that
works in a cropped sub-volume must return world coordinates, not indices.**
Returning an index across that boundary is what keeps failing, and the fix is to
make the boundary impossible to cross wrongly rather than to remember it.


---

## Making the crest trustworthy

Both failures had one cause: **neither excluded the other teeth.** A wide angular
sector reaches into a neighbour's alveolus; a tight shell touches a neighbour's
crown, which is denser than bone. The crest is not a percentile of nearby bone.

`tools/cbct/crest.py` replaces it with a **directed apical search**: start at the
measured CEJ, walk apically along the root surface at each of 24 aspects, and
stop where bone first appears *and persists* for 0.8 mm. Every tooth in both
arches is masked out first, so a neighbour's crown can never register as bone,
and persistence rejects a single dense voxel clipped in passing.

### Validation: the same measurement on a second exposure

The anatomical prior first used — "interdental crest sits coronal to facial" —
is **wrong as a test of the gap**. In health the crest *follows* the CEJ, so the
CEJ-to-crest distance is roughly constant around a tooth; it is the absolute
heights that rise interproximally, not the gap that shrinks. Checking it that way
was measuring nothing.

The test that does work needs no prior at all: resample the `mandibular` volume
into the `centered` frame through the registration, and re-measure. Same anatomy,
same geometry, **independent image data**.

| Arch | n aspects | Median difference | MAD | ≤1 mm |
| --- | --- | --- | --- | --- |
| **Lower** (both volumes cover it) | 302 | **+0.00 mm** | 0.32 mm | 68.5% |
| Upper (clipped in `mandibular`) | 324 | +0.80 mm | 1.28 mm | 42.6% |

**Unbiased, and imprecise.** Zero median difference across two scans means no
systematic error remains. But only ~68% of individual aspects agree within 1 mm,
so this is trustworthy **per tooth**, not per aspect. The upper arch's poorer
agreement is expected — the mandibular volume clips it — and confirms the lower
arch is the fair comparison.

### The result

**Lower-arch CEJ-to-crest: 1.92 mm** (per-tooth medians; 1.92 from `centered`,
1.64 from `mandibular`, IQR ~1.1–2.6). **That is within the normal range, and
there is no generalised bone loss.** The 4.50 mm figure is retracted.

Two teeth read above 3 mm — **20 and 29**, both second premolars — but each
yielded only 7 of 24 aspects, so they are the least-sampled teeth in the set and
this is weak evidence rather than a finding.

One coherent artefact: the **crowned molars 19 and 30 disagree between exposures
by 1.2 and 2.0 mm, against 0.36 mm elsewhere.** Zirconia beam hardening degrades
the crest measurement exactly where `docs/cbct-survey.md`'s artifact map said it
would. Their crest values should carry that caveat.

### What this is and is not

It is good enough to **place the gingival margin and drape the attached gingiva**,
which is what Phase 3 needs it for, and good enough to say this patient's bone
levels are normal. It is **not** a periodontal charting tool: ±1 mm per aspect
cannot resolve an early localised defect, and it should never be presented as if
it could.
