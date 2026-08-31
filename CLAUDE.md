# Notes for Claude Code — 3Dentes

Interactive 3D atlas of human oral anatomy. Vite + Three.js, no framework.
Deploys to https://natesaindon.github.io/3Dentes/ from `main` via Actions.

**This repo is public**, and as of 2026-08-29 that includes the operator's own
CBCT-derived anatomy — they have explicitly consented to it. See "Next on the
docket" below. This is not a general licence: no third-party patient data, ever.

**As of 2026-08-31 the CBCT set is the ONLY geometry here.** The BodyParts3D
alpha, its `assets/source/` tree, `tools/fetch-assets.mjs`, the `TOOTH_SOURCE`
switch and `LICENSE-ASSETS` are all gone — every mesh it supplied had been
replaced by measured anatomy, so the attribution and the ShareAlike inheritance
went with it. Do not reintroduce a BodyParts3D dependency without saying so out
loud: it would put a copyleft obligation back onto a tree that is now free of
one. See ATTRIBUTION.md.

## Machines

- **Arch ThinkPad** — where the alpha was built. Fine for app work.
- **Fedora Workstation desktop** — where Phase 2 modelling happens (GPU headroom,
  real mouse). Blender is **not installed there yet**; install when that work
  actually starts, not before.

## Commands

```bash
npm install
npm run build:assets   # STL -> public/dentition.glb + public/teeth.json
npm run dev            # http://localhost:5173/3Dentes/
npm run dev -- --host  # reachable from the iPad on the same network
npm run build && npm run preview
```

`public/dentition.glb` and `public/teeth.json` are gitignored build products.
Run `build:assets` after cloning or nothing loads.

## Invariants — do not break these

1. **The laterality assertion in `tools/build-assets.mjs`.** Anatomical right is
   negative x. The build fails if any structure labelled left/right sits on the
   wrong side. An atlas that confidently mislabels a side is worse than no atlas.
   If it ever fires, the model is mirrored — fix the pipeline, don't relax the check.
2. **Exact vertex welding.** `weldExact` merges only bitwise-identical vertices.
   Never add a distance tolerance: it would round off cusp tips and occlusal
   fissures, which is precisely the anatomy that matters here.
3. **The anatomy is not open-licensed.** Code is MIT; everything under
   `assets/cbct/` (and the `dentition.glb` built from it) is a named living
   person's medical imaging, published for this project with consent and under
   no reuse grant. Do not add a licence to it, and do not treat "the repo is
   public" as one. The former CC BY-SA obligation from BodyParts3D is retired
   along with those meshes — keep it that way; anything borrowed in later brings
   its licence with it and needs its own tree.
4. **The source-data caveat stays visible in the UI.** The `.caveat` block in
   `index.html`. The user is a dental professional; a tool that looks like a
   clinical reference while omitting pulp and the inferior alveolar nerve must say so.
5. **The tooth identity check in `tools/tooth-morphology.mjs`.** Tooth numbering
   must agree with tooth morphology, or the build fails. Laterality (1) catches a
   structure on the wrong SIDE; this catches one at the wrong POSITION, which the
   notation derivation cannot reveal because it derives all three notations from
   the same triple and so is self-consistent whatever that triple says. Every
   test is ORDINAL — largest two teeth in the quadrant, longest non-molar, most
   roots — never a threshold in millimetres, because this is one person's
   dentition and a build asserting their molar exceeds 800 mm³ would be asserting
   something about *them* rather than about the labelling. If it ever fires,
   suspect the manifest, not the check; `npm test` proves the check still bites.
6. **Every structure states how it was made.** `provenance()` in
   `tools/manifest.mjs` must return a tier, a method and (where anything is
   approximated) a source, for every structure; the build fails otherwise. This
   is the machine-readable form of invariant 4 — a caveat describes the *build*,
   a provenance field describes the *object the user just clicked*, which is
   where the question actually gets asked. `tier` describes the geometry AS
   DRAWN, never the best evidence behind it: the inferior alveolar nerve follows
   a measured canal but what is rendered is a tube of chosen calibre on that
   centreline, so it is `derived`, and the method says which part was measured.
   Overclaiming a tier because some input was measured is the exact failure this
   field exists to prevent.

## Deployment

`.github/workflows/deploy.yml` runs `build:assets` with no environment. It used
to need `TOOTH_SOURCE=cbct`, and without it the deploy published the BodyParts3D
alpha while every local review ran against the CBCT build — the site was a
different model from the one being approved and nothing said so. That whole class
of bug went away with the second build; there is one model now.

Every structure in `tools/manifest.mjs` must have a mesh in `assets/cbct/stl/`.
Listing one that does not fails the deploy with ENOENT, which is how the nerves
broke the build once. Add the STL first.

## Architecture

FMA ids are the join key everywhere — source filename, glTF node name, and
`teeth.json` key are all e.g. `FMA55697`.

`tools/manifest.mjs` is the single source of truth: which structures, their
layer, anatomical side, and the notation derivation. Universal/FDI/Palmer are
**derived** from arch/side/position, never hand-typed — 28 hand-entered tooth
numbers is 28 chances to mislabel a tooth.

Gotchas worth not rediscovering are in the README's "Notes from building it"
(flat-vs-smooth normals, 16-bit indices, see-through picking).

## Status

**Alpha: done and deployed** (2026-08-27). 28 permanent teeth, jaws, gingiva,
muscles of mastication; click selection, odontogram with camera flight, layer
opacity, isolate, PWA offline install.

### Closed: the Universal → FMA mapping (2026-08-31)

This was the standing open item — the mapping was derived and self-consistent and
had been cross-checked against an independently written table, but consistency is
not correctness, and nothing tested it against anatomy.

`docs/cbct-plan.md` predicted the test: per-tooth CBCT geometry is independent
evidence, because tooth-type morphology is unmistakable. It is now run on every
build (invariant 5) and **the mapping is correct** — all 28 teeth, both checks.

What the geometry says, for the record:

- **Arch order.** Ordering each arch by polar angle about its own centroid gives
  a strictly monotonic Universal sequence: maxillary 2→15, mandibular 31→18, no
  inversions, gaps even at 22-25° and the single wide gap falling across the open
  posterior of the horseshoe where the third molars are missing.
- **Molars separate cleanly.** The two largest teeth in every quadrant are its
  molars, with a gap of 673 → 1076 mm³ between the largest non-molar and the
  smallest molar across the whole dentition. Root count agrees independently:
  read at 70% of the way from cusp tip to apex, every molar divides and no other
  tooth does. Read at 55% it is unreliable — some furcations have not opened and
  canines read two loops through the cervical constriction — so the depth matters.
- **Canines are the longest non-molar** in all four quadrants (22.7, 21.7, 25.9,
  26.6 mm), which anchors position 3 and separates the incisors in front from the
  premolars behind.

### Next on the docket — CBCT

The plan is to replace BodyParts3D hard tissue with segmented CBCT the user
supplies. This is the main Phase 2 thrust and supersedes several options in
`docs/phase-2-options.md`. **Read [docs/cbct-plan.md](docs/cbct-plan.md) before
starting** — it is authoritative for the dataset, the registration strategy, the
artifact map and the first-session steps.

The four things from it that matter most:

- **There are three volumes, not one** — central, mandible-focused,
  maxilla-focused — and they are **three separate exposures**. They do not share
  a coordinate frame, and the mandible moved between them.
- **Register in voxel space, fuse in mesh space.** CBCT gray values aren't
  calibrated HU, so a spliced volume has two intensity regimes and no threshold
  works across the seam. Two masked rigid transforms onto the central volume;
  segment each arch in its native grid; composite the meshes, not the voxels.
- **The laterality assertion does not protect against a globally mirrored
  volume** — it only catches a label on the wrong side. With bilateral crowns on
  19 and 30 and no third molars, there is no asymmetric landmark to fall back on.
  Derive L/R from `ImageOrientationPatient` (DICOM LPS: anatomical right is
  negative x, matching the atlas convention) and confirm with the user.
- **Do not run the vendor `.exe`** that ships alongside the imaging data. It's a
  Windows viewer, irrelevant on Fedora, and unnecessary — DICOM is an open standard.

The privacy question that used to gate this work is **settled: public is
approved.** De-identify headers anyway.

### CBCT: where things actually stand (2026-08-29)

The USB has been surveyed and a pilot tooth segmented. **Two documents now sit
between you and `cbct-plan.md`, and they win where they disagree with it:**

- **[docs/cbct-survey.md](docs/cbct-survey.md)** — what is really on the disc.
  Read it before touching the data. Four of the plan's premises were wrong:
  all three volumes are the *same* 0.16 mm isotropic resolution and FOV (not
  focused, higher-res); the **maxillary volume truncates the upper crowns** and
  is a sinus/root volume, not an upper-arch source; **`centered` is the only
  volume with both complete arches** and should be the primary segmentation
  source, not just the registration anchor; and it was acquired **2025-06-27**,
  fourteen months before the other two.
- **[docs/cbct-pilot.md](docs/cbct-pilot.md)** — tooth 9 segmented end to end,
  what worked, and two traps that cost real time (see below).

