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

1. **Register the `mandibular` volume onto `centered`** (plan step 6, now
   justified by the truncated canal) and rebuild the canal continuous, foramen to
   foramen.
2. **Pulp as tissue** — relabel, add the lining and neurovascular core, and wire
   the apical foramina to the IAN.
3. **Generate gingiva** from CEJ and alveolar crest.
4. **PDL shell.**
5. **Muscles fitted to measured attachments; tongue authored.** Blender, and last.

See [wishlist.md](wishlist.md) for what this anatomy would later enable.
