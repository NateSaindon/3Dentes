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

## Smaller things

- Retopologise the apical spikes on the tooth surfaces — an imaging limit, not a
  code bug, but it looks like a defect.
- The coronal pulp chamber is under-represented in multi-canal teeth: it is one
  space split between canal basins. Model it explicitly.
- Per-basin dentin reference in the pulp tracker, to close the systematic bias
  documented in [cbct-whole-mouth.md](cbct-whole-mouth.md).