**Laterality is resolved.** The operator confirms the septum deviates right,
matching the headers' LPS reading. The volumes are not mirrored.

Working data is in `~/projects/3Dentes-cbct/` and is **not** committed — see the
`.gitignore` note. Regenerate with `tools/cbct/prepare.py`.

Three things worth not rediscovering:

1. **A tooth cannot be thresholded out of its socket.** Root dentin and alveolar
   bone overlap in density and neighbours touch at their contacts. Use the
   marker-based watershed in `tools/cbct/segment_tooth.py`, and seed **bone** as
   its own basin or the result leaks up the socket.
2. **The watershed basin has the pulp cut out of it**, and 3D `fill_holes` will
   not close it, because the canal opens at the apical foramen. Fill **per axial
   slice**. Any analysis of interior anatomy against an unfilled mask will
   confidently report that the canal does not exist. It does.
3. **Mesh from grey levels, not the binary mask.** Marching cubes on a mask
   terraces at 0.16 mm however much you smooth it.
4. **The pulp cannot be thresholded at all**, at any setting — below ~3 voxels
   wide, partial volume means no voxel ever reaches pulp density. Measure the
   lumen by integrating the intensity deficit across each cross-section, which
   survives sub-resolution blurring. `tools/cbct/pulp_model.py` does this and
   recovers tooth 9's canal at 20.4 mm³ with a 0.33 mm apical foramen. Do not
   "fix" it back into a threshold.

### Whole-mouth pipeline (2026-08-29)

**[docs/cbct-whole-mouth.md](docs/cbct-whole-mouth.md)** supersedes the
hand-seeded per-tooth approach. DentalSegmentator runs standalone (no Slicer) in
8 s on the GPU and gives all 28 teeth plus the mandibular canal; the arch is
split by dynamic programming over arc length against a tooth-width prior; pulp is
modelled per canal by intensity-deficit integration. Both arch maps are
operator-verified.

Four things worth not rediscovering:

4. **DentalSegmentator is per-CLASS, not per-instance** — "Upper Teeth" is one
   label. Its masks are already *solid* (pulp inside), so they need no per-slice
   fill.
5. **Do not split the arch by 3D shape.** A distance-transform watershed peaks
   per cusp and per root, not per tooth. Teeth are sequential *along the arch*;
   split by arc position.
6. **When capping a count by an anatomical prior, fold the surplus in, never
   drop it.** Dropping surplus canal tracks cost tooth 9 a third of its pulp.
7. **The pulp count is a prior; the volume is a measurement.** An extra canal
   will be neither found nor flagged.
8. **Any function that works in a cropped sub-volume must return WORLD
   coordinates, not indices.** This bug class has now appeared three times
   (`pulp_all.py` twice, `landmarks.py` once), the last time two steps after
   being documented here. Restating it does not work; make the boundary
   impossible to cross wrongly. `pulp_all.py` omitted it and placed all 28 pulp
   meshes at the wrong point in the volume. Nothing in the *numbers* looked
   wrong -- volumes and diameters are counts and differences, so they stayed
   correct -- and it surfaced only when nerve branches were wired to the apices
   and a lower-LEFT molar's apex came out on the right side of the head. When a
   geometry bug cannot change any scalar you are printing, print a coordinate.

### Pulp geometry, settled against hand-shaded ground truth (2026-08-29)

The operator hand-shaded all 14 exported slices of tooth 14 (`shade-14/`, via
`tools/cbct/shade_kit.py`). That is the ground truth; `tools/cbct/pulp_solid.py`
is fitted to it and scores **Dice 0.804** at **57.0 mm3** against their 56.9 mm3.

9. **One threshold cannot find a canal that narrows.** Inside the shading the
   median is 500 HU, matching the measured `pulp_density_hu` -- the density model
   was never wrong. But the apical canal READS 890-1086 HU, because under three
   voxels wide every voxel is a mixture. Lowering the cut until the apex appears
   floods the crown (318 mm3, precision 0.28). The cut must **taper coronal to
   apical**; that is the only family that beat a flat cut (0.804 vs 0.763).
   Hysteresis is *worse* (0.664): at a low enough cut everything connects, so
   connectivity constrains nothing.
10. **Never filter components by a fraction of the largest.** Apical to the
    furcation a molar has three separate canals, each tiny beside the chamber
    they are compared against, so a relative floor deletes exactly the anatomy in
    question. Use an absolute voxel count.
11. **Calibrate the mask you actually ship.** The volume search fitted an
    intermediate, and the closing and fill *after* the fit added 56% -- the
    delivered tooth missed the target it had just been fitted to. Worse, the
    search then compensated by starving the roots, which inverted the shape:
    Dice fell to 0.662 while every isolated ingredient was better than before.
12. **The modelled tube is measurement, not geometry.** Once the cut tapers, the
    threshold reaches further apically than the tube does, and unioning the tube
    only adds volume in the wrong place (-0.03 to -0.06 Dice, monotone across
    every cut depth tested). Likewise `binary_closing(iterations=2)` costs
    0.05-0.12. `pulp.json` keeps the measured lumen; the mesh no longer uses it.
13. **The operator's pulp is ~2.1x the strictly-measured lumen** -- 56.9 mm3
    shaded against 26.8 mm3 of lumen on tooth 14 (`SHADING_SCALE`). Both are
    right about different things: the deficit integral recovers the radiolucent
    lumen, while predentin and the partial-volume shell read denser than pulp but
    ARE pulp tissue. This is why the old model looked like "thin filament lines":
    `pulp.json` models N tubes and has **no chamber term at all**, so a 12.9 mm2
    chamber could never be represented. Note the scale is measured on ONE tooth;
    widen the ground truth before trusting it far. Whole-dentition total is now
    1503 mm3, against ~760 mm3 of published *lumen* -- consistent with the 2.1x,
    but the number to re-check first if anything looks fat.

### Apical foramina and canal continuity (2026-08-29)

`tools/cbct/pulp_connect.py` runs after `pulp_solid.py`. It joins each tooth's
pulp into ONE body and carries each root's canal to a modelled apical foramen.
All 28 teeth are now a single component; only 19.4 mm3 (1.3%) is added, so this
is almost entirely joining what was already measured.

14. **Thresholded pulp arrives in pieces, and the pieces are real.** Tooth 12's
    largest fragment held 59.9% of its pulp and stopped 2.9 mm short. Between two
    fragments the canal certainly exists, so the BRIDGE path is recovered from
    the image by routing along the darkest route through dentin (`MCP_Geometric`
    on a squared intensity cost). Past the last radiolucent voxel nothing is
    resolvable and the continuation is modelled. `pulp-connect.json` records
    which voxels are which -- do not let that distinction collapse.
15. **Do not place a foramen by cheapest exit.** Routing to the lowest-cost
    surface voxel put foramina a mean 2.85 mm from the apex against a literature
    mean of 0.52 (worst 7.46), because a short lateral path through thin dentin
    beats running the length of the canal -- it finds LATERAL canals. Capping the
    search radius just moved the answers onto the cap. Extrapolate the canal's
    own measured trajectory instead (SVD over its last 1.6 mm, then march to the
    surface).
16. **Do not tune a placement to the statistic you then validate it against.**
    Narrowing the search window until the mean hit 0.52 mm was available and
    would have been circular. The trajectory method has no parameter tied to
    apex distance, which is what makes the agreement worth anything:
        mean 0.55 mm (lit. 0.52), median 0.51, range 0.00-2.17 (lit. 0.2-2.0),
        86% deviating >0.2 mm (lit. ~85%)
17. **Apical deltas are below this scan's resolution and are NOT modelled.**
    9.7% of teeth (molars 15-16.5%), median branch diameter 132 um against a
    160 um voxel. Drawing one would render it at ~4x its true calibre.

Lower foramen to the MEASURED mandibular canal: molars 1.6-5.2 mm, rising
monotonically to 22-26 mm at the incisors -- the canal ends at the mental
foramen and the anteriors are supplied by the incisive branch. Any neurovascular
link must treat those two regimes differently.

### Meshing thin anatomy (2026-08-29)

The operator reported pulp "islands" still floating beside teeth 2, 3, 4, 14, 15
AFTER `pulp_connect.py` reported every tooth as one piece. Both were true: the
MASK was one component and the MESH was not, on 24 of 28 teeth.

18. **Check connectivity on the artefact you ship, under FACE connectivity.**
    26-connectivity counts a corner touch as joined; a surface does not. Under
    6-connectivity the masks held 11-43 pieces -- a main body of 10-20k voxels
    and specks of 1-256. Those specks are threshold noise and are now dropped
    (`despeckle`); a bridge path is re-walked one axis at a time (`face_path`)
    so it cannot be joined only at a corner.
