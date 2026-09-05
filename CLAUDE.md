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
7. **A NEUROVASCULAR BUNDLE IS BUILT WHOLE OR NOT AT ALL.** Operator's rule,
   2026-09-04: where an artery, a vein and a nerve run together, all three go in
   at the same time. `tools/bundle.test.mjs` enforces it — every structure in
   the `vessels` or `nerves` layers names its `bundle`, and a bundle must carry
   at least one of each role. It is a check and not a note because the failure
   is SILENT: the greater palatine artery shipped alone and nothing said so, the
   mental artery had no vein for a release, and neither is visible in a render,
   because an absent vessel looks exactly like one you have not switched on.
   The exemption list is EMPTY and any entry must give an ANATOMICAL reason;
   "not built yet" is the thing being caught.
8. **Every ontology id names what the manifest says it names.**
   `tools/ontology.test.mjs` resolves each id against a vendored snapshot of the
   ontology's own labels (`tools/ontology-labels.json`) and fails the build if a
   structure carrying a BARE id shares no word with it. TWO NAMESPACES: FMA
   where the FMA has a term, IFAA Terminologia Anatomica Humana (`TAHU15802` in
   the manifest, `TAH:U15802` in the table) where it does not — which is every
   vein in this atlas. This is invariant 5 one level up: a tooth number
   can disagree with tooth morphology, but an FMA id is self-consistent with
   nothing, so a wrong one is invisible forever unless something looks it up.
   Two were wrong from 0.1.0 until 2026-09-04 — see below. The exemption list in
   that file has exactly ONE entry, and it earns it: the greater palatine vein
   carries the id of the pterygoid plexus it drains into, because no ontology
   names the vein and there is no bare sibling to vouch for the group.

### Which pulp and which split the maxillary nerves came from (2026-09-04)

Chased and settled. The shipped maxillary set was built from
`pulp-v2/pulp-connect.json` and `split-new/split.json`. Everything is now on
`pulp-v2` + `split-v3`, one input set across teeth, nerves and vessels.

190. **A NODE COUNT IS A FINGERPRINT.** Regenerating the maxillary nerves moved
    them 0.4-1.8 mm and the cause was invisible in the geometry, but the plexus
    came out with 700 triangles against the shipped 3,360/700 — one node fewer,
    because `pulp-connect/` has 24 upper foramina and `pulp-v2/` has 25. Its 19
    LOWER foramina then matched the 19 branches already recorded in
    `docs/cbct-nerve.json`, which confirmed it. With those inputs the plexus,
    the branches AND the infraorbital nerve all reproduce BYTE-FOR-BYTE.
191. **Three of four reproduced; the trunks mesh was stale.** `FMA77528T`
    (PSA/MSA/ASA) cannot be reproduced from any pulp x split combination
    available -- it was built from an earlier code state and never regenerated
    when its siblings were, and it sat 0.613 mm off. Regenerated, so the set is
    internally consistent for the first time.
192. **Choosing the split cost 0.013 mm.** `split-new` reproduces the shipped
    nerves; `split-v3` is what the TEETH are built from. Between them the
    maxillary nerves move 0.006-0.013 mm, a fifteenth of a voxel -- so the
    inconsistency was worth removing and the geometry barely noticed. The
    maxillary VESSELS were being built on `pulp-connect` + `split-v3` and are
    now on the same pair as the nerves, which matters because they ride the
    same arc.
193. **A TOOL MUST RECORD WHAT IT WAS BUILT FROM.** None of the above would have
    been a mystery if `nerve-maxilla.json` had named its inputs. Rule 116 said
    this about a transform's own description; it is just as true of a mesh.
    `nerve_maxilla.py` and `vessels.py` now write their input paths into their
    JSON output.

### The bundle rule, and two veins no ontology names (2026-09-04, 0.6.0)

186. **Drawing one member of a bundle asserts the others are not there.** A
    canal or a groove carries an artery, a vein and a nerve; a reader who sees
    only the artery reads that as the anatomy, not as a work queue. Hence
    invariant 7. Tagging the existing structures found two real gaps at once —
    the greater palatine had no nerve and no vein, and the mental artery had no
    vein — neither of which any render would have shown.
187. **NEITHER ONTOLOGY NAMES A GREATER PALATINE VEIN OR A MENTAL VEIN.**
    Checked against an FMA index carrying 3,741 vein terms, against the IFAA's
    own tributary lists for the pterygoid plexus and the facial vein, and
    against Wikidata. They take the id of what they DRAIN INTO with the repo's
    derived-mesh suffix — `TAHU4540P` off the pterygoid plexus, `TAHU15802M` off
    the inferior alveolar vein. That is the same reasoning that put the anterior
    maxillary tributaries on the infraorbital vein rather than under a tidier
    but wrong parent, and it is the most precise identifier that exists.
188. **A suffix-only group has nothing to vouch for it.** Every other suffixed
    mesh sits beside a bare sibling that agrees with the ontology label, so the
    group clears itself. `TAHU4540P` does not — the pterygoid plexus is not
    drawn — so `ontology.test.mjs` correctly refused it, and it is the first and
    only entry in that file's ALIASES. Recorded rather than worked around.
189. **The lateral member of a bundle is the one that meets the alveolar
    process.** The palatine vein at 0.75 mm across the groove grazed a root; the
    bundle was narrowed to 0.62 mm to fit. That is a constraint on the DRAWING,
    not a fact about the patient — the arrangement across the groove was already
    convention, and the groove is narrow.

### The greater palatine artery, and one toggle for two colours (2026-09-04, 0.6.0)

178. **One vessel here belongs OUTSIDE the bone.** The greater palatine artery
    runs forward in a groove ON the palate, under the mucosa, so `confine()` is
    exactly wrong for it. Its surface is found by casting a ray UP from the oral
    cavity, which meets the palatal plate first and can meet nothing else --
    rule 139's argument for finding skin, on a different surface.
179. **A COLUMN THROUGH A PALATAL ROOT IS NOT PALATE.** The upper teeth are
    their own labels, so they are holes in the bone mask, and a ray fired under
    a palatal root passes through it and stops on the bone ABOVE -- putting the
    artery 2.35 mm inside the root. The ray now stops at a tooth and the station
    is rejected.
180. **Scan for the gutter, do not guess a fraction of the way to the midline.**
    Stepping medially from each tooth centroid found 5 of 7 stations on the
    right and 3 of 7 on the left, because near the front the column above that
    offset is the incisive canal and the nasal floor. At any coronal level the
    palate's LOWEST point on each side IS the lateral gutter the groove runs in,
    so it can be scanned for: 21 and 19 stations, both sides, 44 and 38 mm.
181. **Smoothing pulls a course INTO a concave surface.** The palate is a vault,
    so a curve smoothed across stations that hug it moves toward the chord,
    which is up into the bone -- it came out 67% inside after smoothing that had
    been 0% before. Re-project after smoothing, not before.
182. **A graze shallower than ONE VOXEL is not a resolvable claim, and saying so
    is not the same as widening the tolerance.** Two palatine courses graze a
    root by 0.14 mm against a 0.16 mm voxel. They are counted and named
    separately rather than folded into the allowance, because moving a threshold
    until the number reads zero is how a check stops meaning anything.
183. **`IO_RADIUS_MM` was applied backwards and is now applied in the COURSE's
    own direction.** The constant is written posterior-to-foramen; the traced
    course is ordered anterior-first and the constructed fallback arc is not, so
    one `linspace` cannot be right for both. The traced branch had the thick end
    at the foramen, which is the reverse of the anatomy. `vessels.py` carries the
    matching pair and a note that the two must move together.
184. **Regenerating a mesh is not free, and three came back different.**
    Re-running `nerve_maxilla.py` to fix one calibre also rebuilt the plexus, its
    branches and the named trunks, and all three moved 0.4-1.8 mm -- so the
    SHIPPED ones were built from inputs other than the ones I passed. Only
    `FMA52978` was staged, and it was verified first: same triangle count,
    centroid shift 0.000 mm, a pure radius-ramp reversal. WHICH pulp and split
    the maxillary nerves were built from is now an open question, not a silent
    change.
185. **A per-structure appearance override needs the same check as a layer.**
    One vascular toggle carries red arteries and blue veins by naming a
    `material` per structure. An unknown material name would fall back to the
    layer's colour and every vessel would come out arterial red -- a wrong
    drawing rather than an obviously broken one, which is rule 135's whole
    complaint. `build-assets.mjs` now fails on an unknown material as well as an
    unstyled layer, and it was verified to bite.

### Vessels follow the bone now, not just the gaps between teeth (2026-09-04)

The operator's read: the maxillary vessels should curve the way the hard palate
does. They now do -- the maxillary arc is 100% inside measured bone against 83%
unconfined, and the incisive vessels 88% against 64%.

174. **"Out of the teeth" is not "in the bone", and the maxillary vessels needed
    BOTH.** The arc laid between apices floats wherever the arch is concave,
    which is nerve_maxilla's own finding about its nerves -- 72% of that mesh
    was outside bone, a median of 3.5 mm and up to 10.1 mm, in the sinus, until
    it was confined. `route()` now confines to measured bone with
    `nerve_maxilla.confine` and the same masks the nerves use, rather than a
    second opinion about where bone is.
175. **The two constraints FIGHT, and dentin has to go last.** Both bone masks
    FILL the teeth -- `nerve.bone_test` unions the lower-tooth class into the
    mandible and `maxilla_bone` fills each slice -- so "snap to the nearest
    bone" can land a point inside a root. Confining after clearing put two
    branches back a voxel deep. Confine first, clear second, and end with a
    clearing pass that has no confinement behind it.
176. **A field sampled NEAREST-NEIGHBOUR cannot answer a sub-voxel question.**
    Two branches reported travelling exactly 0.16 mm through dentin -- one
    voxel -- and no number of clearing passes moved them, because a point
    0.08 mm CLEAR of a root rounds into the voxel inside it. The clearances
    being asked about here are smaller than a voxel, so the signed field is
    interpolated. That is the difference between 2 of 76 and 0 of 76, and the
    2 were never real.
