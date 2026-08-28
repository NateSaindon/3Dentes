# Phase 2 — closing the anatomy gaps

The alpha's ceiling is the source data: BodyParts3D gives external morphology and
nothing else. Everything below is anatomy that has to be **authored**, which is
where the real cost lives. Modelling work is planned for the Fedora desktop
(Blender, real mouse, GPU headroom) rather than the ThinkPad.

Roughly in order of value-per-hour for a clinical user.

## 1. Internal tooth structure — enamel, dentin, pulp

The biggest gap. Without it this is a model of teeth, not dental anatomy.

**Option A — procedural offset (fast, approximate).** Shrink each tooth mesh
inward by a per-region distance to generate a dentin shell, and again for a pulp
chamber. Mesh offsetting is well-supported (Blender's Solidify, or an SDF
round-trip for a cleaner result on concave occlusal surfaces).

- *Pros:* covers all 28 teeth in roughly a day; automatable in the existing
  pipeline; anatomically suggestive and genuinely useful for teaching shape.
- *Cons:* not textbook-exact. Pulp horns will not sit where they truly sit, and
  canal counts will follow crown shape rather than real root canal anatomy. For
  endodontic study this is **not** good enough, and would need labelling as
  schematic.

**Option B — modelled from published morphology (slow, correct).** Author pulp
chambers and canals per tooth in Blender against endodontic references, ideally
with micro-CT literature for canal configurations (Vertucci types).

- *Pros:* the only version trustworthy for endo.
- *Cons:* days per arch, and it needs real anatomical judgement — this is where
  your expertise is the bottleneck, not the software.

**Recommendation:** do Option A first and label it schematic. It makes the app
substantially more useful immediately and establishes the layer/cross-section UI
that Option B would reuse. Upgrade individual teeth to Option B as needed.

## 2. Nerve pathways

Inferior alveolar, lingual, mental, and the greater/lesser palatine. High
clinical value — these are injection landmarks, not just anatomy.

Hand-authored as splines rather than meshes: a curve through the mandibular
canal from the mandibular foramen to the mental foramen, swept to a tube at
render time. Both foramina are visible landmarks on the existing mandible mesh,
so the path can be anchored to real geometry rather than invented.

Cheap relative to its value — likely the best return in Phase 2 after pulp.
A cross-section or transparency mode through the mandible is needed to see it.

## 3. Third molars

Four missing teeth. Either model them from morphology references, or adapt the
existing second molars (a scaled and reshaped second molar is a defensible
starting point, given third molar morphology is highly variable anyway).

Note the licensing consequence: adapting an existing BodyParts3D mesh makes the
result a **derivative**, so it inherits CC BY-SA. Modelling from scratch does
not. Keep them in separate directories.

## 4. Periodontal ligament and lamina dura

A thin shell between root and socket — a good candidate for the same offsetting
approach as the dentin shell, generated from the root surface. Mostly valuable
as context for perio work, and cheap once the offsetting pipeline exists.

## 5. Cross-sections

A clipping plane through the model, driven by the existing layer system. Needs
capped cross-sections (Three.js gives clipping planes but hollow shells look
wrong when cut — the standard fix is a stencil-buffer cap pass). Worth doing
once there is internal structure worth cutting into; pointless before then.

## 6. Soft tissue

Tongue, salivary glands, TMJ disc. None are in BodyParts3D. Lower priority
unless the atlas is meant to cover the oral cavity broadly rather than the
dentition specifically.

---

## Licensing, before any modelling starts

The BodyParts3D meshes are CC BY-SA 2.1 JP. **Anything derived from them by
editing inherits ShareAlike.** Anatomy authored from scratch does not.

Keep the two physically separate in the repo (`assets/derived/` vs
`assets/original/`) so the licensing story stays clear if this is ever published
more widely or commercialised. Deciding this after a month of Blender work is
much worse than deciding it now.

## Also worth doing, independent of anatomy

- **`EXT_meshopt_compression`** if the iPad load feels slow (4.77MB today,
  probably ~1.5MB compressed).
- **Quiz mode** — hide labels, ask for a tooth by notation. The odontogram and
  selection state already provide everything needed; this is mostly UI.
- **Deep-linkable selection** (`?tooth=3`) so a specific structure can be shared
  or bookmarked.