19. **Decimation is what severs thin canals, and it is not monotone.** Both
    earlier suspicions were wrong -- lowering the isolevel never reached one
    component even at 40% volume inflation, and thickening the connectors added
    41 mm3 to tooth 2 and still left three pieces. `marching_cubes` returns ONE
    surface and Taubin preserves it; quadric collapse from ~24,500 to 3,500
    triangles pinches off the one-voxel canals. One tooth split at 3,500, held
    at 5,000, split again at 7,000 and 10,000. `decimate_connected` therefore
    tries increasing budgets and takes the first that verifies. Do not replace
    it with a fixed number.
20. **`mesh_field` floors every mask voxel just above the isolevel.** Smoothing
    a one-voxel tube at sigma 0.9 peaks near 0.33, so the canal disappears from
    the mesh while remaining in the mask. The floor is applied only where the
    smoothed value fell below it, keeping the hard-clamp terracing warned about
    above confined to thin canals.

All 28 pulp meshes now verify as a single connected surface (167k triangles).

21. **Bridge only across gaps a canal could plausibly have.** Connecting every
    island drew thin strings out of the chambers of 19 teeth. The span
    distribution separates cleanly: genuine partial-volume dropouts bridge in
    0.23-1.37 mm (mean 0.78), while the rest ran to 8.06 mm -- paths through
    solid dentin to isolated blobs, which is beam hardening between dense roots
    thresholding as pulp, not anatomy. `MAX_BRIDGE_MM = 1.5` sits in the gap;
    40 islands (8,732 voxels, 36 mm3) are dropped rather than bridged, because
    leaving them unbridged would put floating debris back in the mesh.
    Real accessory canals are NOT what these were: they run canal-to-SURFACE and
    average 132 um, below the 160 um voxel.

22. **Span alone is the wrong discriminator for an island; FORM is.** The
    1.5 mm cap deleted the MB canals of teeth 3 and 14 outright -- an MB canal
    detaches from the chamber in the threshold mask because its orifice is the
    narrowest part, so it presents exactly like a distant artefact. An island
    that is long, thin (aspect >= 2.5, length >= 1.5 mm) and points apically is
    a canal and gets up to `CANAL_BRIDGE_MM`; a compact blob still gets 1.5.
23. **Every root has a canal, and the threshold does not always find it.**
    Tooth 14's three roots held 990, 69 and 4 pulp voxels -- the palatal canal
    and chamber absorb the whole calibrated volume budget, so MB and DB never
    appear at all. Nothing to bridge, no trajectory to extrapolate. A canal is
    therefore ASSERTED in any root left under `MIN_ROOT_PULP`, the way
    CANAL_COUNT is asserted in pulp_all.py. Keep the three claims separate:
    existence is an anatomical prior, the route is the measured darkest path,
    the calibre is modelled.
24. **The isolevel floor must apply ONLY to thin voxels.** Flooring every mask
    voxel -- chamber walls included, whose surface sits near 0.5 by definition
    -- shoves the isosurface out by an uneven fraction of a voxel and pebbles
    the surface. That is the terracing warned about above, and it is what made
    the premolar and incisor pulp look crunchy. Thick anatomy is the Gaussian's
    job; only canals, which have no smooth rendering at 0.16 mm, are clamped.

25. **The canal must NOT be thresholded -- rule 4, which I broke.** Tooth 9, a
    maxillary central incisor with exactly ONE canal, had more than one blob in
    63% of its axial slices (up to 5); tooth 22, a mandibular canine, in 70%
    (up to 9). Because the volume is calibrated, the budget was being SPENT on
    that scatter. The pulp is now built as CHAMBER (thresholded then opened --
    it is wide enough to resolve, and opening deletes speckle, which is thin by
    nature) UNION CANAL (the smooth swept tube along the centreline pulp_all.py
    measured). Apical multi-blob fell to 6% and 2%. No amount of smoothing fixes
    wrong geometry; do not reintroduce a thresholded canal.
26. **Cap canal calibre with anatomy, not with the volume budget.** Scaling the
    tube until the union hit the calibrated volume gave molar canals
    0.65/0.70/0.69/0.74 mm equivalent diameter at 1/2/3/4 mm from the apex
    against micro-CT's 0.29/0.39/0.40/0.44 -- a fat canal standing in for volume
    that belongs in the chamber. `CANAL_ENV_MM` clamps it; ratios are now
    1.14-1.43. NOTE the reference series is molar-MESIAL-specific: anterior
    canals are legitimately wider, so their higher ratio is not an error.

27. **`total_lumen_mm3` is over-measured on 13 teeth, and it renders as a
    coronal bulge.** The operator flagged 13 bulging chambers. Sorting all 28
    teeth by lumen as a FRACTION of tooth volume separates their list exactly:
    their reference teeth 2.83-3.67%, molars 1.69-3.57%, their flagged teeth
    4.06-8.17% -- a clean gap between 3.75 and 4.06, no overlap. A clinician's
    eye and a ratio neither party chose in advance agreeing on the same
    partition is what makes this a measurement error in pulp_all.py's deficit
    integration (it over-integrates on single-rooted teeth with wide canals),
    not a rendering complaint. `PULP_FRACTION_MAX = 0.039` caps the target until
    the tracker is fixed; molars and the reference teeth fall under it untouched.
28. **Split the volume budget, then FIT THE TUBE TO THE CHAMBER.** Calibrating
    the threshold against the whole pulp volume and adding the canal on top made
    the chamber absorb the entire budget in the crown -- the bulge. But splitting
    it and then rasterising the tube at a nominal scale left the sum
    unconstrained: 2313 mm3 against a 1495 target. Chamber is calibrated to
    (want - canal), then the tube is fitted against the fixed chamber so the
    total lands on the budget. The envelope still caps calibre, so that fit can
    only shrink the canal.
29. **Branching below the crown is the artefact metric; above it is anatomy.**
    Pulp horns are real and legitimately show as 2-4 blobs in a coronal slice, so
    a raw multi-blob count condemns healthy teeth. Of 10 teeth the operator
    flagged, 9 showed extra blobs only in the coronal third once the canal was
    modelled properly.

30. **Pulp may not approach the surface CORONALLY; apically it may.** The
    chamber ran to within 0.16 mm -- one voxel -- of the occlusal surface and
    incisal edges. The limit comes from the operator's own shading of tooth 14,
    not a textbook: 99% of what they shaded lies at least 0.92 mm deep. It must
    apply to the CORONAL HALF ONLY -- teeth 24 and 25, which they hold up as
    correct, have 17% of their pulp within 0.92 mm of the surface because a thin
    incisor ROOT carries its canal close to the surface. Split by half the metric
    separates cleanly (their reference teeth 0.0-2.8% shallow coronally, their
    flagged teeth 5.0-23.2%); unsplit it would have destroyed the good ones.
31. **Sample roots at 0.20 of tooth length, not 0.30.** At 0.30 the maxillary
    FIRST premolars (5, 12) still read as ONE root -- that far from the apex the
    two are fused -- so the per-root canal assertion never fired and those roots
    had no pulp. At 0.20 they separate and every molar keeps its count.
32. **A root with a canal and no foramen is a canal ending in solid dentin.**
    Painting an asserted canal to the surface and leaving a SEPARATE trajectory
    step to discover the foramen left teeth 5 and 12 with two canals but one
    foramen, and tooth 20 with none. The assertion now records the exit it
    already computed, and any root still without one falls back to the same
    construction. Every root ends in exactly one foramen.
33. **Report modelled and measured foramina separately.** Trajectory-derived
    placements (n=20) come to mean 0.71 mm against the literature's 0.52 and are
    genuine corroboration. Asserted/fallback placements (n=20, mean 1.20) are
    searched within a radius chosen FROM that prior, so their agreement is
    circular. Do not pool them into one validation claim.

34. **The 0.92 mm coronal clearance was MIS-DERIVED and far too permissive.**
    It came from the 1st percentile of ALL the operator's shaded voxels, which is
    dominated by canal and chamber-periphery voxels deep in the root, not by the
    horn tip. Measured against the OCCLUSAL surface specifically, the same
    shading gives a closest approach of 4.05 mm (median 6.23), and the literature
    agrees: cusp tip to pulp horn 5.59 mm maxillary first molar (SD 0.84), 5.30
    mandibular, to chamber ceiling ~6.3. `OCCLUSAL_CLEARANCE_MM = 4.0`, measured
    from the crown-most 15% of the tooth surface -- occlusal clearance only, since
    a canal may still run close to a thin root wall laterally.
    THE LESSON: a percentile over a whole structure is not a measurement of one
    part of it. Measure the thing you intend to constrain.
35. **The cheapest exit is systematically SHORT of the apex.** A route leaving
    the root wall early costs less than one running the last millimetre, so
    tooth 4 and tooth 30's mesiolingual both stopped ~1.6 mm short -- which the
    operator reads straight off a periapical. Take the cheapest 30% of
    candidates, all plausible dark routes, then pick the one NEAREST the apex.
    Foramen deviation went 1.18 -> 0.46 mm on asserted canals.
36. **Reaching the foramen is a separate guarantee from having one.** Fixing the
    exit choice only helped ASSERTED canals; tooth 30's mesiolingual comes from
    the measured tube and still stopped short, because the tube ends where
    pulp_all.py's centreline ends. A final pass carries any root whose pulp stops
    more than `APEX_REACH_MM` from the apex the rest of the way, whatever
    produced it. Median canal-to-apex across 40 roots is now 0.51 mm, against a
    literature foramen position of 0.52.