177. **I rebuilt a bone mask and walked into the trap its own docstring
    describes.** Measuring containment against a bare `lab == 2` minus teeth
    reported the inferior alveolar artery as 0.0% inside bone. `bone_test` says
    why in its second paragraph: the canal and the teeth are classes of their
    own, so they are holes in the mandible label, and it read 0 of 209 trunk
    points before that fill was added. Use the module, do not re-derive the
    mask. (The trunk still reads 44% because roughly half the fused canal lies
    beyond the centred volume's field of view, which is expected and is in
    nerve.py's own comments.)

### Every tooth has a supply and a drainage now (2026-09-04)

Sixteen vessel meshes, 120 structures. All 28 teeth get an artery and a vein;
0 of 76 branches travel through dentin.

168. **A dental branch MUST end inside the tooth, so "percent inside a tooth" is
    not the question.** The apical foramen is on the root, so the last fraction
    of a millimetre of every branch is in hard tissue by design. The first check
    counted mesh vertices inside the tooth labels and reported 7-12% on branches
    that were correct, which is unusable as a pass/fail. Measuring contact
    against DISTANCE FROM THE ENDPOINTS separates the connection from the
    defect, and the answer is 0 of 76.
169. **What is rendered is a TUBE, so clearing the CENTRELINE clears nothing.**
    The first router pushed each course until its centreline was outside the
    tooth labels, and the meshes still had 7-10% of their vertices in dentin,
    because a tube whose axis sits on the surface is half buried. The clearance
    a point needs is its own radius plus a margin.
170. **A signed field, or "far enough clear" cannot be asked.** A plain distance
    transform of the tooth labels is zero everywhere outside them, so it answers
    "inside or not" and nothing else. Subtracting the outside transform gives a
    field that can be asked for a margin.
171. **The anterior teeth have no supply without the INCISIVE vessels.** A chord
    from the canal to a central incisor is 22-26 mm and runs through bone, which
    is why nerve.py hangs the anterior teeth off the incisive nerve. The vessels
    had the same gap and it showed as teeth 24 and 25 having no drainage drawn.
    Neither ontology names an incisive artery or vein -- the FMA has no term and
    the IFAA lists only dental, peridental, mental and mylohyoid branches under
    TAH:U3863 -- so they take the repo's derived-mesh suffix off their own
    parent, exactly as the incisive NERVE does as FMA53243T.
172. **Split a branch mesh by TERRITORY when the ids are territorial.** One
    "upper dental" mesh has to be filed under either the anterior or the
    posterior superior alveolar artery, and is then wrong about half its own
    branches -- invariant 7's failure, self-inflicted. PSA and ASA branches are
    separate meshes with exact ids, and the anterior venous tributaries hang off
    the INFRAORBITAL vein rather than the posterior superior alveolar one,
    because that is where the anterior maxilla actually drains.
173. **Vessels ride the arc the NERVE plexus is already built on.** Three
    independent constructions of one course drift apart; the maxillary arc is
    the only thing here anchored to measured foramina, so the artery and vein
    are offsets off it rather than fresh guesses.

### The canal is an OVAL, and that is where the artery went (2026-09-04)

The infraorbital artery was held back the same morning because it came out 100%
and 89% buried inside the drawn nerve. It ships now, and nothing about the nerve
changed: the packing was measuring the wrong thing.

160. **`canal_r_mm` IS NOT A RADIUS, it is the EQUIVALENT-CIRCLE radius.**
    `io_centreline.centreline()` computes it as sqrt(area/pi), which for an
    ellipse is the geometric mean of the two semi-axes. Packing a bundle against
    it therefore assumes a circular lumen of the AVERAGE cross-dimension, and
    every millimetre of the long axis is invisible. Measured perpendicular to
    each canal's own tangent, the infraorbital canal runs 2.0:1 and 2.4:1 —
    semi-major 1.60 and 1.95 mm against semi-minor 0.85 and 0.90 — exactly the
    2.0-2.6 mm transverse against 3.8-5.5 mm vertical the CBCT literature
    reports for the foramen. The mandibular canal measures 1.17:1 on this
    patient, so the circular rule there was right, and that is now a
    MEASUREMENT rather than a lucky assumption.
161. **A cross-section belongs in the centreline file, not in the packing code.**
    `io_centreline.py` now records `semi_major_mm`, `semi_minor_mm` and
    `major_axis_lps` per sample, so the direction a vessel is placed along is
    measured on the same footing as the point it is placed at. Re-running it
    reproduced every existing `p` and `canal_r_mm` to 0.000000 mm before the new
    fields were trusted.
162. **Carry a DIRECTION through a transform as two points.** The major axis has
    to reach the atlas frame, and re-deriving "just the rotation part" of a fit
    expressed as centre + rotation + voxel translation means restating that
    convention in a second place — rule 116's complaint in a new costume.
    Mapping the sample and the sample-plus-half-a-millimetre and subtracting
    cannot disagree with how the points themselves moved.
163. **An eigenvector's SIGN is not a direction.** The major axis comes out of an
    eigen-decomposition, which fixes the axis and not which end is which, and it
    can flip between adjacent samples. Unoriented, the artery and vein swap ends
    wherever the solver changes its mind. Oriented by its own z component they
    do not. Rule 158, one week old, in a second place.
164. **The residual overlap is the NERVE's, and it is now measured.** The
    infraorbital nerve is drawn at an absolute 1.05 mm and is wider than its
    canal's SHORT semi-axis at 70% and 37% of samples, by up to 0.44 mm — never
    wider than the long one. So at the narrow ends no arrangement fits both, and
    4% of the right-side vessels still lie 0.014 mm inside it. Reported rather
    than tuned away, and the honest fix is the nerve's calibre.
165. **`IO_RADIUS_MM` is applied backwards from its own comment.** It reads
    "posterior -> foramen", but `io_centreline` orders the course ANTERIOR-FIRST
    and `nerve_maxilla` reads `io[0]` as the anterior end, so `linspace(1.05,
    0.80)` puts the THICK end at the foramen. Found while packing against the
    real ramp. NOT corrected: it changes a shipped mesh, and it is the
    operator's call.

### Veins exist, under a different ontology (2026-09-04)

166. **The FMA gap is real; the IFAA fills it.** Terminologia Anatomica Humana
    names all three — `TAH:U15802` vena alveolaris inferior, `TAH:U15803` venae
    dentales (its child, which is exactly the relation the dental branches have
    to the trunk), `TAH:U15485` vena infraorbitalis — and cross-references FMA
    wherever both exist, so the namespaces agree rather than compete.
    Operator's find; verified against the IFAA unit pages before use.
167. **The join-key field is still called `fma` and now holds TAH ids too.**
    Renaming it touches the manifest, the STL filenames, `teeth.json` and every
    consumer at once, which is the same reason `FMA53649` kept an inexact id.
    Worth doing deliberately, not as a side effect of adding six vessels.

### Arteries, and the vein the ontology does not name (2026-09-04)

`tools/cbct/vessels.py`. The inferior alveolar artery rides the MEASURED
mandibular canal on the identical centreline as the inferior alveolar nerve --
read through `nerve.canal_centrelines` rather than re-derived, so the two cannot
drift -- offset 0.80 of the canal's own local radius toward superior, 14 degrees
lingual, drawn at 0.13 of that radius. The mental artery leaves the measured
foramen on the mental nerve's own course. Both are `derived`: the canal was
measured, its contents were not, at any calibre.

155. **THE FMA HAS NO INFERIOR ALVEOLAR VEIN** — resolved the same day by
    rule 166; the veins ship under TAH ids. 3,741 vein terms -- facial,
    lingual, maxillary, the pterygoid plexus -- and nothing for the inferior
    alveolar, infraorbital, alveolar or dental veins, checked four ways. The
    atlas joins on FMA ids, so there is no honest id to hang blue on. Borrowing
    the artery's with a `V` suffix would mean "a part of the artery", which a
    vein is not, and inventing one puts back the exact defect invariant 7 was
    written for the same morning. Blue is blocked on IDENTITY, not geometry:
    `vessels.py` draws a vein the moment a caller supplies an id.
156. **A vessel inside another structure is a claim nobody can see** — the
    infraorbital artery ships now; the cause was rule 160, not the nerve alone. The
    infraorbital artery sits correctly inside its measured canal -- 0% of points
    outside the wall -- and still comes out 100% and 89% buried inside the DRAWN
    infraorbital nerve, by up to 0.85 mm. The cause is the nerve: it is drawn at
    an absolute 1.05 -> 0.80 mm in a canal whose measured radius averages 0.92
    and 1.03. The mandibular canal has no such problem because its nerve is a
    FRACTION of the measured lumen (0.55) rather than a millimetre figure. The
    artery is built and HELD out of the manifest; the fix belongs to the nerve's
    calibre.
157. **A clearance check must take the other structure's REAL radius.** The
    first version passed the artery's own `offset - radius` as the nerve's
    radius, which makes the test evaluate to zero by construction; it duly
    reported -0.000 mm on every infraorbital point and looked like a pass. Same
    family as enamel detector (c), and caught only because a figure that clean
    is not what real geometry looks like.
158. **Orient a lateral axis against ITS OWN component, not a per-side
    constant.** `cross(tangent, superior)` points whichever way the centreline
    happens to be ordered. Multiplying by `sign(midline - x)` flips both canals
    together and was 100% correct on today's data -- and 0% correct the moment
    the traversal reverses, which is rule 125's failure exactly. Comparing the
    axis's own x to the direction of the midline is true per point whatever the
    ordering, and was verified by reversing both centrelines.
159. **A new layer decides the camera unless told not to.** Adding the arteries
    widened the framed extent from 82.1 x 81.2 to 84.8 x 84.1 mm, because the
    mental artery runs an arbitrary 7 mm out of its foramen -- a drawing choice
    moving the whole model, which is rule 114 and the nerves' own reason.
    `arteries` is now in `NOT_FRAMING`.

### Two FMA ids named the wrong organs, and nothing could have noticed (2026-09-04)

`FMA53381` — the inferior alveolar nerve, its dental branches and its mental and
incisive branches, three meshes — is the **occipital part of the aponeurosis of
epicranius**. `FMA53088` — the superior dental plexus and its two derived meshes
— is the **lateral wall of the right orbit**. Both shipped in every release from
0.1.0. They are now `FMA53243` and `FMA77528`, resolved on EBI OLS4 and
cross-checked against Wikidata's P1402.

152. **The join key was the one identifier nothing checked.** README calls FMA
    ids "the join key throughout" and the manifest explains what the ontology
    is, and between them that reads like a claim someone verified. Laterality,
    tooth identity, provenance, layer appearance, shell count and version drift
    all had checks; the ids themselves had none, and they are the one field
    whose correctness cannot be inferred from anything else in the repo.
153. **A group check needs a member that must answer for itself.** The first
    version cleared an id if ANY mesh carrying it agreed with the label, because
    the B/T/M suffixes name parts and their names are legitimately free. That
    let `FMA52978` sit on "Mandible" without complaint — the real infraorbital
    nerve shared the id and vouched for it. A mesh carrying the BARE id claims
    to BE that structure, so it now has to agree on its own.
154. **The teeth and the tooth-adjacent anatomy were all correct.** 40 of 42
    ids resolve cleanly. The two that did not are both nerve structures added
    later and by hand, which is where an id gets typed rather than derived.

### Enamel: four automatic hole-detectors, all blind (2026-09-01)

The operator repeatedly reported blocks cut out of the enamel cap. Four metrics
were written to find them automatically and ALL FOUR were wrong, each in a
different way. None is worth retrying; the overlay sheets from `tissue_tune.py`
are the check, which is rule 74 and the `verify_overlay.py` precedent again.

  a. Bright tissue adjacent to the crown but unclaimed by any tooth. Scored 0.9%
     of the dentition and 0.5% on the tooth being complained about. Blind
     because the tissue beyond an arch-split contact face carries the
     NEIGHBOUR's label, so it is neither orphaned nor unlabelled.
  b. Fraction of the envelope BAND the cap fills, per sector. The envelope is a
     ceiling, not a target, so legitimately thin enamel scores like absent
     enamel: 19 of 28 flagged, including a canine at its own cusp tip.
  c. Fraction of crown SURFACE carrying any enamel. A TAUTOLOGY -- `SURFACE_MM`
     is painted unconditionally, so it is 100% by construction wherever a cap
     exists. Duly reported 26 of 28 perfect while holes were visible.
  d. Median enamel thickness at the crown surface, per sector, as
     distance-to-nearest-dentin. That distance collapses to one voxel near ANY
     lateral edge of the cap -- the CEJ, a contact face -- so it measures
     proximity to the cap's boundary, not its thickness. Flagged 28 of 28 on a
     cap whose voxels are 41-59% deeper than 0.5 mm.

WHAT THE REAL DEFECT WAS: the arch split ends each tooth at its contacts, and
that boundary is ARTIFICIAL -- two touching crowns share one contiguous mass of
enamel. Treating it as free tooth surface let `depth` read small there, which
opened the envelope and painted the surface shell across the cut, and where the
cut fell inside real enamel the cap ended in a clean straight edge. `outer_depth`
measures against the tooth UNION its neighbours so a contact face is interior.
The signature to look for is a STRAIGHT, axis-aligned edge in the cap: anatomy
does not produce those.

### All three exposures now supply geometry (2026-09-01)

Only the centred volume did until now. The two focused scans each see much more
of what they are aimed at — upper skull 54.0 cm3 against 31.3, mandible 32.1
against 21.6 — and `tools/cbct/export_extra_bone.py` contributes the difference
per exposure, so each scan supplies exactly the bone it alone measured.

Transforms are in `docs/transform-{maxillary,mandibular}-to-centered.json`. The
MAXILLARY one is fitted on the UPPER SKULL, not the mandible, which is not rigid
with respect to the maxilla across separate exposures. Held out of that fit, the
upper teeth land at Dice 0.708 against a ceiling of 0.728 — the evidence it is
right for reasons other than overfitting.

Layer layout follows the ACQUISITION, not the anatomy: everything the centred
volume measured is in `maxilla` or `mandible` however far from the teeth it
reaches, and each focused exposure's addition gets its own toggleable layer
(`midface`, `ramus`).

113. **Mesh in the MOVING grid, then transform the vertices.** The exposures sit
    about 35 mm apart in x, so resampling the maxillary label onto the centred
    grid discards every voxel that lands outside it — which is precisely the new
    anatomy. The centred volume's own bone is pulled INTO the maxillary grid to
    subtract, the remainder is meshed there, and only the finished vertices are
    mapped out. This is the plan's "register in voxel space, fuse in mesh space"
    for the same reason it gave.
114. **New bone must not decide where the camera looks.** The mid-face reaches
    75 mm above the occlusal plane, and letting it into `bounds()` moved the
    model's centre ~19 mm off the teeth — rule 48 again, except this time the
    geometry is measured rather than schematic, so "exclude it because it is
    invented" does not apply and "exclude it because framing is not its job"
    does. The `skull` layer is excluded from centring alongside muscles and
    nerves.
115. **Bone can be lost at EXPORT, not just at segmentation.** `export_bone.py`
    cropped the upper skull to within 22 mm of the upper teeth and dropped
    3.6 cm3 of labelled bone on the floor. Before generating anything to fill a
    gap, check what the pipeline already measured and threw away: unlabelled
    tissue at or above 400 HU in `centered` comes to 3.7 cm3 in 1,979 specks,
    so the segmentation had found essentially all of it.
116. **A transform's own description must name the label it was fitted to.**
    `register.py` hardcoded "rigid, mandible only" into every transform it
    wrote, so the maxillary run — fitted on the upper skull — described itself
    as a mandible fit. Nothing downstream reads that string, which is exactly
    why it would have survived indefinitely and misled whoever read it next.

### Inter-tooth contacts re-cut, and a second defect nobody had named (2026-09-02)

The contact-boundary fix that `docs/wishlist.md` lists as the DRR's prerequisite.
Overlay sheets (`tools/cbct/contact_tune.py`, one per contact, the rule-74
discipline again) found TWO defects where the wishlist described one.

  a. **The planar chord**, as documented. Visible at 5-6 and 11-12: a straight
     diagonal running the full length of a broad contact, through what the
     greyscale shows as continuous tissue.
  b. **Restoration bloom**, which was not in any doc. The zirconia on 19 and 30
     saturates, and its halo is labelled as tooth and then divided between the
     crowned tooth and its neighbour. 20 and 29 each carried ~1% of voxels at
     restoration density, which no natural tooth in this mouth reaches at all.

120. **A planarity metric ranks CORRECT contacts as the worst offenders.** All
    26 interfaces fitted a plane to 0.06-0.26 mm RMS, and the flattest of all
    (24-25, 0.06) is the one the image shows is RIGHT: at a tight contact the
    true boundary IS a small flat patch. Free-surface patches of equal area fit
    planes only ~2.3x worse, which is not the separation a usable metric needs.
    This is the fifth blind metric in this repo -- see the four enamel ones --
    and the sheets are again what actually found the defect.
121. **Watershed flooding cannot cut a uniform mass, and fails by LANDSLIDE.**
    Flooding on -intensity to put boundaries in the interproximal dip assigns
    each voxel to whichever marker reaches it across the lowest MAXIMUM
    elevation. Inside the lower incisor block every path ties, so the tie broke
    arbitrarily: tooth 26 grew 112% while 23, 24 and 25 lost about a third each.
    An ADDITIVE cost does not tie, because accumulated cost grows with distance
    and no front crosses a whole tooth for free.
122. **Cut pairwise, in a local crop, as a SAFETY property.** A pair can only
    redistribute tissue between those two teeth, so the landslide above is
    structurally impossible and the arch total is conserved exactly rather than
    as a checked outcome. It is also 8x faster than the whole-arch attempt.
123. **The seeds were the other half of the bug.** `refine_boundaries` eroded by
    3 iterations, ~0.5 mm, which is less than the depth a neighbour's proximal
    bulge reaches across the sector plane -- so the seed contained the wrong
    tissue and the boundary grown from it inherited the bias of the cut it was
    replacing. Seeds are now a fraction of each segment's OWN maximum depth,
    which scales with the tooth.
124. **Contralateral symmetry is the independent test here.** Nothing in the
    method optimises for it -- left and right are cut in separate local crops --
    so it cannot be gamed. Mean |L-R| volume asymmetry fell 3.09% -> 2.63% and
    improved on 11 of 14 pairs (one-sided p ~ 0.03). Modest, and 3 pairs got
    worse; real anatomical asymmetry puts a floor under it.
125. **The lower arch's label ids are REVERSED against `split.json`.**
    `split_arch` walks it from the patient's left, so `main()` iterates
    `range(n, 0, -1)` and label 1 is tooth 31, not 18. Assuming the two agree
    mirrors every lower-arch figure onto its contralateral pair -- which is the
    same tooth TYPE, so it survives a glance and every sanity check that only
    asks "is this a molar". `contact_tune.py` maps by centroid; do the same, or
    read the ordering from `main()`, and never index `split.json` by label id.
126. **This scan cannot measure zirconia density.** The volume saturates at
    3072 and 14-18% of each crowned molar is pegged there, while uncrowned
    second molars top out at 2403 and 2331. So 2500 finds WHERE the restoration
    is, cleanly, and says nothing about how dense it is. A DRR must take that
    figure from literature -- and the same ceiling means restoration bloom can
    be located but not unmixed from the tooth it sits on.

STILL OPEN after this: the crowned teeth's OUTER contour is still bloom-inflated
against bone and background. That is a segmentation problem, not a boundary one,
and re-cutting contacts does not touch it.

### Enamel tooling is present but NOT wired into the build (2026-09-01)

`tools/cbct/{enamel,enamel_audit,tissue_tune,enamel_test}.py` ship with 0.4.0 as
inert tooling so the work is not lost, but nothing in `build:assets` calls them
and no enamel structure is in the manifest. That is deliberate — the enamel work
lands with the DRR, and the contact-boundary fix in `docs/wishlist.md` is a
prerequisite for both. `npm run test:enamel` checks the one part that can go
wrong silently: the Universal-number-to-tooth-type mapping, against the
manifest's own derivation.

### Nerve courses re-derived against Malamed (2026-09-01)

`docs/wishlist.md`'s rule was followed: the geometry was re-derived first and
`SRC.malamed` added only to the structure that changed. The rest still cite
Wikipedia because Wikipedia is still what produced them — a citation is a claim
about provenance, not a compliment to a book.

117. **A nerve nobody tested against bone will float, and no metric complained
    for two weeks.** `nerve_maxilla.py` had no bone test at all, while
    `nerve.py` had had one since rule 108. 72% of the maxillary trunk mesh lay
    outside bone, a median of 3.5 mm and up to 10.1 mm out. Confining the
    courses brought that to 0.5 mm and 1.2 mm — the tube's own radius, i.e. the
    centrelines are now inside. The test only became meaningful once the
    maxillary exposure supplied enough mid-face to test against.
118. **Confining is not observing.** The trunks stay `schematic`. Bounded by
    measured bone is a real constraint and a real improvement, and it is still
    not the same claim as "seen in the scan". Do not let the improvement
    promote the tier.
119. **~~The infraorbital canal does not resolve~~ — WRONG, corrected
    2026-09-02. See rules 127-131.** The claim was that interior voids are all
    sinus and nasal cavity, aspect 1.1-1.7, no thin tube. The canal is there and
    the operator can see it; the METHOD was blind. Kept rather than deleted
    because the correction is the useful part.
    The other half of this rule stands: the mandibular foramen's landmarks need
    the ramus's posterior border and the coronoid notch — the ramus is still
    FOV-cut at y 23.7 against a box edge of 23.85 even with the mandibular
    exposure in, and no FOV ever contained a condyle.

### The infraorbital canal IS resolved, and five detectors said otherwise (2026-09-02)

The operator said it was plainly visible. It was. Five automatic methods were
written and every one failed, each for its own reason, and the reasons are the
point — a sixth detector is not what was needed.

127. **A void search cannot find a neurovascular canal, because the canal is not
    a void.** Rule 119's method filled the bone label and took interior voids.
    Voids in bone are AIR: the sinuses and the nasal cavity, exactly what it
    reported. The infraorbital canal carries a nerve, an artery and a vein, so
    its lumen is SOFT TISSUE. The method could never have found it, and the
    aspect ratio it quoted was measuring lumps of sinus.
128. **Nor can an enclosure test, because a through-canal is not enclosed.** It
    opens at the foramen in front and the inferior orbital fissure behind, so
    its contents are continuous with the face. A search for soft tissue enclosed
    by bone returned ZERO on both sides — the criterion was blind, not the
    anatomy absent. The same trap caught a region-grow that leaked into the
    cheek through the foramen.
129. **A narrow-width band is not a tube detector.** Non-bone voxels within
    2.4 mm of bone form a connected SHELL around every cavity in the midface, so
    the largest "tube" it found was 11,000 mm3 wrapping the whole sinus.
130. **The plane matters, and so does the structure's own axis.** Ring closure
    in a plane cut ACROSS a canal is the right idea and it still found nothing
    here at any threshold from 350 to 1000, with and without closing: this
    cortex does not close at a global threshold. Worse, the same reasoning
    applied to MY prior axis produced a display in which a round lumen appeared
    as a crescent, and I nearly rejected a correct tracing because of it. The
    tracing was round when measured against ITS OWN principal axis: ratio
    1.0-1.7, singular values [4.63, 1.31, 0.87], which is a tube. **When a
    tracing disagrees with your section geometry, suspect the geometry.**
131. **"Inside bone" is the wrong test for a nerve in a canal.** Rule 117 had it
    right for a schematic course that should be BOUNDED by bone. A canal is a
    void IN bone, so a tube correctly placed in one is correctly outside the
    bone label — the measured infraorbital reads 62.6% inside the bone union and
    that number means nothing. The test that means something is distance to the
    traced lumen: median 0.16 mm, max 0.99 mm, against a tube radius of
    0.80-1.05 mm.

132. **The centred volume's ceiling was the reason, and the operator called it.**
    The canal's posterior end reaches z 37.8 and that reconstruction stops at
    37.2 — six of 23 centreline samples fall outside its grid entirely, and
    sampling the left canal there reads -298, i.e. air, where the maxillary
    exposure reads 219. Anything read within a few millimetres of a
    reconstruction ceiling is suspect. Segment in the exposure that MEASURED the
    region, which for the whole mid-face is the maxillary one.
133. **Splitting a structure is sometimes what a provenance change costs.**
    `FMA77528T` (then `FMA53088T`) used to be "Infraorbital, PSA, MSA and ASA nerves", one mesh.
    Once the canal is traced the infraorbital nerve is `derived` while the other
    three are still textbook, and one mesh carries one tier — so leaving them
    merged would have meant either promoting PSA/MSA/ASA or hiding this. The
    infraorbital nerve is now `FMA52978` in its own right.
134. **A rule tuned to a constructed course will break when the course becomes
    measured.** MSA and ASA used to be hung on the trunk at the nearest point to
    the plexus node they serve, with that node lifted by `IO_ABOVE_MM` to reach
    a constructed arc. Against the real canal, which climbs to z 29-38 while
    every plexus node sits at the alveolus, the nearest point to ALL of them is
    the anterior end, and both branches collapsed onto the foramen. They are
    placed by arc length along the canal now, per Malamed.

### Learning the pulp from one traced tooth (2026-09-03)

`tools/cbct/pulp_learn.py`. The operator traced tooth 31 densely in the slicer
and asked whether that is enough to have the machine do tooth 30. Partly.

157. **A held-out TOOTH is the only validation that means anything, and the
    obvious spatial split is a trap.** Holding out the coronal half of the
    training tooth scored Dice 0.061 -- not because the model is that bad but
    because `along_axis` is one of its features, so the test asked it about
    values it had never seen. Interleaved bands within tooth 31 give 0.801, and
    a genuinely held-out tooth 19 gives 0.398. Only the last is a number.
158. **Read a Dice against the disagreement between two humans, not against 1.0.**
    The operator's dense tracing of tooth 31 scores 0.563 against the atlas's own
    older hand-trace of the SAME tooth. So 0.398 on a held-out tooth is about
    two thirds of the way to how well two serious attempts agree here, and
    quoting it against a perfect score would be meaningless.
159. **Break the score down by region before believing it.** Dice 0.393 overall
    on tooth 30 hid the actual behaviour: by thirds it is 4x too GENEROUS in the
    crowned coronal third, 1.8x too generous in the middle, and half too THIN
    apically. The classifier keys on "dark and central", which describes a pulp
    chamber perfectly and a one-voxel canal not at all. A single number would
    have shipped that as "mediocre" rather than as "wrong in two opposite ways".
160. **Classify the chamber, TRACK the canals.** No threshold and no hysteresis
    setting got the prediction closer than 2.1 mm to either measured apical
    foramen -- the canal is simply not visible to a voxel classifier down there.
    But both ends are known: the chamber is confidently classified and the
    foramina were MEASURED. Routing between them with `MCP_Geometric` over a
    cost field built from the classifier's own SOFT probability closes the gap
    to 0.40 and 0.18 mm for 0.7 mm3 of extra volume. The soft output is worth
    far more than the thresholded one; it still ranks a faint canal above the
    dentin beside it long after it has stopped calling it pulp.
166. **ONE CORRECTED TOOTH IS WORTH SIX OLD ONES, and after two the old ones
    start to hurt.** Held out on tooth 19: his 31 alone 0.306, his 31 plus six
    older sparse traces 0.398, his 30 and 31 both densely corrected 0.470, and
    all eight together 0.464. The loop pays immediately and the scaffolding
    should come down early.
167. **Never quote agreement with a correction the operator STARTED FROM.**
    Dice(my prediction, his corrected version) is 0.727, which is above the
    human-to-human 0.563 and means nothing: he edited my mask, so it is anchored
    to it. What his correction is good for is a TRAINING LABEL and a diagnosis
    of where the model was wrong — never as a score for the model.
168. **A prediction and a tracing must not share a directory.** The prediction
    goes to `predicted-pulp/` and says so in its own JSON provenance field;
    `slicer.py --mask` takes a comma-separated list so a session can load his
    tracings and my guess together while the files stay apart. In an atlas whose
    entire discipline is knowing where each surface came from, a machine guess
    filed among hand-traced masks is a provenance failure waiting to happen.

194. **`pulp_learn.py --threshold` IS A DEAD PARAMETER, and it prints a claim of
    rigour while doing nothing.** Line 384 reads `th = float(opt.get(
    "threshold", 0.30))`, line 385 prints *"threshold 0.30 (chosen on a HELD-OUT
    tooth, not on these)"*, and `th` is never referenced again. The segmentation
    uses the module constants `SEED_P = 0.50` and `GROW_P = 0.20`. Swept on
    held-out tooth 18 at 0.30, 0.45, 0.60 and 0.75 the output was 135.7 mm3 to
    the decimal every time. `--grow` IS wired (`opt.get("grow", GROW_P)`);
    `--threshold` is not, and there is no flag for `SEED_P` at all. This is
    worse than rule 163's silent failure: the run PRINTS a methodological claim
    that nothing in the code implements, and that line has been going into the
    provenance record of every prediction. Fix the wiring or delete the flag and
    the print; do not leave a knob that lies.

