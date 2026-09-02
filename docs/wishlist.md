# Wishlist

Ideas captured for later. Nothing here is scheduled, and nothing here should be
built before the Phase 3 anatomy it depends on exists. Recorded so they are not
lost, with a note on what each actually needs.

**Two ordering constraints, though, added 2026-08-31 — these are not free to
reshuffle:**

- **Enamel, dentin and cementum come before the radiograph simulator.** Tissue
  identity plus density is what a DRR integrates; building the DRR first means
  building it twice.
- ~~**Provenance labels come before anything simulated.**~~ **Done 2026-08-31.**
  Anaesthetic diffusion and the pathology sliders generate geometry that is
  neither measured nor a literature mean; there is now a per-structure tier to
  say so, and a `simulated` tier waiting for them.

Both are buildable now and need no new anatomy.

And one item is genuinely **scheduled**: an intraoral scan of the operator's own
arches, around late September 2026, which would move the gingiva from derived to
measured. See [Scan the gingiva](#scan-the-gingiva-and-stop-deriving-it--scheduled-late-sept-2026).

---

## The unifying idea: a digitally reconstructed radiograph

Items 2 and 3 below both hinge on one capability, and it is worth stating
separately because it changes how hard they are.

A simulated periapical or bitewing radiograph is a **digitally reconstructed
radiograph (DRR)** — a ray-cast integral of attenuation through a volume. We
already have the volume, at 0.16 mm isotropic, of *this patient*. So a simulated
radiograph would not be a generic illustration: it would show the same anatomy as
the 3D model, because it is computed from the same data.

That has two consequences worth designing around:

- **Cone-beam geometry, not parallel projection.** Foreshortening and elongation
  are exactly what receptor angulation teaches, and a parallel projection cannot
  show them. Model a source point, a receptor plane, and the bisecting angle.
- **Pathology modelled once, seen twice.** If a lesion is a parametric
  perturbation of the *volume* — a density deficit at an apex, a concavity on the
  lingual mandible — then the DRR picks it up for free and the 3D model shows the
  same object. One model, two views, always consistent. This is the reason to
  build pathology volumetrically rather than as a decal on a mesh.

Feasible in the existing stack (WebGL ray-marching in three.js), but the volume
is ~185 MB per arch and would need aggressive downsampling or a cropped region of
interest to ship to a browser. That is the main engineering question.

**Prerequisite, added 2026-09-01: fix the inter-tooth contact boundaries first.**
The arch split ends each tooth at its contacts, and at a true contact the two
crowns' enamel is one contiguous mass with no separating feature, so the
boundary currently lands as a near-planar chord through the crown. Nothing is
lost from the mouth — the wedge cut off one tooth is labelled as its neighbour —
so the assembled atlas renders correctly and this is invisible until something
integrates density PER TOOTH. That is exactly what a DRR does, and the bitewing,
its flagship view, is *about* the interproximal contact. Shipping a simulator
whose contact geometry is arbitrary would fail at the one thing it exists to
teach. See [Fix the inter-tooth contact boundaries](#fix-the-inter-tooth-contact-boundaries--prerequisite-for-the-drr).

**Prerequisite, added 2026-08-31: split the hard tissue into enamel, dentin and
cementum first** — see that section below. Tissue-labelled geometry carrying its
own density is a second, much lighter substrate for the ray-cast, and it may
remove the shipping problem entirely rather than mitigating it.

---

## 1. Pulpitis → necrosis → root canal, as a timelapse

A progression the user can scrub through:

1. Intact tooth.
2. Insult — trauma, or restoration placement with its thermal and mechanical
   history.
3. Reversible pulpitis, then irreversible.
4. Necrosis, with the periapical consequence appearing (see PARL, item 3).
5. Cross-section of the complete root canal procedure: access cavity, working
   length, cleaning and shaping, obturation.

**What it needs:** the pulp as *tissue* with internal structure, not just a lumen
boundary — the odontoblast layer and neurovascular core described in
[phase-3-soft-tissue.md](phase-3-soft-tissue.md). Inflammation and necrosis are
changes in that tissue, so the tissue has to exist first.

**Worth noting:** the operator's dentition has **no endodontic treatment
anywhere**, so all 28 pulps are native and unobturated. The atlas therefore shows
the *healthy* baseline from real measured anatomy, and the diseased states are
authored departures from it. That is the right way round, and rarer than it
sounds — most endodontic teaching material starts from treated teeth.

The access cavity and instrumented canal are *authored* geometry, not measured.
Keep them in a separate tree from the measured pulp.

---

## 2. Draggable radiograph simulator

A side panel showing a simulated PA or bitewing. The user drags a receptor around
the arch and sees what that placement would produce.

- Receptor position and angulation as the controls; paralleling versus bisecting
  technique as a mode.
- Show the resulting cone cut, foreshortening, elongation, and overlap — the
  actual failure modes of the technique.
- Ideally: display the receptor and beam in the 3D view simultaneously, so the
  geometry and its result are visible together.

**What it needs:** the DRR above. Nothing else — this one is buildable on the
existing volume without any further anatomy.

**Why it is the strongest item here:** it teaches something no static atlas can,
and the data to do it honestly already exists.

---

## 3. Pathology menu, shown on model and radiograph together

Select a pathology; it appears on both the anatomical model and the simulated
radiograph, consistently, because both read the same volumetric perturbation.

Initial candidates:

| Pathology | Volumetric form | Ties to |
| --- | --- | --- |
| Periapical radiolucency | Density deficit centred on an apical foramen | Item 1's necrosis stage |
| Stafne defect | Lingual concavity of the mandible, below the canal | — |
| Cementoma / periapical cemento-osseous dysplasia | Mixed deficit and excess at apices, staged | Progression variable |

**Randomizable variables**, so the same pathology yields unlimited practice cases:

- Size.
- Location, constrained to a defined set of anatomically valid points — for a
  PARL, the measured apical foramina; for a Stafne defect, the lingual mandible
  below the canal.
- Disease progression / stage, which for a cementoma is a genuine radiographic
  sequence from radiolucent through mixed to radiopaque.
- Optionally: whether the lesion is visible on a given projection at all, which
  is itself the lesson — a buccal lesion hidden by the root on one angle.

**What it needs:** the DRR, plus the measured apical foramina (**already have
these — 48 of them**) as anchor points, plus the mandibular canal as an anatomical
constraint for anything sited near it.

**Design note:** the anchors should be the *measured* landmarks wherever possible.
A PARL placed on a real apical foramen at a real position is a better teaching
object than one placed at an arbitrary point, and costs nothing extra now that the
foramina are measured.

---

## Time-varying sliders — one mechanism, three diseases

All three below are the same interaction: a scrub bar the operator drags, with
the model and (once the DRR exists) the simulated radiograph both updating. They
are grouped because building the scrubber once buys all of them, and because
each is a process a patient actually walks through over years rather than a
static finding.

### Calcification with age

Secondary dentin deposits throughout life, so the chamber and canals narrow and
the pulp horns recede. This is the single most useful one for teaching, because
it is what makes an endodontic access on a 70-year-old different from the same
tooth at 20, and it is measurable rather than invented: pulp chamber volume has a
well-documented linear inverse association with age, which is the basis of the
CBCT age-estimation literature. It also runs *backwards* from the model we have
— the operator's own dentition is a real point on the curve, so the slider
interpolates from measured geometry rather than from an average.

**What it needs:** an erosion of the pulp surface parameterised by age, with the
apical foramen narrowing faster than the chamber; ideally calibrated against
published pulp-volume-versus-age regressions rather than chosen by eye.

### Dentinal decay

A caries lesion advancing from the enamel surface through dentin toward the
pulp, with the slider being lesion depth. The teaching value is the relationship
between radiographic depth and pulpal status — the point at which a restorable
lesion becomes a pulpotomy becomes a root canal.

**What it needs:** a lesion volume seeded on a tooth surface and grown along
dentinal tubule direction (toward the pulp), subtracted from the dentin. Should
respect the enamel-dentin junction, where real lesions spread laterally.

### Fracture progression

From a small coronal crack extending apically to a full root-length fracture,
with the **J-shaped radiolucency** appearing on the simulated radiograph as it
progresses — the halo that wraps the apex and runs up one side of the root,
which is the classic sign and the reason this belongs with the DRR work.

**What it needs:** a fracture plane through the tooth with a controllable apical
extent, plus the associated bone loss pattern. The J-shape is a *consequence* of
modelling the periradicular bone loss correctly, not a shape to be drawn — if it
emerges from the DRR on its own, the simulation is right.

**Note on all three:** these are the first features that would show *disease*
rather than anatomy. Everything shipped so far is measured or modelled from one
healthy dentition, and the provenance tiers say so. A pathology slider produces
geometry that is neither measured nor a literature mean but a *simulation*, and
it needs a fourth tier or a very loud label, or the atlas quietly starts
asserting things about a real person's mouth that are not true of it.

---

## Vascular structures — arteries and veins

**Arteries red, veins blue**, matching the yellow now used for nerve tissue, so
the neurovascular bundle reads at a glance.

The bundle in the mandibular canal is not a nerve alone: the inferior alveolar
**artery** (from the maxillary artery) and **vein** run with the IAN and share
its course, so the geometry already built for the trunk carries all three — the
canal lumen is the measured part and the split between its contents is not
resolved at 0.16 mm. The same is true of the incisive and mental branches. In
the maxilla the posterior, middle and anterior superior alveolar arteries
accompany their nerves, and the infraorbital artery runs with the infraorbital
nerve in its canal.

**What it needs:** a `vessels` layer with two materials; arterial and venous
courses derived from the nerve centrelines where they are genuinely companion
vessels, and separate geometry where they are not (the greater palatine and
sphenopalatine vessels have no nerve twin in this model). Provenance is the
usual problem — the canal is MEASURED, its division between artery, vein and
nerve is SCHEMATIC, and the atlas must not draw three tubes in a canal it only
ever saw as one lumen and imply otherwise.

---

## Fix the inter-tooth contact boundaries — prerequisite for the DRR

`split_teeth.py` partitions the arch by arc position and then `refine_boundaries()`
moves the cuts off the sector planes and onto the necks with a watershed. That
function's own comment names where it still fails: *"Where two teeth are in true
contact the distance transform has no minimum to cut at."* With no waist to
settle into, the watershed boundary lands wherever the eroded seeds happen to
meet — a near-planar chord, sometimes well inside the crown.

**What it does and does not break.** It does not lose tissue: the wedge taken off
one tooth is labelled as its neighbour, so the assembled model is right and the
error exists only per tooth. It does distort anything measured PER TOOTH from the
mask — the CEJ ring is the live example, and a chord through the crown is the
most likely cause of the implausible 3.84 mm cervical scallop measured on tooth
29, which matters because the gingival margin is lofted from that ring.

**Why it gates the DRR** is in that section above. Enamel work is not blocked by
it: `enamel.py`'s `outer_depth()` measures against the tooth *union its
neighbours*, so a contact face is interior and no enamel is painted onto the cut.

**What it needs.** A boundary criterion that does not depend on a distance
minimum — the midsurface between the two teeth's own bodies, or the intensity
dip where one resolves. Cost is compute, not hand work: the pulp tracings are
stored against `crop_origin_zyx` in VOLUME space, not against the split labels,
and the pulp is nowhere near the contacts, so a re-split does not invalidate
them.

**The honest caveat.** At a true contact the two enamel surfaces touch, and at
0.16 mm the scan may not resolve a boundary at all. Some of "the correct split"
there is a modelling choice rather than a measurement, which makes it a
provenance question as much as a geometric one. Decide that deliberately instead
of tuning until it looks right.

---

## Enamel, dentin and cementum — before the DRR, not after

Split the hard tissue into its actual constituents, each carrying a density. The
model currently treats a tooth as one homogeneous solid with a lumen cut out of
it, which is why the README's "what it is not" still says *no enamel/dentin
split*.

**This is sequenced deliberately ahead of the radiograph simulator.** A DRR is an
integral of attenuation along a ray. If every structure already carries a tissue
identity and a density, the ray can be integrated against *labelled geometry*
instead of against the 185 MB voxel volume — which is the one engineering problem
the DRR section flags as unsolved. Doing this first may turn the radiograph
simulator from a volume-shipping problem into a shading problem. Doing it
afterwards means building the DRR twice.

It also pays off immediately in the atlas itself, independent of any radiograph:
the enamel cap, the dentin bulk and the DEJ between them are what a tooth
cross-section is actually *about*, and caries depth (in the sliders above) is
meaningless without them.

### What separates and what does not

| Tissue | How it comes out | Standing |
| --- | --- | --- |
| **Enamel** | Thresholds. Densest tissue in the body, and well clear of dentin at 0.16 mm — the CBCT plan lists enamel/dentin separation as one of the reasons for this data. | **Measured** |
| **Dentin** | The remainder of the tooth solid once enamel, pulp and any prosthetic are removed. | **Measured** |
| **DEJ** | Falls out as the shared boundary. Not drawn separately, but it is the surface caries spreads along. | **Measured** |
| **Cementum** | **Will not threshold.** 20–50 µm at the CEJ, thickening to perhaps 150–200 µm apically — every part of it is sub-voxel at 0.16 mm, and it is barely denser than dentin besides. Build it as a thin shell on the root surface, CEJ to apex, thickening apically. | **Derived / exaggerated**, exactly like PDL thickness |
| **Zirconia on 19 and 30** | Thresholds far above enamel; already flagged in the artifact map as a separate `prosthetic` label. | **Measured, but lab work — not anatomy** |

The CEJ is already measured per tooth (Phase 3, step 3), so the cementum shell
has a real upper boundary to start from. The **cementodentinal junction has no
measured position at all** — it is wherever the authored shell thickness puts it.
Same failure mode as the PDL: measured in position, drawn thicker than the truth.

### Density, and how to store it

Store **composition and physical density per tissue**, not a single attenuation
coefficient. µ is energy-dependent, so a bitewing at 60 kVp and a pan at 70 kVp
attenuate the same enamel differently; baking one µ in now makes kVp
unsimulatable later, and kVp is itself a thing worth teaching.

Rough physical densities to start from — to be sourced properly, not left as
these numbers: enamel ~2.9–3.0 g/cm³, dentin ~2.1–2.2, cementum ~2.0, cortical
bone ~1.9, trabecular bone much lower and heterogeneous, pulp ~1.0, zirconia
~6.0. Whatever is used, cite it, and let the provenance labels below carry the
citation.

**What it needs:** nothing new from the scan. Enamel is a threshold within the
existing per-tooth masks, which already exist for all 28. Cementum is a script,
like the gingival collar. This is the most immediately buildable large item here.

---

## ~~Provenance label on every structure, in the UI~~ — DONE 2026-08-31

Every structure should state **how it was generated**, in the app, at the point
of selection — not only in the README and the docs.

The distinction already exists and is already carefully maintained in prose: the
README's measured / derived / schematic table, the Phase 3 provenance summary,
and Invariant 4's caveat block. What is missing is that **the model itself does
not carry it**. In `tools/manifest.mjs` provenance survives only as a
`(schematic)` suffix inside a display name, which cannot be filtered, cannot be
styled, cannot be cited, and quietly disappears the moment someone tidies the
names.

### The shape of it

A `provenance` field on every manifest entry — manifest is already the single
source of truth for layer, side and notation, and this belongs beside them:

- **`tier`** — measured / derived / schematic / simulated. (The fourth tier the
  pathology sliders will need is the same field; add it once.)
- **`method`** — one line, specific. Not "measured" but *how*: "hand-traced on
  axial slices, 0.16 mm CBCT"; "thresholded, then watershed out of its socket";
  "lofted from the measured CEJ, refitted to published cervical-line curvature";
  "centreline through the mandibular canal — the canal is measured, its contents
  are not".
- **`sources`** — citations, required for anything approximated. The maxillary
  nerve courses are textbook, and the atlas should say *which* textbook.

Worked examples of what each would say:

| Structure | Tier | Method |
| --- | --- | --- |
| Teeth, mandible, maxillae | Measured | Segmented from 0.16 mm CBCT |
| Pulp | Measured | Hand-traced per slice — no threshold separates it from dentin at this resolution |
| Apical foramina | Measured | Intensity-deficit integration across the canal cross-section |
| Inferior alveolar nerve | Measured *course*, schematic *content* | The canal void was traced foramen to foramen; the nerve inside it is drawn, not seen |
| Mental / incisive branches | Schematic | Foramen measured, course inferred |
| PSA, MSA, ASA, infraorbital | Schematic | Textbook course; superior alveolar canals not resolved at 0.16 mm. Cite the source |
| Gingiva | Derived | Collar lofted from measured CEJ |
| PDL | Measured position, exaggerated thickness | Both walls measured; drawn far thicker than ~0.2 mm, which is one voxel |
| Cementum *(once built)* | Derived | Authored shell on the measured root surface |

### Why it matters more than it looks

This is the machine-readable form of Invariant 4. A caveat paragraph describes
the *build*; a per-structure field describes the *object the user just clicked*,
which is where the question actually arises. It also unlocks small things that
are otherwise impossible: filtering the view to measured anatomy only, or tinting
schematic structures so the eye is told the same thing the text says.

**Built 2026-08-31**, as described: `provenance()` in `tools/manifest.mjs`
returns a `tier`, a `method` and `sources`, the detail panel renders it as a
coloured block under the selected structure, and invariant 6 fails the build if
any structure lacks one. 58 measured, 32 derived, 4 schematic.

Two things worth knowing that only appeared in the building:

- **The tier had to describe the geometry AS DRAWN**, not the best evidence
  behind it. The inferior alveolar nerve was the test case: its course is the
  measured canal, but what is rendered is a tube of chosen calibre on that
  centreline, so it is `derived` rather than `measured`, with the method saying
  which half was seen. Tiering by the strongest input would have quietly promoted
  half the atlas.
- **The `(schematic)` name suffixes are gone.** They were the only carrier of
  provenance before, and keeping them alongside a real tier meant saying it
  twice. The nerve layer's comment used to warn against removing them; the tier
  is what protects that distinction now, and it protects it better, because the
  build enforces it.

The `simulated` tier is defined and unused, so the anaesthetic diffusion and the
pathology sliders cannot ship without choosing a tier.

---

## Shade the landmark, do not invent the point — a rule for the whole atlas

**Operator's idea, 2026-09-01, and it generalises well beyond anaesthesia.**
Where a landmark is not resolved in this scan, do not place a point. Render the
REGION the literature says it is most commonly found in, and let its size carry
the uncertainty.

This came up because the anaesthesia item needs targets the scan does not give.
Tonight established that two of Malamed's constructions cannot be anchored here
at all: the infraorbital canal does not resolve, and the mandibular foramen's
landmarks need the ramus's posterior border and a coronoid notch that no field
of view ever contained. The alternatives had been (a) place a point anyway from
a published mean, which draws a confident dot on anatomy nobody measured, or
(b) omit the landmark, which teaches nothing. A shaded region is the honest
third option, and it is *more* useful for teaching than a point: the spread is
the clinically important part. A needle aimed at a mean is aimed at a place the
foramen is, in most people, not.

**Why it fits the provenance system rather than fighting it.** Every structure
already declares how it was made. A region says the same thing in geometry: its
extent IS the claim. A 2 mm blob and a 12 mm blob are different assertions, and
the reader does not have to open a panel to see which one they are looking at.

**How to build it, in the order the honesty degrades:**

1. **From a published dispersion.** Where a morphometric series gives a mean and
   an SD relative to a landmark THIS scan measured, the region is that
   distribution mapped onto measured bone. The infraorbital foramen is the clean
   case: 5.8–7.3 mm below the inferior orbital margin across several series, and
   the orbital rim is measured. That is a band, not a point, and drawing it as a
   band is simply telling the truth.
2. **From a landmark-relative construction with no dispersion quoted.** Malamed's
   mandibular foramen is here — ~19 mm below the coronoid notch, ~2.75 mm behind
   the ramus midpoint, with no spread given and, on this scan, without either
   reference. The region has to be sized from a separate anatomical series, and
   the structure must say that its *anchor* was unavailable, not just its
   position uncertain.
3. **From nothing but a textbook picture.** Do not draw it.

**What it needs:** a `region` tier alongside `measured` / `derived` /
`schematic` / `simulated`, rendered as a translucent volume rather than a
surface, and a UI convention that reads as "somewhere in here" at a glance —
probably a soft-edged isosurface rather than a hard shell, since a hard shell is
itself a false precision. The `simulated` tier is already defined and unused;
this is a sibling to it, not a special case of it.

**Do this before the anaesthesia item, not during it.** That feature will want
several of these, and inventing the convention while also modelling diffusion
would mean deciding twice.

---

## Local anaesthetic delivery, from needle to numb tooth

Show the injection techniques as *three-dimensional geometry*: the needle in the
soft tissue, the solution leaving the bevel, its spread through tissue, and which
nerves — and therefore which teeth — that spread actually reaches.

### Techniques worth covering

| | Target | Why it is worth drawing |
| --- | --- | --- |
| **Maxillary infiltration** (supraperiosteal) | Apex of the target tooth | The whole technique depends on the maxillary plate being thin and porous — the one place diffusion through bone works |
| **PSA, MSA, ASA / infraorbital** | Regional maxillary blocks | Their target nerves are already in the model, schematically |
| **Greater palatine, nasopalatine** | Palatal soft tissue | Both foramina are potentially measurable in the volume |
| **IANB** (Halstead) | Mandibular foramen, above the lingula | The classic, and the classic failure |
| **Gow-Gates** | Neck of the condyle | Higher target, larger bony landmark, catches branches the IANB misses |
| **Vazirani-Akinosi** | Closed-mouth, pterygomandibular space | The technique for a patient who cannot open — ties directly to the mouth-opening item below |
| **Long buccal, mental / incisive** | Terminal and soft-tissue supply | Explains why an IANB alone does not get you a mandibular extraction |
| **Intraligamentary, intraosseous** | PDL space, cancellous bone | Both target structures already exist in the model |

### Why this model is unusually well placed to do it

**The bony targets are measured.** The mandibular foramen and lingula, the
condylar neck, the mental foramen, the apices of every maxillary tooth, and the
mandibular canal itself are all real geometry from this patient's scan — so
"where the needle goes" is not an illustration, it is a position relative to
measured bone. Very little teaching material can say that.

**The failures are geometric, and therefore showable.** An IANB deposited too low
or too anterior misses because of where the foramen actually is. Contacting bone
too early means the wrong angle of approach. A buccal infiltration failing in the
adult mandible is a cortical-plate thickness fact, and the plate thickness is
*in the scan*. These are the things that are hard to teach from a diagram and
easy to show from a model.

### What it needs

- **Soft tissue that does not exist yet** — oral mucosa, the pterygomandibular
  space and raphe, buccinator, medial pterygoid. This is Phase 3 tier-3 work and
  gates the whole item. The maxillary infiltrations need much less of it than the
  mandibular blocks do.
- **A needle** as a positioned rigid body: insertion point, angulation, depth,
  bevel orientation. Gauge and length matter (25 mm long vs 20 mm short changes
  which techniques are even possible).
- **A diffusion field** from the deposition point — a scalar spreading through
  tissue, blocked by cortical bone, permeable where the plate is thin. This is
  the actual mechanism of the lesson and the reason the item is not just a video.
- **A nerve-territory map**, so a nerve inside the anaesthetised field marks its
  teeth numb. Partly present already: there is a measured branch to all 14 lower
  apices.
- **Aspiration** would want vessels — see the vascular item below. The inferior
  alveolar artery and vein share the canal, which is exactly why aspiration is
  taught.

**Provenance warning, and it is a serious one:** the needle path is authored, the
soft tissue it passes through is authored, and the diffusion is a *simulation* —
not measured, not a literature mean. This is the same fourth-tier problem the
pathology sliders raise, and here it is sharper, because a plausible-looking
depth-and-angle animation reads as clinical instruction. It needs the provenance
labelling above to exist first, and it needs to be loud.

---

## Open and close the mouth

Once there is enough soft tissue for it to mean anything, let the mandible move.

**It is not a hinge.** Mandibular opening is rotation in the lower joint
compartment for roughly the first 20–25 mm, and then translation as the condyle
runs forward and down the articular eminence. Animating a pure hinge through a
full opening puts the condyle through the eminence and is wrong in exactly the
way the TMJ is interesting.

### What it needs

- **A mandibular group in the scene graph.** Everything mandibular has to move
  together: the mandible, the 14 lower teeth, their pulp and PDL, the lower
  gingiva, the inferior alveolar nerve with its dental, mental and incisive
  branches. Today these are flat siblings in one glTF, so this is a real
  restructuring of the scene, not a transform on one node. Worth designing before
  the tree gets larger.
- **A condylar path — and it will have to be generic.** *Answered 2026-08-31 by
  `tools/fov-audit.mjs`:* the mandible is **cut through both rami**, with a
  172 mm² planar cap on the right FOV wall, 191 mm² on the left, and 156 mm²
  where the posterior wall slices the ramus coronally. Its full width is 82.0 mm,
  which is the 81.9 mm FOV exactly. A bicondylar breadth is around 120 mm, so the
  condyles were never in the box — and neither were the glenoid fossa or the
  articular eminence. There is no measured eminence slope to derive an opening
  path from, and the Gow-Gates target in the anaesthesia item above sits in bone
  this scan never saw. Use a published condylar path and label it schematic.
- **Muscles that deform rather than translate.** This is the real reason to wait:
  masseter, medial pterygoid and lateral pterygoid all change shape through the
  opening, and rigidly transforming a static belly with the mandible will look
  broken. Phase 3 step 5 fits the muscles to measured attachments; do that first.
  The lateral pterygoid is the one that *produces* translation, so it is the one
  that has to be right.

### What it buys

- **The mandibular anaesthesia techniques above.** IANB and Gow-Gates are given
  with the mouth wide open; Vazirani-Akinosi is defined by being closed. The
  techniques cannot be shown honestly in a fixed-occlusion model.
- **Occlusion**, eventually — contacts, excursions, and the difference between
  centric relation and maximum intercuspation.
- **The scan itself is a single frame**, so all of this is authored motion over
  measured geometry. Note also that the three CBCT exposures caught the mandible
  in different positions, which is a caution about the source data rather than a
  source of motion data.

---

## The rest of the skull — generating what the FOV never saw

Everything in the atlas stops at the edge of an **8 cm cube**. All three volumes
are 81.9 × 81.9 × 81.76 mm at 0.16 mm isotropic (see
[cbct-survey.md](cbct-survey.md) §2), aimed at three different places. Their
union is a dentition and its immediate surroundings — it is nowhere close to a
skull.

So the maxillary nerves currently run through empty space, the mandible ends
where the box ends, and there is no cranial context to orient any of it against.
For an atlas whose whole argument is *this is measured*, the boundary of what was
measured is presently invisible.

### What is missing, and why each matters

| Structure | Why it is wanted |
| --- | --- |
| **Glenoid fossa and articular eminence** | The mouth cannot open correctly without the eminence — see [Open and close the mouth](#open-and-close-the-mouth). **Confirmed outside every FOV** by the audit below. No longer necessarily generated: a small-FOV TMJ volume would measure it, though the fossa is the harder of the two to register — see below. |
| **Condyle and upper ramus** | The Gow-Gates target is the condylar neck. The audit below shows both rami sliced by the FOV walls, so the condyle is absent outright. **A TMJ volume would measure this cleanly**, registering on the mandible via the shared ramus. |
| **Pterygopalatine fossa, foramen rotundum, pterygoid plates** | V2's course. The maxillary nerves are drawn schematically already; without this bone they are schematic *and* floating. |
| **Infraorbital canal and rim, orbital floor** | The ASA and infraorbital nerve terminate here. Also the roof of the maxillary sinus, which *is* well resolved. |
| **Zygomatic arch and zygomaticomaxillary complex** | Masseter origin — needed the moment muscles are fitted to attachments. |
| **Cranial vault, base, nasal bones, hyoid, cervical spine** | Orientation and context only. Cheapest to fake, least at stake. |

### The FOV audit — done 2026-08-31

`tools/fov-audit.mjs` measures every shipped mesh and detects where the FOV cut
it, by finding planar caps sitting on a bounding-box face: truncated anatomy ends
in a flat wall, intact anatomy closes over smoothly. Results:

| | |
|---|---|
| **Measured anatomy spans** | 85.6 × 73.5 × 80.1 mm — against an 81.9 mm box per volume. It exceeds one FOV in x only because the mandibular volume is registered in alongside `centered`. |
| ~~**Mandible: cut through both rami**~~ | 172 mm² cap on the right wall, 191 mm² on the left, 156 mm² posteriorly. Width 82.0 mm = the FOV exactly. **Fixed 2026-09-01** by registering the mandible-focused exposure in: `FMA52748M` adds 12.0 cm³ and the rami are no longer truncated. |
| **Condyle, fossa, eminence** | **Not measured, and never could have been.** Bicondylar breadth is ~120 mm against an 81.9 mm box. |
| **Upper skull: NOT cut** | Caps of 4–18 mm² only, i.e. it closes smoothly. Its extent is a *segmentation* crop by DentalSegmentator, not an FOV limit. |

That last row is the useful one, and it changes the shape of this item.

**Some of the missing bone is not missing — it is unexported.** The upper skull
mesh stops where the label stops, not where the data stops, so there is measured
bone in the volumes above and lateral to it that has never been meshed. The
`maxillary` volume is the clearest case: [cbct-survey.md](cbct-survey.md) §3
found it to be a **sinus / root-apex / nasal-anatomy volume** whose upper crowns
fall below the FOV floor, which is why it was set aside as an arch source — and
it is currently used for nothing at all. It covers a good part of the mid-face
wanted in the table above: orbital floor, infraorbital canal and rim, sinus
walls, nasal bones.

**Partly done, 2026-09-01.** The `centered` volume's share of this is recovered:
`FMA53649U` ships the 3.6 cm3 the maxilla's 22 mm crop was discarding — posterior
mid-face and pterygoid region, plus the infraorbital rim and zygomatic process
bilaterally. Two things were measured while doing it and are worth not
rediscovering:

- **There is no large body of unlabelled bone in `centered`.** Tissue at or above
  400 HU carrying no label at all comes to 3.7 cm3 scattered across 1,979
  components, the largest 286 mm3 — noise, not a zygomatic arch. The nnU-Net
  label had already found essentially all of it; the loss was at EXPORT, not at
  segmentation.
- ~~**The remaining prize is the `maxillary` volume**~~ **Done 2026-09-01.** It
  is registered in (`docs/transform-maxillary-to-centered.json`) and ships 23.0
  cm3 as `FMA53649M`. Its upper-skull label holds 54.0 cm3 against `centered`'s
  31.3, and the atlas now reaches 75 mm above the occlusal plane instead of 37.
  It remains **essentially free of crown artefact** (max 2605 HU against
  `centered`'s saturated 3072) because the zirconia sits outside its field of
  view — worth remembering for anything that needs clean mid-face intensities.
  Its own label still stops before the field of view does, so there is more.
- **The mandibular exposure is in too**, on the same pattern
  (`docs/transform-mandibular-to-centered.json`, already fitted for the arch
  work): 32.1 cm³ of mandible against `centered`'s 21.6, contributing 12.0 cm³
  as `FMA52748M`. All three volumes now supply geometry.

**So the order is: export what was already measured, then generate only the
remainder.** Re-segmenting the upper skull to the full FOV and bringing the
`maxillary` volume into the build is Fedora work on data already in hand, and
every millimetre it recovers is one that does not have to be invented. Do it
before fitting any template.

### A TMJ scan would MEASURE the part that matters — noted 2026-09-01

The operator's machine offers a small-FOV TMJ volume, left and right. That
captures the condyle and the coronoid process — precisely the anatomy this
section exists because we do not have, and the only part of the missing skull
with real clinical function. **It supersedes generating them.** The operator is
deliberately spacing the exposure out, which is the right call; nothing here is
urgent and everything below is about making sure that when it is taken it is
right the first time, so it never has to be taken twice.

**The trap, and it is not obvious: one TMJ volume contains two structures with
DIFFERENT rigid parents.** The condyle belongs to the mandible; the glenoid
fossa and articular eminence belong to the temporal bone, and so to the cranium.
CLAUDE.md's rule that one transform cannot serve both jaws applies here exactly:
that volume will need **two** registrations, and each needs its own overlap.

- **The condyle registers on the mandible**, and its handle is the RAMUS. So the
  FOV should be positioned to include as much ramus below the condyle as it can
  — that shared bone is the entire basis of the fit. A volume containing a
  beautifully resolved condyle and no ramus is unregisterable and therefore
  worthless to this atlas.
- **The fossa and eminence register on the cranium**, and that is the harder
  one, because the cranial bone we have is MID-FACE — anterior — while the fossa
  is posterior-superior. The overlap may be poor or absent. If the machine
  allows any latitude in positioning, favour including the zygomatic arch: it
  runs between the two and is the only plausible bridge.

**Measured now, so the FOV can be positioned rather than guessed** (atlas frame,
LPS mm — the point is the shape of the requirement, not the numbers themselves):

- The mandible plus ramus currently reaches **z 16.6** at the top, and the bone
  within 10 mm of that top sits at **y 12.4–23.5**, laterally around
  **|x| 35–45**. So a TMJ volume needs to reach INFERIORLY far enough to take in
  roughly the **top 10–15 mm of ramus below the condylar neck**. That is the
  whole mandibular registration handle; without it the condyle cannot be placed.
- For the fossa, the bridge exists: there are **18.5 k mesh vertices of cranial
  bone lateral of |x| > 32 mm**, spanning y −21.9 to 28.8 and z −7.1 to 67.3 —
  the zygomatic process region and posterior enough to be plausible overlap. So
  favour a position that catches the **zygomatic arch**, and the fossa has
  something to register against rather than nothing.

**Worth settling before the appointment:**

- **Match 0.16 mm isotropic** if the Vol. 1 protocol offers it, so it composites
  with the existing three without a resampling step.
- **Record the jaw position** — maximum intercuspation or rest — explicitly, and
  prefer whatever the existing volumes were taken in. Condyle-to-ramus is rigid
  either way, so the mandibular registration is safe; condyle-to-FOSSA is not,
  and two volumes in different positions would place the joint differently. That
  is interesting rather than fatal — it would show the joint in two positions,
  which is exactly what [Open and close the mouth](#open-and-close-the-mouth)
  wants — but it must be RECORDED, never averaged.
- **Both sides**, and note the mental foramen asymmetry already on record: the
  right mandibular canal centreline is the weaker of the two, so the right joint
  is the more valuable of the pair if only one were possible.
- **Export DICOM, not the vendor's viewer file.** The survey already found a
  Windows `.exe` shipped alongside the imaging data and correctly refused it.

**If it happens, this section shrinks to the cranial vault and the zygomatic
arch** — orientation context, the part the wishlist already calls cheapest to
fake and least at stake. The generation options below stay for that remainder.

### How to generate the remainder, in order of preference

*(For the condyle, fossa and eminence, see the TMJ scan above first — measuring
beats all three of these, and the whole argument of this atlas is that measured
anatomy is the point.)*

1. **Template morphed to the measured boundary.** Take a skull mesh and fit it so
   that where it overlaps measured bone it *matches* — then extrapolate outward
   from that fit. The generated skull is then this patient's size, proportion and
   asymmetry rather than a generic one, and it joins the measured mandible and
   maxillae without a seam. This is the only option that is genuinely
   "generative" rather than "borrowed", and it is the one worth the effort.
2. **A permissively licensed skull, registered and scaled.** Faster, and honest
   if labelled. **Licence trap:** BodyParts3D is CC BY-SA, and Invariant 3 means
   anything derived from it inherits ShareAlike. Pulling a skull from there would
   re-infect a tree the CBCT work deliberately freed. Source something
   public-domain or permissive instead, and keep it in the atlas-derived tree.
3. **Authored from scratch.** Most work, least benefit — a hand-modelled cranial
   vault teaches nothing the other two do not.

### The provenance problem is worse here than anywhere else

Every other structure in the atlas is measured, derived or schematic *as a
whole*. A generated skull is **measured and invented in the same mesh**, with the
join running through the middle of the mandible. Per-structure provenance is not
enough; this needs provenance **per region**, or the mandible starts asserting a
ramus height nobody ever measured.

Two things follow, and they are the interesting part of this item:

- **Draw the FOV boundary.** The extent of each 8 cm box is a real, knowable
  surface. Showing it — as a clip plane, a fade, or an outright change of
  material — turns "where the data stops" from a caveat into something visible.
  That is a better answer than a footnote, and it is the honest version of a
  feature that is otherwise pure decoration.
- **Never feed a generated skull into an extraoral DRR unlabelled.** A simulated
  panoramic or cephalometric radiograph needs far more skull than 8 cm, so it
  would be computed largely from invented bone — a fabricated radiograph of a
  real, identifiable person. Intraoral projections stay inside measured data and
  are fine; extraoral ones are not, and the difference must be enforced in code,
  not left to a label.

**What it needs:** the FOV audit (cheap, and possible today); then a skull source
with a licence that does not contaminate; then a fitting script. No new imaging —
the missing anatomy is missing permanently, since re-scanning to fill it would
mean irradiating a healthy person for an atlas.

---

## Re-derive the nerve courses from a primary anatomical source

The maxillary and terminal mandibular nerve courses were built against the
Wikipedia anatomy articles, and `provenance()` cites exactly that, because
citing what was actually used is the whole point of the field.

Upgrading the source is worth doing. **The trap is that it is not a citation
change.** Swapping `SRC.wikiSA` for a better reference without re-deriving the
geometry would be false attribution — it would credit a book for a course it did
not produce, which is worse than an honest citation of a weaker source. The work
is: re-check each course against the reference, adjust the geometry where they
disagree, *then* change the citation.

Candidates, and they are not equivalent:

| Source | Why |
| --- | --- |
| **Gray's Anatomy** | The obvious upgrade, and the 1918 edition is public domain — but it is a general anatomy, thin on the dental branches, and its plates predate the imaging that settled several of these courses. |
| **Netter's Head and Neck Anatomy for Dentistry** (Norton) | Written for this exact purpose. Almost certainly the better reference for the superior alveolar plexus and the infraorbital canal. |
| **Malamed, Handbook of Local Anesthesia** | The one to use if the [anaesthetic delivery](#local-anaesthetic-delivery-from-needle-to-numb-tooth) item is built, because it describes these nerves in terms of where a needle goes — which is what that feature needs and what a general anatomy does not give. |

Doing this *with* the anaesthesia item rather than before it would mean deriving
each course once, against the source that item needs anyway.

**Decided 2026-08-31: that is the plan.** The operator wants the courses
re-derived *before* the anaesthesia modelling rather than after, so the
derivation happens once against Malamed — the reference that feature needs — and
the citation follows the work instead of preceding it.

### Partly done 2026-09-01 — and the shape of the rest has changed

The maxillary trunks were re-derived against Malamed and are now **confined to
measured bone**. They had never been tested against bone at all: 72% of that
mesh lay outside it, a median of 3.5 mm and up to 10.1 mm out, floating in the
sinus. It is now 0.5 mm median and 1.2 mm maximum, which is the tube's own
radius — the centrelines are in bone. `SRC.malamed` is cited on that structure
only, because that is the only geometry actually re-derived against it. The tier
stays `schematic`: bounded by measured bone is not the same as observed.

**Two of Malamed's landmark constructions cannot be anchored to this scan, and
both were checked, so nobody spends the time again:**

- **The infraorbital canal does not resolve.** Filling the upper-skull label per
  slice and taking the interior voids returns the sinuses and the nasal cavity
  (aspect ratios 1.1–1.7) and no thin tube anywhere. The infraorbital foramen
  therefore cannot be measured; placing it from the orbital rim plus a published
  5.8–7.3 mm offset is the best available, and would be *derived*, not measured.
- **The mandibular foramen construction needs bone that is not there.** Malamed
  places it ~19 mm below the coronoid notch and ~2.75 mm behind the ramus's
  anteroposterior midpoint. Both need the ramus's posterior border, and the
  ramus is still cut by the field of view at y 23.7 against a box edge of 23.85
  *even with the mandibular exposure registered in*; the condyle was never
  inside any of the three FOVs. The superior-border profile rises to the
  coronoid and then stops, so there is no second peak to put a notch between.

**What is left of this item** is the mandibular terminal branches and the
palatal nerves, plus deciding whether an offset from a measured orbital rim is
worth having for the infraorbital foramen. The maxillary trunk topology is done.

---

## Scan the gingiva, and stop deriving it — SCHEDULED, ~late Sept 2026

The gingiva is currently a collar lofted from the measured CEJ, and its
provenance says plainly that the gingiva itself was never imaged. It does not
have to stay that way: unlike the condyles, this tissue is *available* — it is in
the operator's mouth, and CBCT's inability to see it is a contrast limitation,
not a geometric one.

### Planned, not hypothetical

**Agreed 2026-08-31: an intraoral scan is happening.** Chairside access to a
scanner is arranged for roughly **late September 2026**, so this is planned work
rather than a wish. The photogrammetry section below stays as the fallback if the
scanner is unavailable on the day.

Worth settling before then, because a second attempt is a month behind the first:
export **STL or PLY, not a proprietary case file**, capture both arches fully
including the vestibular depth rather than stopping at the gingival margin, and
take the scan **before any scaling or polishing** — both inflame marginal tissue,
and the atlas wants the gingiva at rest.

### An intraoral scan beats photographs, by a lot

If a chairside scanner is reachable — Trios, iTero, Primescan — **that is the
answer**. It captures teeth and gingiva together as one surface at 20–50 µm,
which is better than the CBCT's own 160 µm, and it exports STL directly into the
existing pipeline. Crucially it captures the **gingival margin**, which is the
clinically loaded part and the thing the lofted collar can only approximate.

Registration is already solved by the data: the tooth crowns appear in both the
scan and the CBCT, and the crowns are measured in both. Fit crown to crown by ICP
and the gingiva arrives in the atlas frame for free, correctly scaled. That is a
far better-posed problem than the volume-to-volume registrations already done.

### Photographs are the fallback, and still worth it

Multi-view photogrammetry would work, with caveats worth knowing before shooting:

- **Cross-polarise if possible.** Wet gingiva is specular, and specular
  highlights move with the camera, which is exactly what breaks feature matching.
  A polarising filter plus a polarised light source removes them.
- **Many overlapping views**, 30–60 around the arch, rather than a few good ones.
- **Scale comes from the teeth**, not from a ruler — photogrammetry is
  scale-free, and the crowns are already measured.
- **Retraction changes the answer.** Pulling the lip to see the gingiva moves the
  vestibule and can blanch and displace the marginal tissue. The attached gingiva
  is fairly safe; alveolar mucosa photographed under retraction is not the shape
  it has at rest.
- **Only the visible surface.** Neither photographs nor an intraoral scan see
  below the margin — the sulcus, the attachment and the biologic width stay
  underived. The CEJ is measured and the margin would be measured; what is
  between them remains an inference.

### What it would change

- **Gingiva moves from `derived` to `measured`**, with a method naming the
  modality and the crown-based registration — the first structure in the atlas
  measured by something other than the CBCT, which the provenance field is
  already shaped to express.
- **Real colour.** The gingiva is a flat pink material today. Photographs carry
  actual tissue colour, and in a dental atlas that is anatomy, not decoration:
  biotype, pigmentation and the difference between attached gingiva and alveolar
  mucosa are all visible and all teaching material.
- **Recession and papilla fill become observed** rather than lofted, which is the
  difference between an atlas that shows a gingival margin and one that shows
  *this* gingival margin.

**What it needs:** the imagery, then a photogrammetry or mesh-registration step
and an ICP fit to the measured crowns. No new radiation, which is the other
reason this is a good trade — [the skull item](#the-rest-of-the-skull--generating-what-the-fov-never-saw)
notes that the missing hard tissue is missing permanently, because re-scanning to
fill it would mean irradiating a healthy person for an atlas. Soft tissue has no
such constraint.

---

## Smaller things

- Retopologise the apical spikes on the tooth surfaces — an imaging limit, not a
  code bug, but it looks like a defect.
- The coronal pulp chamber is under-represented in multi-canal teeth: it is one
  space split between canal basins. Model it explicitly.
- Per-basin dentin reference in the pulp tracker, to close the systematic bias
  documented in [cbct-whole-mouth.md](cbct-whole-mouth.md).