37. **Occlusal clearance is per tooth GROUP.** 4.0 mm clipped anterior pulp,
    which does reach further coronally. Measured on this patient with the
    constraint off, the coherent radiolucency starts at 2.7-3.7 mm from the
    incisal edge on the clean anteriors against 3.3-3.9 on molars -- so incisors
    and canines get 3.0 mm. Premolars measure 0.4-1.1 there, but that is
    threshold LEAKAGE, not anatomy, which is why they keep the 4.0 mm rule. Do
    not "extend the exception" to them.
38. **A root may carry more than one canal.** Tooth 30 has three canals and two
    roots, so one canal per root left its ML a stub in the coronal third. Where
    the canal count exceeds the root count the surplus goes to the largest roots
    -- the mesial root of a lower molar, which carries MB and ML -- and the extra
    exits are forced `MIN_CANAL_SEP_MM` apart.
39. **Widening the exit search for multi-canal roots was tried and REVERTED.**
    MB and ML foramina really are 2-3 mm apart, so searching wider looked right,
    but enlarging the candidate set also changes which exit is chosen FIRST, and
    tooth 30 fell from three canals to one. A second canal is worth less than
    the first one being correct. `MULTI_EXIT_MM` remains defined but unused --
    if you retry it, decouple the first pick from the widened set.

40. **Canals are traced from the ORIFICES DOWN, not back from the apices.**
    One-canal-per-root is wrong and the operator was emphatic about it: 2:1
    anatomy (two canals leaving the chamber and joining before the apex) is
    common, and this dentition shows it plainly in tooth 31's mesial root. The
    cost field is seeded at the APICAL exits and each orifice traced down into
    it, so two orifices whose cheapest route reaches the same exit merge partway
    -- 2:1 falls out of the geometry instead of being special-cased. The ORIFICE
    count sets the canal count, because that is where a canal is widest and most
    reliably resolved. Result: 28/28 teeth reach their canal prior below the
    chamber floor, 17 show an n:1 join.
41. **The chamber FLOOR is not the apical end of the chamber mask.** That mask
    is the whole opened threshold and runs the length of the tooth, so its
    extreme put the orifice band past the apex and found nothing. The floor is
    where the pulp's cross-section collapses from chamber width
    (`FLOOR_AREA_FRAC`). Measure canal counts against that floor too -- measuring
    them at a fixed FRACTION of pulp length reported teeth 18 and 30 as one canal
    short when the geometry was in fact correct.
42. **The PDL is dark, so orifice detection must be interior-only.** Without a
    depth requirement the detector returned the root's whole dark rind -- 18 to
    35 "orifices" on teeth whose prior is 3 or 4. Contrast at the floor is
    400-800 HU, far more than apically, so the cut there is much tighter than
    the taper's.
43. **A ribbon orifice is two canals.** A mandibular molar's MB and ML are
    commonly joined at the orifice by an isthmus and read as ONE blob. Detecting
    one blob is correct; treating it as one canal is not -- an elongated orifice
    is seeded at both ends of its long axis.

44. **MCP.traceback(end) returns the path STARTING AT THE SEED.** The orifice
    tracer seeds at the APICAL EXITS, so path[0] is the foramen and path[-1] the
    orifice -- the opposite way round to the bridge traceback, whose seeds are
    the chamber. Getting it backwards painted the WIDE end of the taper at the
    apex (the operator saw bulbous canal tips on every single-canal tooth and on
    the molar distal roots) and recorded orifices as foramina. Fixing it took
    molar canal diameter at 2/3/4 mm from 1.27/1.14/1.14 x literature to
    1.02/1.03/1.06, and dropped 58 mm3 of invented volume.
45. **Two canals sharing a root need SEPARATE cost fields, and a reuse
    penalty.** Seeding one field at all exits and tracing every orifice into it
    collapsed siblings onto the same cheapest corridor immediately: teeth 30, 19
    and 31 each ran ONE canal down the whole mesial root. Each root now pairs its
    orifices with its own exits and routes each on a field seeded at that exit
    alone. Where a root has more orifices than reachable exits -- tooth 19's
    mesial has two orifices and one exit -- the first canal's corridor is made
    `CANAL_REUSE_PENALTY` times more expensive so the second takes its own route
    and converges only where it must. That convergence IS the 2:1 join, arrived
    at rather than asserted. All four lower molars now run two mesial canals
    joining apically.

Debugging note: two runs were wasted concluding the orifice tracer "found
nothing" when it was working -- its summary line prints ABOVE the ones being
tailed. Check the whole summary before diagnosing a silent failure.

KNOWN LIMITS, not yet fixed: a few single-canal teeth (11, 23, 24, 25, 26) show
a transient second blob mid-root -- the canal pinching in the mask rather than a
real bifurcation -- and tooth 4 reads 4 orifices against a prior of 1, which is
over-detection even allowing that a maxillary premolar has two. Root separation
in `split_teeth.py` is still the underlying limit. The eight that fall one short (3, 14, 15, 18, 19, 31, and the counting
edge cases 4 and 25, whose canals end 1.0-1.13 mm out) are limited by ROOT
SEPARATION in `split_teeth.py`, not by pulp_connect: tooth 18's mesial and
distal roots never separate in the apical fifth, and teeth 4 and 13 read as
single-rooted at every slab depth tried. Fixing those means re-running the arch
split and everything downstream of it.

104. **The hand-traced pulp has no foramina, and nothing said so.**
    `combine_traces.py` folds tracings into a mask and emits `foramina: []` for
    every tooth. Repointing the nerves at the hand-traced pulp therefore drew
    27 mandibular branches -> 0, in silence: a foramen is not part of the pulp
    mesh, so no pulp number moved and the loss surfaced two steps downstream.
    Rule 8's failure mode in another costume -- a missing value that changes no
    scalar being printed. `tools/cbct/trace_foramina.py` recovers them as the
    apical terminus of each connected component in the apical 45% of the traced
    pulp (canals are separate down there even where they merge higher), and
    writes them back as world LPS. 44 foramina against the tree pipeline's 47,
    and the per-tooth counts match the canal priors.
105. **Validate a foramen against ITS OWN root's apex.** Scoring every foramen
    against the single most-apical voxel of the tooth compares two of a molar's
    three against the wrong root and reports a 2.63 mm mean when nothing is
    wrong. Restricted to the 17 single-canal teeth: mean 0.84 mm, median 0.76
    (literature 0.52) -- the hand tracing stops a little short of the true
    foramen, which is expected and worth remembering before anyone "fixes" it.

### Nerve supply, expanded against the Wikipedia anatomy (2026-08-30)

The IAN terminates by dividing into the MENTAL nerve, which leaves the mental
foramen near the second premolar, and the INCISIVE branch, which continues
forward inside the mandible to the first premolar, canine and incisors. V2 gives
PSA directly in the pterygopalatine fossa, but MSA and ASA are branches of the
INFRAORBITAL nerve inside its canal.
  -- /wiki/Inferior_alveolar_nerve, /wiki/Mental_nerve,
     /wiki/Posterior_superior_alveolar_nerve, /wiki/Anterior_superior_alveolar_nerve

106. **Teeth anterior to the mental foramen hang off the INCISIVE nerve.** The
    old code ran a straight chord from the canal to every lower apex and
    discarded anything past 25 mm, which silently dropped teeth 24 and 25 -- and
    the cutoff was right, because a 25 mm chord to a central incisor runs
    through bone. The incisive branch is built through the anterior apices
    themselves (offset apically), which is the only measured evidence of where
    that canal runs on this patient. All 14 lower teeth are now supplied: 9
    branches off the plexus, 10 off the incisive.
107. **The anterior end of the skeleton is NOT the mental foramen.** The fused
    canal sits on a padded grid spanning both exposures, so its centreline
    carries spurs and on the right dives to z = -44.7, below the mandible's own
    floor at -43.7. Place the foramen where the anatomy says -- project the
    MEASURED premolar apices onto the centreline. y went from -22.0/-23.9 (one
    a spur) to -21.9/-23.9, symmetric.
108. **`lab == 2` says a nerve inside the mandibular canal is outside the
    mandible.** DentalSegmentator is per-class, so the canal (5) and the lower
    teeth (4) are HOLES in the mandible label: the containment test read 0 of
    209 trunk points as inside bone, and "fixing" the foramen on that basis
    moved it 21 mm posteriorly. Fill the mandible and union the classes that sit
    within it. (Rule 4, in a new disguise.)
109. **Reject points outside the VOLUME, not outside the BONE.** Roughly half
    the fused canal legitimately lies beyond centered.nrrd's FOV, so an
    in-bone filter discards good anatomy along with the spur.
110. **A branch must taper into the pulp.** A 0.35 mm tube entering a 0.2 mm
    foramen reads as a peg pushed into the root. Every branch now runs
    0.32 -> 0.12 mm, the incisive 0.45 -> 0.18, the mental 0.55 -> 0.22.
