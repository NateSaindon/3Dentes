# Research notes — what exists, and why this project was built the way it was

Written 2026-08-27, at the start of the project. Preserved so the reasoning
behind the alpha does not have to be rediscovered.

## The landscape

There is no good 3D dental anatomy application for Linux. The polished products
— Complete Anatomy (3D4Medical), Primal Pictures, and the various dental-school
atlases — are commercial and ship for Windows, macOS and iOS only.

**A warning about searching for this.** Queries for "open source dental anatomy
3D software" return confident, detailed descriptions of an **"OpenAnatomy Dental
Atlas"**, said to show "teeth, jaws, nerves and bone structures in 3D" and to be
used in dental schools. It does not exist. Those pages (dentsoftpro.com,
dentiit.com, toolsdent.com and similar) are SEO content farms generating
plausible fiction. The real Open Anatomy Project (openanatomy.org) publishes six
atlases — brain, inner ear, knee, head and neck, abdomen, thorax — and none of
them is dental. Verify before chasing.

Free individual tooth models exist on Sketchfab, CGTrader, MakerWorld and the
NIH 3D Print Exchange, but they are one-off assets with inconsistent licensing
and no shared coordinate system — assembling a full dentition from them means
positioning every tooth by hand.

## Why BodyParts3D

[BodyParts3D](https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html),
from the Database Center for Life Science, is what makes the project cheap
rather than expensive. Verified directly rather than taken on description:

| | |
|---|---|
| Individually segmented permanent teeth | **28** (all but the third molars) |
| Supporting structures used here | mandible, L/R maxilla, L/R palatine, upper/lower gingiva, 10 muscle parts |
| Total | 45 meshes, 347,826 triangles, 17MB of STL |
| License | CC BY-SA 2.1 Japan |
| Indexing | FMA ontology ids, so every mesh is unambiguously named |

**The decisive property is that everything shares one coordinate system.** A
bounding-box check before any code was written confirmed the upper central
incisor at z 1464.9–1489.8mm and the lower central at z 1442.0–1465.9mm —
occluding correctly, teeth seated in their sockets. Positioning 28 teeth by hand
would have been the single largest cost in the project, and it was already done.

Coordinates are millimetres in a whole-body frame: z is height above the floor
(the head sits near z=1470mm), anterior is −y, and **anatomical right is −x**.
That last fact is asserted at build time; see `checkLaterality`.

## What the source data does not contain

Confirmed by grepping the full BodyParts3D parts list, not assumed:

- **No third molars.** 28 teeth.
- **No internal tooth structure.** There is a generic "crown of tooth" entry but
  no enamel, dentin or pulp geometry. External morphology only.
- **No nerves at all** — no trigeminal, inferior alveolar, lingual or mental.
- **No periodontal ligament, tongue, TMJ disc, or salivary glands.**

Also relevant clinically: BodyParts3D is derived from a **single individual**, so
root counts and curvature are that person's rather than a textbook composite.

These absences are the entire Phase 2 scope. They are stated on screen in the app
because a tool that looks like a clinical reference while quietly omitting the
pulp and the inferior alveolar nerve is worse than one that says so.

## Why a web app

Targets are Arch (ThinkPad), Fedora Workstation (desktop) and iPad. A web app
covers all three from one codebase with no porting, and a PWA install gives the
iPad an offline home-screen app. 348k triangles across 45 draw calls is
comfortably within what mobile Safari handles at 60fps, so nothing about the
anatomy pushed toward a native renderer.

## Performance and payload

| | |
|---|---|
| Triangles | 347,826 |
| Vertices after exact welding | 173,956 (from 1,043,478 — 83.3% reduction) |
| Built `.glb` | 6.29MB (8.38MB before 16-bit indices) |
| Over the wire, gzipped | 4.77MB |

Float geometry gzips poorly, hence only ~25% off. `EXT_meshopt_compression`
would likely reach ~1.5MB and is the obvious next step **if** the iPad load time
proves annoying — it was deliberately skipped for the alpha because the runtime
decoder wiring is a known Vite footgun and the win was speculative. Measure
first.
