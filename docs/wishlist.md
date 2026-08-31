# Wishlist

Ideas captured for later. Nothing here is scheduled, and nothing here should be
built before the Phase 3 anatomy it depends on exists. Recorded so they are not
lost, with a note on what each actually needs.

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

## Smaller things

- Retopologise the apical spikes on the tooth surfaces — an imaging limit, not a
  code bug, but it looks like a defect.
- The coronal pulp chamber is under-represented in multi-canal teeth: it is one
  space split between canal basins. Model it explicitly.
- Per-basin dentin reference in the pulp tracker, to close the systematic bias
  documented in [cbct-whole-mouth.md](cbct-whole-mouth.md).