111. **Keep the schematic terminal branches in their OWN mesh.** They were
    first appended to the trunk's buffers, which would have let the UI colour a
    course this scan never saw exactly like the canal it did -- the thing this
    module's docstring exists to prevent. `nerve-terminal.stl` / FMA53381T.
112. **MSA and ASA must arise FROM the infraorbital nerve.** They were free
    stubs in the sinus. The infraorbital nerve is now built from the
    pterygopalatine fossa forward to its foramen, with MSA and ASA descending
    from it and PSA still leaving V2 directly -- so the rendered tree matches the
    branching order. Still entirely SCHEMATIC; nothing of it is resolved.

Nerve tissue renders YELLOW (`nerves` in build-assets.mjs MATERIALS), the
convention in every anatomy atlas. Arteries red and veins blue are on the
wishlist; the inferior alveolar artery and vein share the measured canal with
the nerve, which is a provenance trap worth reading before starting.

KNOWN LIMIT: the mental foramina sit at |x| 18.4 right against 26.3 left. The
right canal centreline is the weaker of the two.

### Nerves (2026-08-30)

`tools/cbct/nerve.py` (mandibular, pre-existing) now anchors on
`pulp-connect.json`'s `foramina` -- the modelled foramen EXITS -- rather than
pulp.json's `apical_position_lps`, which is the end of the deficit-integration
tube and a worse point to hang a nerve on. 2 trunks (60.8 / 54.6 mm), 27
branches. `tools/cbct/nerve_maxilla.py` is new and builds the superior dental
plexus, its branches, and PSA/MSA/ASA bilaterally.

46. **The maxillary nerves are SCHEMATIC and must not render like the IAN.**
    The mandibular trunk follows a canal this CBCT resolves; the superior
    alveolar canals are thin, often dehiscent, and not reliably visible at
    0.16 mm. Nothing in nerve_maxilla.py was seen in the scan except the
    foramina. The structure names and the UI caveat both say so -- do not let a
    tidy-up merge the two into one undifferentiated "nerves" claim. MSA is
    absent in ~2/3 of people and is flagged `inconstant` in the JSON.
47. **atan2 about the arch centroid puts its branch cut INSIDE the horseshoe.**
    Ordering plexus nodes that way jumps from one posterior end to the other,
    and smoothing then averages across the jump and drags nodes toward the arch
    centre -- it produced a plexus node at x = 0.0, in the middle of the palate.
    Measure the angle from the ANTERIOR direction so the cut lands in the
    arch's posterior opening. The same trap applies to anything else ordered
    around the arch.
48. **Schematic geometry must not participate in centring.** The maxillary
    trunks run an arbitrary `TRUNK_RUN_MM` out of the plexus, so including them
    in `bounds()` let a drawing choice move the whole model: it shifted the
    centre ~1 mm and tripped the laterality assertion on the right maxilla,
    whose centroid sits near the midline. `build-assets.mjs` now excludes the
    nerves layer from centring, as it already did muscles.

49. **THREE mechanisms were creating canals at once, and the extras are the
    offshoots.** Orifice tracing, asserted canals and trajectory extension all
    ran unconditionally, layering canal on canal: tooth 14 ended with SIX
    foramina for three roots, and the operator saw the surplus as a DB canal
    wrapping into the MB and a palatal canal branching into the buccal. Orifice
    tracing is the only one that starts from where the canal demonstrably is, so
    it now runs FIRST and claims its roots; the other two fill only what it could
    not reach. 59 -> 46 foramina, 39 of them orifice-traced, and foramen
    deviation improved to mean 0.53 mm against the literature's 0.52.
50. **Gating the fallbacks removed the apex-reach guarantee.** Tooth 13 promptly
    came up 1.85 mm short. The final pass is restored, but as a SHORT STRAIGHT
    extension from the existing terminus -- re-routing is what produced the
    offshoots in the first place, so it must not route again.
51. **Do not judge cross-root wandering by apical root footprints.** Roots are
    detected in the apical fifth where they are narrowest, so legitimate
    mid-root pulp reads as "outside every root footprint" -- the metric showed
    15-32% stray on healthy teeth and moved the wrong way when the confinement
    that was supposed to fix it went in. Confining canals to their own root
    below the chamber floor is still right (`ROOT_FOOTPRINT_PAD_MM`), but it was
    not the cause of the offshoots.

### The canal system is a TREE (2026-08-30 rewrite)

`tools/cbct/canal_tree.py` + `tools/cbct/pulp_build.py` replace
`pulp_connect.py`'s accumulate-and-filter approach. `pulp_connect.py` is kept
only for the helpers both share (orifice detection, root slabs, cost field,
mesh field, adaptive decimation) -- its `connect()` is dead.

The architecture is two claims kept apart:

  ABOVE THE CHAMBER FLOOR  thresholded radiolucency, opened. The chamber is wide
                           enough to resolve, so the image says what shape it is.
  BELOW THE FLOOR          the canal tree and NOTHING else. A canal is 1-3
                           voxels across; thresholding there returns speckle.

The tree has one root inside the chamber, one leaf per apical foramen, and a
radius at every node. A branch can then exist only where the tree branches and a
dead end is unrepresentable, because every leaf IS a foramen by construction.
Voxelisation is still used for MESHING (it handles junctions for free) but what
gets voxelised is a smooth analytic tube, not accumulated paint. There is no
bridging, no despeckling, no per-voxel repair. If the output is wrong the TREE is
wrong -- fix it there, and do not add a filter.

Measured against the old pipeline:

    meshes in pieces        9  ->  0
    voxel masks in pieces  12  ->  0
    below-floor twigs      39  -> 25
    below-floor branchpts  63  -> 31
    foramen deviation    0.56  -> 0.55 mm   (literature 0.52)
    canal calibre vs micro-CT at 1/2/3/4 mm: molar 1.10/1.00/1.06/1.02
    Dice vs the operator's tooth-14 shading: 0.777 (old best 0.804, but that
    was a fat thresholded canal matching a generous shading)

52. **The micro-CT series is the canal's TARGET apically, not a cap.** Using it
    only as a ceiling and interpolating linearly orifice-to-foramen undershot
    everywhere -- molars came out at 0.59-0.74x measured calibre. Within the
    apical 4 mm the canal IS the literature profile; above that it widens to the
    orifice radius measured from the chamber.
53. **Cutting the chamber at its floor can SPLIT it**, because parts of the
    coronal pulp are joined only through voxels below the floor. Re-take the
    largest component after cutting -- under FACE connectivity. Selecting it with
    a 3x3x3 structure says one component where the mesher sees twelve; that is
    rule 18 again, and this rewrite walked into it a second time.
54. **Root the canal INSIDE the chamber, not at the orifice.** Orifices are
    found 0.4-2.4 mm below the floor, so a canal starting deep in that band never
    touches the chamber; start the centreline a couple of voxels inside the
    chamber so the capsule overlap is solid rather than tangential.

Ruled out along the way, so nobody repeats it: it is NOT `split_teeth.py` (that
splits the arch into teeth and never separates roots -- root separation is
`apical_roots()`); NOT the measured tube (removing it made things worse); NOT
`CANAL_REUSE_PENALTY` alone. Two metrics also mislead: cross-root "stray" voxels
judged against apical root footprints, and whole-tooth twig counts (pulp horns
ARE short terminal runs). Measure branching strictly BELOW the chamber floor.

55. **Give the canals their share of the volume budget.** Calibrating the
    chamber to the WHOLE pulp volume and then adding canals left the chamber
    holding 85-95% of the total and visibly too large. The canal volume is known
    after one pass, so the chamber is recalibrated against what remains and the
    tree rebuilt on the corrected chamber. Two passes; it doubles the runtime
    (~4 min for 28 teeth) and that is fine.
56. **Every root must claim an orifice before any root gets a second.**
    Nearest-centroid assignment alone handed every orifice to one root and left
    another with none -- an entire canal missing on teeth 5 and 31. Roots claim
    their closest orifice first, then the remainder are distributed.
57. **The isolevel floor must apply to CANALS ONLY, plus the junction.**
    `mesh_field` floors every voxel thinner than ~1.5 voxels so canals survive
    smoothing; applied to the whole pulp it also guarantees that every one-voxel
    spur on the thresholded chamber survives into the mesh -- the "spikey bits".
    Chambers are thick and the Gaussian should be allowed to smooth them. The
    junction needs flooring too (those voxels belong to the chamber), and where
    an internal chamber neck still thins away the build falls back to the full
    floor rather than shipping a mesh in pieces.

Ruled out for chamber spikiness, so nobody retries them: the opening
structuring element (cross/cube/ball/2x barely move it), Gaussian smoothing of
the mask (5-7%), and the threshold level itself (flat from frac 0.50 to 0.95).
All are compensated by the volume calibration, which simply re-picks a level.

### Canals are LANDMARKS joined by a spline (operator's design)