195. **Adding a third dense tracing made every prediction FATTER, and the
    obvious explanation is wrong.** Training on 30 + 31 + the operator's new 18
    (65.0 mm3, against the model's own 144.9 guess for that tooth) moved 12 of
    13 predictions UP, teeth 3, 14 and 28 by 18-21%. The tidy story -- that 18
    is mostly thin canal at dentin brightness and so teaches "faint is pulp" --
    is FALSE: measured across the three labels, 18 is the DARKEST and cleanest
    of them (median 679 against 707 and 839; 24.7% of its voxels above the
    dentin 5th percentile against 25.8% and 39.2%).

    **CAUSE FOUND the same day: the label that was wrong was 31, not 18.** He
    retraced 31 on the slicer and it came back 97.82 -> 72.08 mm3, a quarter of
    it removed, and what he removed had a median intensity of 1121 against 621
    for what he kept -- he was deleting DENTIN that had been called pulp.
    Retraining with only that label changed and everything else identical moved
    tooth 2 from 83.5 to 55.1 mm3 and tooth 3 from 87.9 to 55.0. The fat
    predictions were a fat training label propagating, and tooth 18 was never
    the problem; it was the tight label that made the conflict visible.

    Two things follow. **A training label is a measurement and needs the same
    scepticism as a prediction** -- 31 sat in every run for three days because it
    was hand-traced and nobody re-examined it. And **contralateral symmetry
    catches it**: `pulp_learn`'s own check flagged 18/31 at 34%, which is what
    prompted the retrace; the pair now agrees to 10%. Rule 166's trajectory was
    measured on Dice against an old trace, not on how much the operator has to
    DELETE, and those are not the same quantity.

    **Tooth 30 is the same vintage and has not been re-examined** (87.70 mm3,
    Sep 4). If it is fat by 31's factor its true volume is ~64.9, and the model
    predicts its contralateral 19 at 66.8 -- a 3% agreement that the current
    24% mismatch would become. Treat 30 as SUSPECT until retraced.

196. **`GROW_P = 0.20` is the WORST operating point available for the operator's
    effort, and 0.50 is the calibrated one.** Swept on held-out tooth 18
    (trained on 30 and 31 only) against his 65.0 mm3 tracing:

        grow   mm3    vs his   delete   paint   total edits   apex gaps
        0.20   135.7   2.09x    23013    5731         28744   [0.11, 0.29]
        0.35    95.2   1.47x    13813    6438         20251   [0.11, 0.03]
        0.50    67.4   1.04x     7922    7313         15235   [0.11, 0.03]
        0.65    48.6   0.75x     4346    8328         12674   [0.11, 0.03]

    The shipped default hands him 2.09x too much mask and 23,013 voxels to
    delete; 0.50 matches his volume within 4% and nearly halves the total edit
    burden. The apical routing also improves at every value above the default --
    0.29 mm to 0.03 mm -- and THAT signal is not anchored to his tracing, since
    the foramina were measured independently.

    **The caveat that keeps this honest:** he built that tracing by editing the
    0.20 mask, so per rule 167 the delete/paint split is anchored to it and is an
    effort ESTIMATE, not an accuracy score. The delete column is the trustworthy
    half; the paint column is the one anchoring flatters. Confirm on the next
    tooth traced from a 0.50 prediction rather than treating this as settled.

197. **The CEJ ring's 45%-of-length fallback is GONE, and the cheap fix that was
    queued for it was a tautology.** The recorded plan was to interpolate the
    NO-NARROW angles from their measured neighbours. Simulated first: teeth 2, 3
    and 15 moved **0.00 mm** and 14 moved 0.50. The reason is that on those four
    molars every no-narrow run is walled in by CLAMPED angles, which are
    themselves `cap_t` -- only 3 of 38 no-narrow angles touch a genuinely
    measured neighbour, so "interpolate from the neighbours" interpolates from
    the constant and returns the constant. Same cap-fallback tautology as rule
    5b's local-minimum attempt, in a new costume. **Simulate a fill before
    building one: ask what the donors actually are.**

    What shipped instead: an angle contributes ONLY if it measured a narrowing
    coronal of `cap_t`; everything else is NaN and is filled from that tooth's
    own measured angles. Because every surviving value is >= `cap_t` and
    interpolation is bounded by its neighbours, the ring can only move CORONALLY
    of the old constant, never further down the root -- so this cannot
    reintroduce enamel painted onto a root. All 28 teeth still produce a ring;
    20 of 28 scallops got SMALLER; median amplitude 1.57 mm.

    **Teeth 20 and 29 remain implausible at 4.08 and 4.15 mm and this change did
    not cause it** -- they were 4.96 and 5.26 before, so the constant was partly
    MASKING them. They are the neighbours of the crowned molars 19 and 30, which
    is the restoration bloom of open question 6 showing up in a third place.
    They have 29 and 28 measured angles, so this is not interpolation starvation;
    the readings themselves are distorted by the zirconia halo in the mask.

198. **THERE ARE TWO CEJ RINGS AND THEY ARE NOT THE SAME RING.** `enamel.py`'s
    `cej_ring()` is 36 angles read from the TOOTH MASK's cervical narrowing and
    feeds the enamel cap. `landmarks.py` has its own 24-angle ring read from an
    OTSU THRESHOLD ON THE ENAMEL, written to `landmarks.json`, and that is what
    `gingiva.py` and `crest.py` consume. The 1,008-angle / 53%-measured figure is
    28 x 36, so it is `enamel.py`'s, and that is the one rule 197 fixed.

    **The work order's claim that this ring "is also what the gingival margin is
    lofted from" is therefore FALSE**, and fixing the enamel ring did not move
    the gingiva at all. Worth noting for whenever gingiva comes off its deferral:
    the ring the margin actually uses derives the CEJ from the enamel, which is
    exactly the circularity `enamel.py`'s header rejects for its own ring
    (CLAUDE.md 97, 102). Two rings, two methods, one of them the method the other
    file refuses to use. Do not "unify" them without deciding which is right.

199. **A label of the right KIND beats more labels of the same kind.** Every pulp
    training label was MANDIBULAR -- 30, 31, 18 -- and every maxillary molar came
    back with its PALATAL canal unrouted: the buccal roots landed within 0.11 mm
    of their measured foramina while the palatal one sat 5.5-6.4 mm short, at
    both grow values, on all four of 2, 3, 14 and 15. It was not the operating
    point and it was not the masks. The model had never been shown a palatal
    root.

    The operator corrected tooth 3 in the slicer -- explicitly a LIGHT pass, not
    a reference tracing -- closing its own palatal gap from 6.34 mm to 0.06 mm.
    Retrained with that one maxillary label added, the other three fixed
    themselves: tooth 2 from 5.97 mm to 0.18, tooth 14 from 5.50 to 0.05, tooth
    15 from 5.58 to 0.10. **One rough label of an unseen structure was worth more
    than three careful ones of a structure already covered.** When a defect is
    confined to a class of anatomy, ask what class the training set is missing
    before touching parameters.

200. **ONE THRESHOLD CANNOT SERVE THE CHAMBER AND THE CANALS, and the operator
    saw it before any metric did.** His report, 2026-09-05: *"every trace YOU ran
    has completely empty chambers which I tried to fix"*. Measured, he was right
    -- his corrected molars carry 32-45% of their pulp coronal to the CEJ against
    the predictions' 8-28%, roughly half. The physical rules were innocent:
    applied to his own tracings they removed 0.02-0.73 mm3 and NOTHING from the
    chamber. It was the single global grow threshold.

    The two regions fail in opposite directions. In the crown a loose threshold
    is safe, because the chamber is a large confidently dark body with nowhere to
    leak; in the root a loose threshold is exactly what inflated the canals
    2.09x, because a canal one or two voxels across is partial-volume with the
    dentin around it. So `GROW_CROWN = 0.20` and `GROW_ROOT = 0.50`, split on
    the tooth's own measured CEJ ring -- the same landmark enamel.py bounds the
    cap with, so the chamber and the enamel cannot disagree about where the crown
    starts. On held-out tooth 18 that moves the crown fraction from ~17% to
    35.1% against his 33.5%, recovering 78% of his chamber volume.

    **And note what raising GROW_P to 0.50 that morning had actually done:** it
    bought volume calibration (2.09x -> 1.04x) by cutting the chamber ~35%
    (tooth 2, 10.3 -> 6.7 mm3). A single number tuned against a single summary
    statistic will do that -- total volume was right while the anatomy inside it
    got worse, and no contralateral or apex-gap check caught it. He did.

201. **A percentage is not a defect. The twelve ANTERIOR pulps sit at 12.8-25.4%
    crown (median 20.3%) against his molars' 32-45%, and that is NOT evidence
    they are wrong** -- an incisor's pulp is mostly canal while a molar's is
    mostly chamber, so the ratio differs for real anatomical reasons. Comparing
    them directly measures the wrong thing (rule 146). They are hand-traced and
    ship as `measured`; do not rewrite them off a ratio. Render them and let the
    operator read them.

202. **`pulp_learn.py` NAMES ITS OUTPUT `U<universal>` UNLESS `--fma` IS PASSED,
    and the build silently keeps the old mesh.** Meshing predicted-pulp-v8
    produced `U2-pulp.stl`, while `build-assets.mjs` looks for
    `FMA55697-pulp.stl` -- so the twelve corrected pulps were written into
    `assets/cbct/stl/` as ORPHANS and the build loaded the previous meshes from
    2026-09-03. Every invariant passed, the structure count was right, the app
    rendered, and 0.7.0 was reported as shipping a pulp fix it did not contain.
    Nothing checks that an STL in that directory is one the manifest asks for.
    Pass `--fma`, or rename before installing, and diff the STL mtimes against
    the build.

203. **A MASK THAT REACHES ITS CROP WALL MESHES OPEN, and nothing prints.**
    `marching_cubes` cannot close a surface at the array boundary, so it emits a
    rim of boundary edges. All twelve machine-predicted pulps hit this --
    54 to 136 open edges each -- because `pulp_learn` crops tight to the tooth,
    while the operator's own tracings came through padded and closed. The
    triangle count and the component count both look NORMAL, so `mesh_hand.py`'s
    own report said nothing.

    **The trap that nearly hid it:** the divergence-theorem volume of an OPEN
    mesh is not translation invariant. Tooth 21 measured 12.0 mm3 about the array
    origin and 1.1 mm3 about the scanner origin FROM THE SAME TRIANGLES, which is
    what made the numbers look impossible -- a permutation and a uniform scale
    cannot change a volume, and that contradiction is what exposed the open mesh.
    If a mesh volume changes when you move it, it is not closed. `mesh_hand.py`
    now pads by 2 voxels and shifts the crop origin to match, so this cannot
    depend on how the caller cropped.

### The nub was the CUT, and my detector was measuring the wrong thing (2026-09-03)

180. **A cost that is cheap through bright tissue lets a front run along a
    neighbour's ENAMEL.** `_cut_pair()` paid 1.0/mm through enamel and 7.0/mm
    through a dark gap, so reaching the contact and then racing around the
    outside of the neighbour's rim was cheaper than that neighbour crossing its
    own dentin to defend it. Every premolar and molar wore a rind of its
    neighbour as a mushroom at the cervical. The second term is depth in the
    UNION of the pair: a true contact is locally thick so the interior stays
    cheap, while a path hugging the outer surface is shallow all the way and now
    pays. Plus a straight-line guard on top.
181. **PROVE THE ISOLATION BEFORE MEASURING THE FEATURE.** Six morphological
    attempts on this nub, each measured, each reverted — and the thing being
    measured was never the nub. The opening residue I called "the nub" was the
    tooth's entire outer shell: 106 mm3, 1.12 mm from its own core and 5.7 mm
    from any neighbour's. Every HU figure and every conclusion drawn from it was
    about the wrong voxels. A detector for a feature is a hypothesis, and it
    needs a check of its own before anything downstream of it means anything.
182. **Regenerating the split regenerates the mouth.** Landmarks, crest, PDL,
    gingiva, per-tooth PDL and every pulp prediction all key off the labels, and
    `export_bone.py` decimates the gingiva for shipping. Skipping it put 621,534
    gingival triangles in the glb and took it from 12.3 to 26.8 MB -- the second
    time that step has been missed, and the second time the triangle count in
    the build output is what caught it.

### THE NUB IS THE CONTACT. CLOSED -- do not attempt a seventh fix (2026-09-03)

Rule 147 said wait for the intraoral scan. A seventh attempt was made anyway,
at the operator's explicit request, reverted at his call ("it looks worse now"),
and it is worth the space because it finally PROVED what 147 asserted. The
attempt reconstructed each crown's contour from the part of its surface that is
not at a contact -- tooth minus a band around its neighbours, closed along its
own curvature, keep only what falls inside -- and fed that decision to the
mesher as well as the mask. It removed the nub. It was still wrong.

183. **The nub and the contact are the SAME VOXELS, and three tests say so.**
    (a) HEIGHT: the material a clip removes sits 3.2-4.0 mm below the occlusal
    end and the measured contacts sit at 2.9-5.6 mm -- one band, no level at
    which the artefact can be cut and the contact spared. (b) RESTORING the
    contact after clipping puts the ball straight back, as a peg; that is the
    cleanest proof, because the restore was given only voxels the clip had
    taken. (c) The COST is symmetric: removing the bridge opened every
    interproximal contact from 80 um to 1.68 mm, which is a worse and far more
    obvious defect than the nub. Do not look for a smarter operator; there is
    no signal here to separate the two.
184. **"Cusps of the neighbour" tests NEGATIVE, and this is the fourth blind
    detector in this family.** Flooding each tooth from its own core through
    dense tissue (>500 and >700 HU, face connectivity) leaves 0.0 mm3
    unreachable on all 28 teeth -- so the nub is genuinely connected to the
    tooth it is labelled as, and nnU-Net did not mislabel it. The earlier probe
    that appeared to show an air gap between the nub and tooth 5's body was a
    SINGLE STRAIGHT RAY passing through a fissure. Rule 181 again, one level up:
    a ray is not a connectivity test.
185. **A trim that improves every proxy can still be the wrong answer.** The
    clip moved mean mesiodistal crown width against Wheeler from +1.08 mm to
    +0.16 mm, improved contralateral asymmetry 3.48% -> 3.06%, and held
    interpenetration at 0.0000 mm3 on all 26 contacts. Three independent
    measures, none of them optimised for, all better -- and the operator looked
    at it once and said it was worse. He is right: open contacts across the
    whole arch are not something a metric here was asked about. THE RENDER IS
    THE ACCEPTANCE TEST, the numbers are only how you get there.

The proximal contour is decided by the INTRAORAL SCAN, which measures the crown
surface directly. Nothing in the CBCT can settle it. If this comes up again the
answer is "147, 183-185", not a new operator.

### Zero overlap, and who gets to say what "measured" means (2026-09-03)

177. **Two surfaces found independently from grey levels WILL cross, however
    good the labels are.** Trimming the bridge got interpenetration from 4.80
    mm3 to 0.17, and 18 of 26 contacts still overlapped, because each tooth's
    isosurface is computed from its own blended field and then Taubin-smoothed
    on its own. Fixing it needs both: the SEGMENTATION alone decides the surface
    within 0.48 mm of a neighbour, so the two teeth read one boundary; and each
    stops `CONTACT_EPS` short of it, because 26 passes of smoothing afterwards
    will otherwise push them back through each other. 0.05 leaves three contacts
    crossing, 0.08 leaves none. Result: 0.0000 mm3 on all 26, gap 40-203 um,
    median 87.
178. **A hairline gap is more honest than a merge.** Two teeth touch over a
    contact AREA; they do not share substance. Representing that as two solids
    40-203 um apart is closer to the anatomy than one fused mass, and at a
    median of 87 um it is half a voxel -- 1.3 at the widest contact -- so
    nothing is being claimed that the scan did not resolve. NOTE this range was
    quoted as 60-96 um until 2026-09-03, when it was re-measured across all 26
    contacts rather than a subset; the conclusion did not change but the figure
    was too tight to be true.
179. **`measured` records that the SCAN decided it, not which algorithm read the
    scan.** I had the fourteen classifier-segmented pulps as `derived` while the
    teeth, mandible and maxilla -- all nnU-Net output -- sat at `measured`. The
    operator pointed out the inconsistency and he is right: the distinction I
    was drawing was between neural network and gradient boosting, which is not
    an epistemic distinction at all. What matters and what the METHOD text must
    carry is that fourteen of them have not been reviewed by eye. Tier for
    provenance, method for caveats.

### The contact bridge, trimmed at last (2026-09-03)

174. **The contact bridge is in the LABEL, and only a big enough opening finds
    it.** DentalSegmentator infers at 0.43 mm, two crowns in contact are one
    voxel apart at that scale, and the label bridges them WIDER than either
    crown. The split then halves the bridge, so each tooth carries a lens about
    3 mm across on its proximal surface and a matching notch where the
    neighbour's fattened label was kept out of it. `debridge()` in
    `export_teeth.py` removes label that is (a) removed by a morphological
    opening and (b) within 1.5 mm of a SAME-ARCH neighbour -- same-arch because
    cusp tips are thin too and sit against the opposing arch, so an
    arch-blind proximity test shaves every cusp in the mouth.
175. **Pick the radius by measuring, not by eye, and measure the thing
    complained about.** r=3 (0.48 mm) was invisible; r=5 and r=7 were not.
    Interpenetration between neighbouring crowns, by exact voxel intersection
    over ten contacts: 4.80 mm3 at r=0, 0.42 at r=5, 0.17 at r=7 -- a 29-fold
    reduction for about 1% of each tooth. Two earlier attempts at this were
    no-ops that I measured and reverted; the difference here is that the
    quantity measured was the one the operator could see.
176. **Smoothing tuned for a hand tracing is not enough for a prediction.**
    30 Taubin passes suited the operator's masks, which are coherent slice to
    slice because a person drew them. A predicted mask changes its mind voxel by
    voxel, and 30 passes leave that as visible faceting. 60/16 fixes it; Taubin's
    lambda/mu pair is close enough to volume-preserving that the extra passes
    cost 1-7% rather than thinning the canals away.

### Pulp for every molar and premolar, and a canal the ML could not help (2026-09-03)

169. **AN SVD AXIS HAS AN ARBITRARY SIGN, and here it was always +z.** So
    `along_axis = 1` meant the CROWN on a lower tooth and the ROOT APICES on an
    upper one, and a model trained on lower molars hunted the pulp chamber at
    the wrong end of every upper tooth: 305 mm3 for an upper molar whose pulp is
    nearer 100, apices 4-5 mm adrift. Orient any axis you derive against
    something anatomical before you use it as a feature. The arch is enough.
170. **26-connected in, TWO SURFACES out.** Masks that pass `ndi.label` with
    `np.ones((3,3,3))` as one component can still be only corner-connected, and
    marching cubes splits there: teeth came out of the mesher in 4 to 47 pieces
    while every mask looked single. Select the final component with FACE
    connectivity (`generate_binary_structure(3, 1)`) and the surface is one.
171. **Contralateral symmetry is the acceptance test that costs nothing.** With
    no second tracing to check a prediction against, the same tooth on the other
    side is free ground truth of a sort. Seven of eight pairs agreed to within
    16%; the eighth, tooth 18, differs by 47% and is also the only tooth whose
    pulp is twice the median fraction of its own volume. Two independent
    measures picking out the same tooth is worth more than either alone.
172. **A prediction can be good and still useless.** Trained on the operator's
    complete left mental canal, the model predicted the right at Dice 0.483 with
    recall 0.662 -- a real held-out score -- and added 103 mm3 of canal. It
    moved the anterior end by 0.2 mm. His blanks were at the anterior end, where
    the canal is genuinely invisible, and the model reads the same voxels he
    does. **Check WHERE a prediction adds before crediting HOW MUCH it adds.**
173. **`buccal_foramen` searched the whole canal, which only worked while the
    canals were short.** Given the longer predicted canal it put the mental
    foramen 18 mm posteriorly, under the external oblique ridge where the
    mandibular canal legitimately runs near the buccal cortex, and threw the two
    sides from 1.9 mm apart to 4.6. Only the anterior third is searched now. A
    rule that depends on its input being small should say so or enforce it.

### The slicer: tracing stops being done on contact sheets (2026-09-03)

`tools/cbct/slicer.py` + `slicer.html`. A localhost server and a page: three
linked planes, scrub, window, paint, save. It emits exactly what
`trace_canal.py import` emits -- one boolean `.npy` per structure on the
volume's own grid plus a `traced.json` -- so `io_centreline.py`,
`combine_traces.py` and `trace_foramina.py` read it unchanged.

    slicer.py nrrd/mandibular.nrrd out --names mental-right,mental-left
    slicer.py nrrd/centered.nrrd out --tooth 30,31

152. **The contact sheet was a tooling limit, not an operator limit.** Every
    tracing so far was marked on static PNGs because a sheet is what the
    importer could read, and it cost real accuracy: the pulp's first round
    failed outright (leave-one-out Dice 0.076 on 1.6 mm axial sections) and the
    mental canal needed two rounds. The operator named it: "it's hard for me to
    orient the anatomy if I'm not able to slice through actively myself". The
    answer was not a better sheet.
153. **Masks are held on the CROPPED grid and expanded only at save.** A
    whole-volume bool mask is 134 MB; 28 pulps would want 3.7 GB. Cropped to one
    tooth they are about 2 MB each, which is what makes `--tooth` viable, and
    the file written is still full-grid so nothing downstream knows or cares.
154. **The tool must not add anything between the brush and the file.** No
    smoothing, no interpolation, no closing -- `trace_canal.py`'s importer had
    to close across 1 mm section gaps, and this one has no gaps to close. Rule:
    if a tracing is wrong afterwards, the TRACING is what changes, and that only
    holds while nothing else touches it.
155. **A headless browser must be killed in a `finally`.** `cdp.mjs` killed
    Chrome on its last line, so every run that threw before reaching it orphaned
    a browser tree -- twelve processes and fifteen profile directories in one
    session, which the operator noticed as his CPU disappearing. It now kills on
    `exit`, `SIGINT`, `SIGTERM`, `uncaughtException` and `unhandledRejection`.
162. **`(a[i], a[:, i, :], a[:, :, i])[plane]` EVALUATES ALL THREE.** Building
    the tuple indexes every axis before the subscript picks one, so a slicer
    request for axial 135 of a 185x185x135 crop passed its own bounds check and
    then raised IndexError on the sagittal expression it never needed. The
    handler died without writing a response, the fetch rejected, and the pane
    went black -- every slice past the SHORTEST axis was unreachable, 100 of 505
    on the tooth crop. The operator found it within minutes of real use.
    It survived my testing because the only volume I tested against was 512^3,
    where all three axes are equal, and `--tooth` -- whose entire purpose is a
    crop that is NOT a cube -- was added afterwards and never swept. **Test a
    tool that indexes three axes on a volume whose three axes differ.**
163. **A tool used alone must never fail silently.** Two changes, both worth
    keeping: a handler that raises now answers 500 with the exception text
    instead of dropping the socket, and the client checks that every slice it
    receives is exactly the length it expected. A short or missing response used
    to feed NaN into every pixel and paint the pane black, which looks
    identical to "the anatomy ends here" -- the single worst way for a tracing
    tool to fail. It now writes the error on the pane and in the message line.
164. **`pkill -f <name>` kills the shell that ran it.** The command line of the
    bash wrapper contains the pattern, so `pkill -f slicer.py` matched itself
    and killed the session -- twice, silently, leaving the server never started
    and a stale log that looked like the fix had not worked. Enumerate `/proc`
    and filter by executable, or accept losing whatever else was in that shell.
165. **`window.META` is always undefined for a top-level `let`.** A classic
    script's top-level `let` goes into the global LEXICAL environment, not onto
    `window`, so a readiness probe of `window.X` never fires however long it
    polls. Probe `typeof X === 'object'` instead. Cost twenty minutes of
    debugging a page that was working.

### Teeth were shipping in pieces, and nothing checked (2026-09-03)

144. **A tooth is one solid, so its surface is ONE SHELL — and 23 of 28 were
    not.** Every tooth carried a detached second component, 25 mm3 on the molars
    and 1-12 mm3 on the premolars. The masks were single connected components on
    both the old and the new split, so nothing upstream was wrong: the
    grey-level isosurface closes a SECOND shell around the pulp chamber, which
    DentalSegmentator does not include in the tooth label. Teeth 20 and 29 were
    worse and that part was mine — restoration-density claiming left their
    surfaces in 27 and 23 pieces against their crowned neighbours.
    `keep_solid()` in `export_teeth.py` drops everything but the largest
    component, before decimation so the triangle budget goes to the tooth, and
    fails outright if a discarded piece is over 6% of the tooth's volume.
    This was NOT what the operator was looking at -- see 147.
145. **The build had three invariants and needed a fourth.** Laterality, tooth
    identity and provenance were all checked; connectivity was not, so this
    shipped through every release since 0.2.0 without a murmur. `shellCount()`
    in `build-assets.mjs` now fails the build for any tooth that is not a single
    shell, and it was verified to bite by feeding it the old mesh.
146. **Measure the thing the operator is describing, not the thing that is easy
    to measure.** Told the teeth overlapped, I measured contralateral volume
    asymmetry (already fine), then a vertex-parity interpenetration test (2-3%),
    then the same test on the .glb (13-18% — the meshes are not quite
    watertight, so parity leaks), then penetration depth by nearest-triangle
    normal (0.06-0.24 mm). Four numbers, three of them wrong, none of them the
    defect. An exact voxel intersection on a shared grid finally gave a figure
    to trust: 0.13-1.06 mm3 per contact, a sliver, and unchanged by the re-cut.
    The overlap was never the problem. RENDERING ONE ISOLATED TOOTH showed the
    defect in a single image, which is what he had done to find it.
147. **EVERY POSTERIOR CONTACT IS BRIDGED IN THE SEGMENTATION, and the split
    divides the bridge rather than removing it.** This is the lump the operator
    means. On the isolated tooth it is a disc about 3 mm across on the proximal
    surface at the cervical, and the neighbour has a matching one within 0.3 to
    1.4 mm -- at teeth 3/4 both sit at (-17.6, -18.5, -10.1). It is 2.5-7.3 mm3
    per tooth, HU 930-1750, and nnU-Net labels all of it `upper teeth`.
    It is IN THE MASK: meshing the label alone with no grey-level blending
    reproduces the disc exactly. Two mesher-side theories were tried and both
    were no-ops, measured and reverted -- clamping the surface to a 3-voxel band
    around the mask changed nothing (it never strayed that far), and widening
    the grey/shape blend across the embrasure moved tooth volumes by 0.4% and
    left the disc untouched.
    The cause is resolution: DentalSegmentator infers at 0.43 mm, two enamel
    surfaces in contact are one voxel apart, and the label bridges them wider
    than either crown. The teeth really do touch, so there is no gap to find and
    nothing to threshold. Fixing it means deciding the proximal contour rather
    than measuring it -- WAIT FOR THE INTRAORAL SCAN, which measures the crown
    surface directly and is the only thing that can settle it. Do not shave the
    protrusions: the same erosion test that finds them also finds every cusp
    tip.

148. **A trace sheet cut on a straight axis is only as good as the canal is
    straight.** The mental canal is not: the operator's own tracing runs 33.9 mm
    along a 23.2 mm chord. Sections perpendicular to that chord meet the canal
    obliquely at both ends and turn a round hole into a smear indistinguishable
    from a marrow space, which is what he meant by "the trabeculation made it
    difficult". Measured against his tracing, round 1 put the canal a median of
    3.3 and 3.6 mm off tile centre and as much as 6.6 mm — nearly at the edge of
    an 8 mm window. `trace_canal.py` now takes a PATH as well as two points and
    cuts each section perpendicular to the local tangent, with the frame carried
    along by parallel transport so consecutive tiles do not spin. Round 2, cut
    on his own round-1 tracing: 0.40 and 0.20 mm off centre, and 37/44 and 30/39
    sections contain the canal against 22/29 and 24/30.
    **The second round of a tracing should be cut on the first.** The operator's
    tracing is a far better prior than anything derived from the segmentation
    that failed, and iterating costs one export.
150. **THE MANDIBULAR CANAL DOES NOT STOP AT THE MENTAL FORAMEN, so the
    anterior end of a tracing is not the foramen.** It runs on as the incisive
    canal, and an operator following the lumen goes straight past the exit — the
    "anterior end" is wherever the canal became too faint to follow, which is
    why the landmark moved 3.0 and 2.8 mm between round 1 and round 2 of the
    same canal. Both tracings say so plainly once looked at: the last few
    millimetres run MEDIALLY, into the symphysis, which is the opposite of the
    way a nerve leaves a jaw. The foramen is instead the canal's CLOSEST
    APPROACH TO THE BUCCAL PLATE, which is measurable on the traced course, and
    it comes out at z -42.7 and -43.3 with the two sides 23.6 and 21.8 mm from
    the dental midline. The old rule's asymmetry was the giveaway and I read it
    as tracing noise: the mental branches measured 3.6 mm on the left against
    26.8 on the right, and on the buccal-plate definition they are 4.2 and 3.4.
    `buccal_foramen()` in `nerve.py`, shared with `nerve_face.py`.
    The infraorbital canal is the opposite case and its anterior end IS its
    foramen, because that canal really does end there. Which end of a tracing
    means something depends on the canal.
151. **Check that a sheet is centred on the thing before sending it.** Sampling
    the previous tracing through the new sidecar's own centre/u/w gives the
    offset in millimetres for nothing, and it is the difference between handing
    someone a better sheet and telling them it is better.

### The face, and a layer that had no material (2026-09-02)

`tools/cbct/nerve_face.py` is new and builds the terminal branches of the
infraorbital nerve into the face — 18 branches in four named groups, both ends
measured on this patient. The mental fan is deliberately absent; see 141.

135. **A layer with no entry in MATERIALS is not unstyled, it is a WHITE
    METAL.** `midface` and `ramus` shipped in 0.4.0 with no appearance, and
    glTF's default for a primitive with no material is white, metalness 1,
    roughness 1 and single-sided. A fully rough metal under this environment
    happens to look like pale bone, so at full opacity nobody saw it for a day;
    but a metal has no diffuse term, so the instant either opacity slider moved,
    the layer became grey smoke instead of translucent bone. The operator
    reported it as "the slider is broken". `build-assets.mjs` now fails the
    build for any layer in use with no appearance. Eight materials for nine
    layers is the kind of gap only a count catches.
136. **Rule 108's per-slice fill is the WRONG instrument for a cutaneous
    branch.** Filling the mandible closes the canal and the teeth, which are
    their own labels and would otherwise read as holes. Filling an AXIAL slice
    of the MID-FACE does something else: the maxilla, zygomata and nasal bones
    close a ring, and the fill declares the sinuses and the nasal cavity to be
    bone. It condemned 16 of 18 branches on the first run, every one correctly
    running in soft tissue over the front of the maxilla. A canal nerve is
    tested for staying INSIDE bone and a facial branch for staying OUT of it,
    and the two want different masks.
137. **`confine()` has a mirror image, and the face needs it.** These nerves lie
    ON the facial skeleton, not in it, and a straight ray from the foramen does
    not know that: the infraorbital rim stands directly above the foramen and
    the canine fossa bulges below it. `ride()` pushes each offending point out
    along its own shortest way out and re-smooths, which is `confine()` run
    backwards. Smoothing between pushes can pull a point back into a plate one
    voxel thick, so the last word goes to the push, repeated until clear.
138. **"The first air" is not the skin, and no amount of tuning makes it so.**
    Four rules were tried on rays cast OUTWARD from the foramen and all four
    failed on cavities inside the face: first air stops in the maxillary sinus
    4 mm out; first air lasting 3 mm stops there too, because a sinus is 30 mm
    across; first air outside a FILLED head mask fails because the nasal airway
    is open at the nares and at the choanae and drains the sinuses through the
    ostia, so it is a hole in no plane and axial, coronal and sagittal fills all
    leave it open; and the LAST tissue-to-air transition is right about cavities
    and wrong about the face, since a ray aimed medially leaves this cheek,
    crosses the nose and ends on the far side of the head.
139. **Cast INWARD instead, or ask whether anything is outside the crossing.**
    A ray that starts outside the patient meets skin first and can meet nothing
    else — that is how the foramen's own depth and the face's outward normal are
    measured (11.2 mm right, 9.6 mm left). For a branch, which must keep its own
    direction, the equivalent question is asked at each crossing: can this point
    leave the patient in a straight line? Only the outside can. Test a SPREAD of
    directions, not one — from the skin beside the nose the face's general
    outward direction goes through the nose, and from the lower eyelid it goes
    through the brow, which failed 13 of 18 branches.
140. **A course laid flat never surfaces, so make the rise a search, not a
    constant.** The subcutaneous branches were specified by which way along the
    face each group heads, which says nothing about how steeply it rises through
    it; the medial superior labial branches were still 10 mm deep 40 mm out,
    past the lip and heading for the chin. Each branch is now steepened by
    successive factors until the patient's own skin stops it within that group's
    plausible length, and the factor it needed is recorded. What SELECTS the
    course is the length cap, so those caps are anatomy, not tolerances.
141. ~~**Projecting a landmark onto a curve cannot beat the curve.** The mental
    foramen lands at z -44.2 with the inferior border at -43.7 — OUTSIDE the
    mandible, about 4 mm too low.~~ **WRONG, and wrong the very next morning.**
    The first half stands: the segmented canal really does stop 11 mm short of
    the premolar window on the right, so "nearest point to the premolar apices"
    really does return the end of the curve rather than a foramen. The
    conclusion did not. **-43.7 is not the mandible's inferior border, it is
    where the centred volume's reconstruction FLOOR cut the bone off.** The real
    inferior border is at z -59, in the mandibular exposure — the 12 cm3 of bone
    that exposure was registered in to supply, and which `FMA52748M` has carried
    since 0.4.0. Measured against the whole mandible the old landmark sits
    14 mm above the inferior border, inside the bone, and roughly where a mental
    foramen belongs. Nothing was 4 mm too low and nothing was outside the bone.
    This is rule 132 exactly, at the other end of the volume: anything read
    within a few millimetres of a reconstruction boundary is suspect, and I had
    written that rule about the maxillary CEILING the day before while
    measuring the mandible against a truncated FLOOR. **Before calling a
    structure mispositioned, check that the thing you measured it against is
    whole.**
142. **The tracing was still worth having, and it moved the foramen 3 mm.**
    The operator traced both mental canals the next morning (80.3 and 87.2 mm3,
    within 8% of each other, traced independently). The foramina come out
    15.6 mm and 15.0 mm above the inferior border and 19.0 and 20.9 mm from the
    dental midline — symmetric, and where the literature puts them. They sit
    3.0 and 2.8 mm from the projected points. So the projection was not broken,
    it was imprecise, and the honest description of what the trace bought is a
    3 mm correction and a foramen that is MEASURED rather than inferred. Both
    `nerve.py` and `nerve_face.py` now read it from `docs/cbct-mental.json`, so
    the trunk and its facial branches cannot leave the bone at different points.
143. **|x| is not laterality, and this is the third time.** CLAUDE.md recorded
    the mental foramina at |x| 18.4 right against 26.3 left as a KNOWN LIMIT, an
    8 mm asymmetry. Measured from the DENTAL MIDLINE at x 3.5 they are 23.2 and
    23.1 mm — symmetric to a tenth of a millimetre. Same family as the
    `export_teeth.py` false failure and the "right maxilla" that spanned both
    sides. Anything sided gets measured from the dental midline, always.

## Deployment

`.github/workflows/deploy.yml` runs `build:assets` with no environment. It used
to need `TOOTH_SOURCE=cbct`, and without it the deploy published the BodyParts3D
alpha while every local review ran against the CBCT build — the site was a
different model from the one being approved and nothing said so. That whole class
of bug went away with the second build; there is one model now.

Every structure in `tools/manifest.mjs` must have a mesh in `assets/cbct/stl/`.
Listing one that does not fails the deploy with ENOENT, which is how the nerves
broke the build once. Add the STL first.

## The changelog is part of shipping

`CHANGELOG.md` records what changed in the **published** app, and it is linked
from the README so it is visible on the repo page. Every commit on `main`
deploys, so the file groups commits into releases rather than listing each one.

**Before any push that changes what a user sees, update it in the same commit**,
and move `version` in `package.json` to match. Minor for anatomy or interface
changes a user would notice, patch for fixes and corrections. Keep the
`[Unreleased]` section current as work lands, and promote it to a numbered
release when it is pushed.

**A provenance change IS a user-visible change.** When a structure moves between
`measured`, `derived` and `schematic`, or when what it is built from changes,
that alters what the atlas claims about itself and belongs in the changelog even
if nothing on screen moves. Invariant 6 exists for the same reason.

Do not backdate or rewrite released entries; correct them in a new patch release
with a note saying what was wrong.

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
    module's docstring exists to prevent. `nerve-terminal.stl` / FMA53243T (then FMA53381T).
112. **MSA and ASA must arise FROM the infraorbital nerve.** They were free
    stubs in the sinus. The infraorbital nerve is now built from the
    pterygopalatine fossa forward to its foramen, with MSA and ASA descending
    from it and PSA still leaving V2 directly -- so the rendered tree matches the
    branching order. Still entirely SCHEMATIC; nothing of it is resolved.

Nerve tissue renders YELLOW (`nerves` in build-assets.mjs MATERIALS), the
convention in every anatomy atlas. Arteries red and veins blue are on the
wishlist; the inferior alveolar artery and vein share the measured canal with
the nerve, which is a provenance trap worth reading before starting.

~~KNOWN LIMIT: the mental foramina sit at |x| 18.4 right against 26.3 left. The
right canal centreline is the weaker of the two.~~ **Wrong, 2026-09-02.** That
is |x| about the SCANNER's origin. About the dental midline they are 23.2 and
23.1 mm, symmetric to a tenth of a millimetre — see rule 142. The right
centreline really is the weaker of the two, but for a different reason: it stops
11 mm short of the premolars, which is rule 141.

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

Node IS installed on the Fedora box (v24.18.0, npm 11) as of 2026-09-01 — the
line that said otherwise was stale. Python side is `python3-pydicom
python3-numpy python3-gdcm python3-scipy python3-scikit-image dcm2niix dcmtk`.

**Run `tools/cbct/*.py` with `~/projects/3Dentes-cbct/nnunet-venv/bin/python`,
not system python3.** The venv carries `fast_simplification`, nnU-Net and the
rest; system python3 has scipy but NOT fast_simplification, so `decimate()` dies
with a bare ModuleNotFoundError *after* the expensive segmentation and meshing
work has already run.