The operator proposed it and it is the right model: for each canal identify four
things the image can actually be asked about --

    chamber   the deepest chamber voxel nearest this canal's orifice
    orifice   where the canal leaves the chamber floor (find_orifices)
    mid-root  the darkest voxel halfway down, near the orifice-apex line
    apex      the foramen (pick_exits)

-- and run a Catmull-Rom curve THROUGH them. A minimum-cost path through a voxel
grid is free to wander wherever the cost field dips, which is what produced the
offshoots and the staircase; a spline through four measured points cannot.
`darkest_near_line` finds the mid-root point by intensity plus a distance
penalty from the straight line: pure minimum-intensity wanders onto the PDL or a
neighbouring canal, and forcing it onto the line would straighten real curvature.

58. **A spline through landmarks cuts corners, and in a curved root the corner
    is OUTSIDE the root wall.** Voxelising with a domain limit then clips the
    tube there, leaving a gap in the canal and a stub either side -- four teeth
    came apart and the twig count rose. `pull_inside` projects stray control
    points back to the nearest voxel inside; run it before AND after smoothing.
59. **`pulp.json`'s canal priors are wrong for teeth 4 and 13.** Both are
    maxillary SECOND premolars listed as single-canal; two canals occur in about
    half of them and the operator reads two on their own periapicals. See
    `OPERATOR_CANALS`. A clinician's reading of their own anatomy outranks a
    default prior -- but keep such overrides in one named dict, never scattered.
60. **Report a dropped canal, never drop it silently.** Where the tree cannot
    realise a canal it leaves an orphan fragment; shipping it breaks the mesh
    and deleting it quietly looks like the anatomy is simply absent. The build
    prints which tooth lost what.

### Canals are TRACKED, not routed and not splined through four points

Four landmarks joined by a spline made molar roots straight -- the operator's
point, and correct. But adding more landmarks was not the fix either, because
the deeper fault was that orifices were assigned to roots detected SEPARATELY:
wherever `apical_roots` saw one root where the tooth has two, both canals went
down the same one. That is "two buccal canals and no palatal" on teeth 5, 12 and
13, and "no MB" on 19.

`track_canal` walks one canal down from its orifice, step by step: predict that
it continues in the direction it was going, accept the darkest voxel near that
prediction. The canal curves as the radiolucency curves, and it lands in
whichever root it actually occupies BECAUSE IT WAS NEVER TOLD ABOUT ROOTS.
Roots are now used only to name the apex a canal arrived at.

    below-floor twigs   39 (accumulate) -> 24 (min-cost) -> 31 (spline) -> 14
    meshes in pieces    0
    foramen deviation   0.72 mm mean, 0.55 median (literature 0.52)

61. **Keep direction in ONE unit system.** The tracker normalised its direction
    in millimetres and then scaled it by a voxel count, which made the step
    length meaningless: every track stopped early, foramina fell to 33 and mean
    deviation from the apex rose to 2.96 mm. Direction is a unit vector in mm;
    convert to voxels only when applying it.
62. **Merge sibling canals only APICALLY and only when genuinely close.** At
    0.55 mm anywhere along its length a faint palatal canal was captured by its
    buccal neighbour on the way down and vanished. Canals sharing a root
    converge near the apex; canals in different roots never do. 0.35 mm, and
    only past 55% of the way down.

### Canal counts are a PER-ROOT quota, enforced (2026-08-30)

The operator's rule: an unfilled root is always wrong, and two canals in a
palatal root are anatomically impossible. Both are now enforced rather than
hoped for.

`ROOT_QUOTA` is keyed by (universal, root identity) from the literature: MB2 in
~60% of maxillary FIRST molars and ~33% of seconds, so the first molar's MB root
gets 2 and the second's 1; the maxillary palatal root is essentially always
single; the mandibular mesial root carries 2 and the distal 1 (a second distal
canal occurs in ~37%). `identify_roots` names each root buccal/palatal or
mesial/distal from its own position relative to the arch, so nothing depends on
a hand-typed table of which root is which.

63. **Reconcile the per-root quota against a per-TOOTH total.** `apical_roots`
    reads tooth 15 as two roots, 18 as one, and 4/12/13 as single-rooted.
    Applying a per-root quota to a root that is really two roots fused throws
    away canals that exist -- tooth 18 lost two. `TOOTH_CANALS` gives the total
    and the remainder lands in the largest detected root, which is the fused one.
64. **File a canal under the root its TIP lands in, not its orifice.** Where a
    canal ends is what makes it that root's canal.
65. **Fill an unfilled root from the image, not from nothing.** `seed_in_root`
    takes the darkest voxel in the root's coronal quarter and tracks down from
    there, so only the DECISION that a canal exists comes from the quota; its
    course is still measured.

    roots with no canal   1 -> 0
    below-floor twigs     15
    meshes in pieces      0
    foramen deviation     0.71 mm mean, 0.49 median (literature 0.52)

Foramina below the canal count is expected where canals merge (Vertucci II):
teeth 3, 12, 13 and 19 each run their full canal count but share a foramen.

66. **One taper slope, foramen to orifice.** The micro-CT series is nearly
    linear in distance from the apex, ~0.088 mm of diameter per mm
    (`CANAL_TAPER`), which is also the range clinical taper is quoted in. The
    previous model held the envelope apically and blended to the orifice radius
    over the remainder -- a visible kink partway up the canal.
67. **Do NOT cap canal calibre by the chamber distance at the orifice.** That
    distance is small whenever the orifice sits at the edge of the chamber, and
    clamping to it flattened the taper from 4 mm upward: 0.72 mm diameter at
    8 mm where the slope calls for 1.00. Cap by an absolute maximum
    (`CANAL_MAX_R_MM`); the canal merges into the chamber at the top anyway.
68. **Canals drift onto the root wall because the PDL is dark.** The tracker
    follows darkness and the darkest thing near a thin root wall is often
    OUTSIDE it. Two defences: the tracker penalises candidates shallower than
    the danger-zone minimum (`MIN_DENTINE_MM`, micro-CT gives 0.67-1.93 mm with
    a 1.10-1.13 mean), and `recentre` moves each centreline point toward the
    local maximum of the distance-to-surface field within its own axial slice.
    Recentre toward the TARGET, not merely to clear the minimum -- a canal at
    0.9 mm in a root centred at 1.6 mm still renders as hugging the wall once
    the tube's own radius is added. Canal surface clearance went from 0.16 mm
    (one voxel, on 24 of 28 teeth) to a 0.77 mm median.

Careful with clearance metrics: dentine is legitimately thin near the apex, so a
5th-percentile over the whole canal mixes real apical thinness with genuine
wall-hugging. The 1.10 mm literature figure is a MID-ROOT danger-zone value.

69. **`seed_in_root` needs memory.** Filling a root that needs two canals called
    it twice and, with nothing excluded, it returned the SAME darkest voxel both
    times -- teeth 12 and 13 got two buccal canals and no palatal, 18 a
    duplicated ML, 19 lost its MB. Pass the canals already drawn as an exclusion
    mask.
70. **Two canals in one root are two canals only if they are apart AT A COMMON
    DEPTH.** Comparing each track's own midpoint by index compares tracks of
    different lengths at different levels, so near-parallel canals read as far
    apart and both survived. Interpolate every track to a shared reference z.
    A "root" that is really two fused roots (`root_names == "s"`) needs a wider
    separation than a true single root, because MB1 and MB2 in a genuine
    mesiobuccal root are only 1-2 mm apart.
72. **THE CHAMBER FLOOR IS A TOOTH LANDMARK, NOT A PULP ONE.** This was the
    cause of the "scraggly" chambers, and it took a screenshot to see. The old
    rule -- most apical slice where the PULP still holds 35% of its maximum
    cross-section -- works on a molar, whose chamber is plainly wider than its
    canals, and fails completely on a single-canal tooth where the two are
    barely different in width. On the anteriors it put the floor at 74-82% of
    tooth length, so nearly the whole ROOT was thresholded chamber instead of a
    swept tube: lumpy ribbons with lateral knobs, and a hole through one. No
    amount of mesh smoothing could fix that, which is why five attempts failed.
    - single-rooted: the CERVICAL narrowing (first slice apical to the crown's
      widest holding < `CERVICAL_FRAC` of it)
    - multi-rooted: the FURCATION (first slice where the tooth's cross-section
      splits into two components of real size)
    Both are read from the tooth mask. Total pulp fell 1097 -> 796 mm3, against
    ~760 published for a whole dentition.
73. **Search the furcation BELOW the cervical line.** Walking from the crown
    finds the CUSPS -- separate components at the occlusal surface -- so the
    "furcation" landed near the crown and deleted the chamber. Every
    multi-rooted tooth was skipped for having no chamber left.
### THE PULP IS HAND-TRACED (2026-08-30)

Automatic segmentation was abandoned for the pulp after it could not tell pulp
from dentin on this scan at any threshold -- molars lost whole roots, anteriors
ran red to the incisal edge. The operator traced all 28 teeth over three rounds;
`tools/cbct/trace_kit.py` exports and imports, `combine_traces.py` folds the
rounds together, `mesh_hand.py` meshes without second-guessing them. If a tooth
is wrong now, the TRACING is what changes.

  round 1  two perpendicular longitudinal planes per single-canal tooth,
           one per root on the others                    (89 images)
  round 2  two perpendicular planes PER ROOT on every molar and premolar,
           plus chamber axials                          (134, 35 carried over)
  round 3  six axial slices per tooth: apical half on posteriors, most of
           the length on anteriors                      (168 images)

Result: 28 teeth, 888 mm3, every one a single connected component, median 4.6%
of tooth volume.

94. **Pulp cannot lie outside its tooth, and the check must come LAST.** The
    longitudinal reconstruction rasterises an ellipse from two traced widths and
    never tested it against the tooth, so where a curved reformat sweeps through
    a furcation the ellipse spills into the void between the roots and joins
    mesial to distal across it. Tooth 18 carried 3.5 mm3 outside its own mask and
    showed six canals; no other tooth had any. Clipping before the component
    bridging was NOT enough -- the routed path stays in dentin but the 3x3x3
    stamp around it spills through a thin wall, so the clip has to be repeated
    after bridging and after closing. Now 0.00 mm3 outside, across all 28.
95. **Route a bridge through dentin, not through space.** A straight run from a
    canal head to the nearest chamber voxel cuts through the inter-root void on
    a tooth whose roots do not separate. Use a min-cost path confined to the
    tooth mask; if none exists, no bridge is drawn.

93. **Smooth the SIGNED DISTANCE along z, not the mask.** Substituting a traced
    axial at its own level and taking neighbouring levels from the longitudinal
    reconstruction leaves a step wherever the two disagree in size -- visible as
    a ledge at every slice level, on every tooth. Smoothing the distance field
    along the tooth's axis and re-thresholding turns each step into a taper;
    blurring the binary mask instead would erode the one-voxel canals. Ledges
    (95th-percentile slice-to-slice area jump) fell on 25 of 28 teeth and the
    dentition total went 888 -> 723 mm3, against ~760 published.
    NOTE tooth 18's ledge metric rose (1.06 -> 5.85) -- a sliver at one end, not
    a shape change; its volume and connectivity are fine. Worth a look if that
    tooth ever renders oddly.

88. **Longitudinal views give the COURSE, axials give the CROSS-SECTION.** Two
    perpendicular widths were being turned into an ellipse, which is too fat for
    a ribbon-shaped pulp; axials measure it. And a canal that has split still
    projects as one shape in a longitudinal view until the parts separate in
    that particular plane -- 2:1 versus 2:2 is an axial question.
89. **Use each tracing AS DRAWN; do not rescale one to fit the other.** Two
    cleverer schemes both inflated the result. Interpolating the axial MASKS
    across a long gap fills the space between a chamber section and a canal
    section with a solid cone (tooth 3 reached 147 mm3 against a traced 18;
    teeth 23-26 reached 7-9% of tooth volume). Interpolating the AREA instead
    does the same thing more smoothly, because the taper below a chamber is far
    from linear. Straight substitution -- axial at its own level, longitudinal
    everywhere else -- is simpler and closer to what was traced.
90. **An area ratio between the two sources is meaningless on a molar.** The
    longitudinal planes there trace only canals while the axials also take in
    the chamber, so the ratio at a chamber slice is enormous and then gets
    applied down the whole root.
91. **A one-voxel bridge joins nothing.** Connecting separately-traced roots
    with a single-voxel diagonal line is not face-connected: tooth 2 went from 7
    components to 36. Stamp 3x3x3. (Rule 18, third occurrence.)
92. **Downsample the tracing by MAJORITY, not ANY.** Marking a voxel traced when
    any pixel in its 6x6 block is red fattens every edge by up to a voxel each
    side and doubled the volume of every narrow canal.

### Gingiva: the CEJ ring is REFITTED, not trusted (2026-08-30)

The operator reported the gingiva sitting far too high, worst on the LINGUAL of
the mandibular incisors. It was: teeth 22 and 27 had a gingival margin 1.1-1.5 mm
below the incisal tip, i.e. gingiva covering essentially the whole crown.

96. **The CEJ has exactly TWO low points, mid-facial and mid-lingual, and they
    are the SAME height.** The cervical line scallops mesiodistally, not
    buccolingually -- which `landmarks.py`'s own docstring already says. So a
    measured ring reading 1.81 mm facially and 8.65 mm lingually (tooth 22) is
    not a biotype, it is a broken measurement, and the asymmetry is a free,
    assumption-light test for one. Lingual-minus-facial was 6.84 mm on tooth 22,
    5.98 on 27, 14.94 on 18; it is now under 0.6 mm on all 28.
97. **The enamel ray fails as a PLATEAU, so refit the ring -- never smooth it.**
    `landmarks.py:93` takes the most apical voxel it still calls enamel. Thin
    mandibular-anterior lingual enamel drops under the threshold, so the lowest
    surviving voxel is up in the incisal third and the CEJ reads ~7 mm too
    coronal; a restoration or the alveolar plate caught instead reads too apical
    (tooth 18, -11.6 mm). Both wrong runs are CONTIGUOUS and cover up to half the
    ring, so a median, a percentile or a smoothing pass is dragged by them. The
    ring is refitted to a one-parameter model instead -- baseline free, shape and
    amplitude fixed by the published cervical-line curvature -- by consensus
    vote. Aspects within 1 mm keep their measured value, so real detail survives.
98. **A vote needs an anchor a wrong majority cannot supply.** On teeth 21, 27
    and 28 the bad plateau covered MORE than half the ring and won the vote
    outright, moving tooth 27's facial CEJ from 2.87 to 7.89 -- worse than doing
    nothing. Crown height (cusp tip to mid-facial CEJ, Wheeler) fixes the
    baseline without reference to any aspect of the ring, so majority size stops
    mattering. It is the same figure gingiva.py's docstring already validates the
    CEJ against.
99. **Calibrate the anchor's CONSTANT, trust the table for the DIFFERENCES.**
    The raw anchor sat 2.04 mm low on every tooth alike -- the tip is a
    percentile of a segmentation and the axis is a principal direction, so the
    pair carries a fixed bias. Teeth whose ring fits a scallop unaided supply the
    constant; the table supplies what no measurement on a broken tooth can, which
    is how much shorter a molar's crown is than an incisor's.
100. **Set a tolerance from the dispersion, not from taste.** Across the 17 clean
    rings the anchor residual has sigma 0.44 mm and a 95th percentile of 1.17, so
    `CROWN_TOL_MM = 1.5` is 3.4 sigma. The 2.5 mm first tried is 5.7 sigma and let
    teeth 20 and 29 ride a 2.2 mm offset straight through it.
101. **A healthy sulcus is deeper interproximally than mid-facial.** The
    operator's spec is 1-2 mm probing depth; the margin is now lofted one sulcus
    coronal to the corrected CEJ, 1.0 mm at the mid-facial and mid-lingual and
    2.0 mm at the col, which is where a papilla's height comes from on top of
    the CEJ's own scallop.

Clinical crown (margin to incisal/occlusal tip) before -> after: tooth 22
1.49 -> 8.33 mm, 27 1.14 -> 8.21, 21 1.93 -> 5.25, 23 2.37 -> 6.49. Teeth 24 and
25, which the operator never flagged, moved 6.32 -> 6.58 and 6.13 -> 6.63 -- a
fit that only disturbs the teeth that were wrong. Lower gingiva 1355 -> 1092 mm3.

NOTE the maxillary and mandibular CENTRALS (8, 9, 24, 25) sit 0.6-1.3 mm below
the calibrated anchor while every other tooth is within 0.6. Most likely the
crown-height figure does not allow for incisal wear. Left alone rather than
given a per-type constant fitted from n=2.

102. **The margin is uniformly ~2.3 mm too coronal, and the molars show it
    first.** After the scallop refit the operator still read the molar gingiva as
    high. Measured against the published clinical crown (crown height less a
    1 mm sulcus) EVERY group is short by the same amount -- molars 4.0 against
    6.3, premolars 5.3 against 7.5, anteriors 5.9 against 8.0 -- so it is one
    uniform error, not a molar one. It surfaces on the molars because their
    crowns are shortest: 2.3 mm is 37% of a 6.3 mm molar crown and 23% of a
    10 mm canine. The cause is rule 99's calibration constant being measured
    from the same enamel ray it is correcting; that ray's error is
    ONE-DIRECTIONAL (thin cervical enamel can only read the CEJ too coronal) and
    cervical enamel is thin on every tooth, so the constant partly measures the
    error. `MOLAR_MARGIN_DROP_MM = 1.5` moves the molars only, because the rest
    of the arch is accepted as it stands. PROVISIONAL: the full correction is
    2.3 mm and the real fix is an anchor constant not derived from the ray.
103. **Shift the RING, not the anchor.** Subtracting the drop from the anchor
    moved 2 of 8 molars: the anchor recentres the window the fit may land in, and
    six consensus baselines were already inside it. What is too coronal is the
    margin, so the correction belongs on the fitted ring. Molar clinical crown
    3.40-5.17 -> 4.90-6.67 mm against a 6.30 expectation.

Ruled out, so nobody retries them: a molar-specific anchor bias (per-group
medians are 2.41 molar / 2.19 premolar / 2.45 anterior -- there is no group
effect), and measuring the cusp tip on the FACIAL only to match how crown height
is defined (it moves the anchor but the global calibration absorbs it exactly).

### SEGMENT IN 2D FIRST, MESH LAST (2026-08-30)

The operator called this correctly: identify the pulp radiolucency on the CBCT
slices for all 28 teeth, verify it there, and only then build geometry.
Everything before this inferred the pulp from a volume budget and literature
priors and checked afterwards, which is backwards and cost most of a long
session. `tools/cbct/pulp_segment.py` does the segmentation with no volume
prior; `tools/cbct/pulp_tune.py` renders one tooth at several contrast levels
side by side so the threshold is CHOSEN BY LOOKING, not defended after the fact.

86. **METAL RESTORATIONS AND THEIR HALOES SEGMENT AS PULP.** Teeth 19 and 30
    carry 340 and 273 mm3 of material saturated at the scanner's 3072 HU
    ceiling; teeth 20, 23, 24 and 29 carry smaller amounts. Metal throws a dark
    beam-hardening halo that thresholds exactly like a lumen, so at EVERY
    contrast level red bled into the restoration and its shadow. This is why
    those teeth always carried the largest volumes and the largest "uncovered
    radiolucency", and why no threshold tuning ever fixed them -- the artefact
    is darker than real dentin. `RESTORATION_HU = 2600` plus a 1.4 mm margin
    excludes it, and the teeth are FLAGGED `obscured`: their pulp is partly
    hidden and whatever is drawn there is inference, not measurement. Say so in
    the UI rather than rendering it like the rest.
87. **A single contrast works better than any adaptive rule tried.** At 380 HU
    below each slice's own dentin, with restorations excluded, 22 of 28 teeth
    land at 2.3-3.9% of tooth volume (literature 3-4) and the dentition totals
    778 mm3 against ~760 published. A "leakage knee" detector was tried and
    failed badly -- it gave tooth 30 a 180 HU threshold (231 mm3, 17% of the
    tooth) and teeth 7/10/26 540 HU (1.5%). Prefer the fixed level plus named
    per-tooth exceptions.

Still to review individually: 19, 20, 26, 27, 29, 30 (four of them restored).

### Overlay verification: the pulp ON the CBCT (2026-08-30)

`tools/cbct/verify_overlay.py` writes one sheet per tooth -- two longitudinal
planes through the pulp centroid plus eight axial slices from chamber roof to
apex, grey CBCT with the model in red. This is the only check that has ever
settled anything here; every proxy metric tried before it was blind to at least
one defect the operator could see instantly.

What it showed, and then let me measure:

83. **The canals are right; the CHAMBERS were under-filled.** Of the interior
    radiolucency the model failed to cover, 98% is CORONAL and 0-3 mm3 per tooth
    is radicular. Stop looking for canal bugs.
84. **The volume search measured the UNCUT chamber and shipped the cut one.**
    `cut_floor` removed a chunk after calibration, so every tooth landed below
    its target -- teeth 9, 11 and 22 at 12.8, 14.7 and 15.0 mm3 against 21.1,
    27.0 and 24.8. The domain was never the limit: at the loosest threshold
    those chambers could reach 100-300 mm3. Calibrate what you ship -- this is
    the third time this exact trap has cost a session (see also closing/filling
    and the assembly chain). Pulp/tooth ratio is now 3.1-4.2% on all 28 against
    a literature 3-4%.
85. **Occlusal clearance is measured from the CUSP TIP DOWN THE AXIS.** The
    literature figure (5.59 mm) is cusp tip to pulp horn along the tooth.
    Measuring to the NEAREST occlusal surface instead penalises a horn under a
    fissure, where the surface dips between cusps -- 69% of the uncovered
    radiolucency lay inside that exclusion.

Do not trust the "missed radiolucency" figure as an absolute: dark interior
voxels also occur under restorations (teeth 19 and 30 both carry one and show
79-84 mm3 of "miss"), at the DEJ, and in beam-hardening shadows. Use it to
compare BEFORE and AFTER, and to split coronal from radicular.

### Per-tooth audit against literature (2026-08-30)

Every tooth checked individually for pulp volume and canal count. The volume
reference is the pulp/tooth RATIO, which is the one figure the literature gives
cleanly per tooth: a canine measures 22-29 mm3 of pulp in a 745 mm3 tooth, 3.9%.
All 28 now fall at 2.2-4.2%; total 620 mm3 against ~760 published for a full
dentition.

79. **`PULP_FRACTION_MAX` capped the LUMEN, then the result was multiplied by
    SHADING_SCALE.** So the effective ceiling on the pulp CAVITY was 3.9 x 2.12
    = 8.3% of tooth volume, and teeth 3, 5 and 31 came out at 7.0-7.8%. The
    literature ratio is for the cavity itself. `PULP_FRACTION_OF_TOOTH = 0.040`
    is applied to the pulp directly. This one error accounted for most of the
    "chambers too big" reports.
80. **`enclosed_void` is a hard floor the threshold cannot cross.** solid_pulp
    unions the hole in the segmentation mask, which does not depend on the
    threshold at all, so tooth 3 could not go below 55 mm3 of chamber against a
    44 mm3 budget however tight the cut. Erode the chamber until the total fits.
81. **Apply that erosion AFTER the two-pass recalibration, not before.** The
    second pass rebuilds the chamber from scratch and silently discarded it --
    the total moved 713.0 -> 712.5 mm3 instead of 713 -> 620.

82. **Teeth 3, 14, 18 and 12: a second canal exists as a tree branch and a
    FORAMEN but never appears as separate geometry.** Confirmed by measuring the
    cross-section: tooth 12 is a single ROUND tube 0.64 -> 0.32 mm all the way
    down, not two touching (which would read elongated). So the sibling canal is
    tracked, recorded, voxelised -- and coincident. Three attempts failed to
    separate it: a soft proximity penalty in the tracker (`avoid_pen`), a seed
    exclusion radius, and a HARD exclusion of the sibling's corridor from the
    track's domain. None changed the profile at all, which suggests the second
    canal is not going where the exclusion applies -- diagnose where its track
    actually runs before trying a fourth variant.

Residual flags are canal COUNT measured at one depth (45% of root length), which
reads a merged pair as one canal and a splitting one as two. Teeth 3, 14, 18 and
31 carry the right number of FORAMINA; their canals merge above that plane,
which for MB1/MB2 is normal anatomy.

75. **Occlusal clearance scales with CROWN HEIGHT.** The 4.0 mm figure came
    from tooth 14, a long-crowned molar. Applied to a premolar or an incisor it
    squeezes the coronal pulp between itself and the chamber floor until the
    crown reads as empty -- premolars 20, 21, 28, 29 held 0-6% of their pulp in
    the chamber. Molars 4.0, premolars 3.0, anteriors 2.2.
76. **Cap the chamber floor at a fraction of tooth length.** A canine tapers so
    gradually that the cervical area test lands at 55% of its length, giving
    teeth 22 and 27 chambers of 28 and 23 mm3 -- bigger than most molars', which
    is absurd for a single-rooted tooth. `MAX_CHAMBER_FRAC = 0.45`; a crown is
    at most about 45% of a tooth.
77. **A canal created to satisfy the quota must never be merged away.** It
    exists precisely because a separate canal is required there, so letting it
    merge into a neighbour is the same as never drawing it: teeth 4 and 12 lost
    their palatal, 18 its ML, 19 its MB -- all of which the fill had correctly
    created and the merge then erased.
78. **Every canal reaches the chamber, merged or not.** A canal that joins a
    sibling lower down still LEAVES the chamber at its own orifice. Giving the
    chamber connection only to unmerged canals left tooth 31's ML starting in
    mid-root with nothing above it.

74. **My roughness metrics were blind to the actual defect.** area/volume^(2/3)
    is dominated by the thin canals hanging off the chamber (70 Taubin passes
    moved it 1%); mean dihedral angle read 11-15 degrees, i.e. "smooth". The
    defect was lumpy GEOMETRY, not a rough surface. When a metric says a
    reported defect does not exist, suspect the metric.

71. **Close the chamber before falling back to the full floor.** The full floor
    keeps every chamber spur, and it was firing on teeth 4, 9, 23 and 28 --
    exactly the scraggly-incisor list. A morphological closing thickens the thin
    internal neck that broke the surface WITHOUT extending spurs, since a spur is
    thin in every direction. All four now mesh with the canal-only floor. The tree cannot emit a dead end, so
these arise where two canals in one root run close enough that their capsules
merge and a skeletoniser reads spurs off the merged blob. Teeth 18, 31 and 14
account for most of them.

Node is **not installed** on the Fedora box: `sudo dnf install -y nodejs24
nodejs24-npm`. Python side is `python3-pydicom python3-numpy python3-gdcm
python3-scipy python3-scikit-image dcm2niix dcmtk`.
