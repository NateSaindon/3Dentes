# CBCT-derived anatomy — plan

Agreed 2026-08-27. Revised 2026-08-29 after the operator confirmed the shape of
the dataset. To be executed on the Fedora desktop.

The alpha's ceiling is its source data: BodyParts3D is external morphology of a
single individual, with no pulp and no nerves. The plan is to replace the hard
tissue with **CBCT volumes the operator supplies**, segmented into real measured
anatomy.

This supersedes several options in [phase-2-options.md](phase-2-options.md); in
particular the procedural pulp-offset approach becomes a fallback rather than the
recommendation, since real measured anatomy beats an approximation.

---

## The dataset

**Three volumes, not one.** All are labelled "Vol. 1" by the vendor export; that
is the vendor's volume label, not a series relationship.

| Volume | Coverage | Role |
| --- | --- | --- |
| Central | Full dentition, both arches | **Reference frame.** Everything registers to this. |
| Mandible | Mandible only, focused FOV | Higher-resolution source for the lower arch |
| Maxilla | Maxilla only, focused FOV | Higher-resolution source for the upper arch |

**These are three separate exposures**, confirmed by the operator — not three
reconstructions of one rotation. This is the harder case and it drives the whole
registration strategy below. Do not assume a shared coordinate frame.

Each volume ships with several export folder types. Triage them before analysing
anything (see [Export triage](#export-triage)).

### Clinical facts that shape the work

- **28 teeth.** Third molars extracted; expect healed edentulous ridges at 1, 16,
  17 and 32.
- **Two restorations: zirconia crowns on 19 and 30.** Nothing else.
- **No endodontic treatment anywhere. No fillings.**

---

## Settled decisions

**Privacy — resolved 2026-08-29. Public is approved.**

This is the operator's own PHI and they have explicitly consented to the scan
data and derived meshes being public. The repo stays public and the Pages deploy
continues. The three-option decision recorded in earlier revisions of this
document is closed; imaging-derived artefacts may be committed here.

Two things that remain true regardless:

- **Still de-identify.** Strip name, DOB, institution, accession and device
  serials into the working copy. Consent to publish anatomy is not a reason to
  publish header metadata that serves no purpose.
- **A public push is permanent.** Rewriting git history does not retract what has
  been cloned, forked, or indexed. This is a note about irreversibility, not a
  reason to revisit a settled decision.

**Related, and not settled by the above:** bring only the operator's own imaging.
No third-party patient data, ever, regardless of de-identification.

**Do not run the vendor `.exe`.** It is a Windows viewer, irrelevant on Fedora,
and unnecessary — DICOM is an open standard with better Linux tooling.

---

## Why this is the right data

- **Pulp chambers and main canals** — the headline gap, from real anatomy, and
  with no endodontic treatment anywhere these are native and unobturated in all
  28 teeth.
- **The mandibular canal**, traceable from mandibular foramen to mental foramen:
  the inferior alveolar nerve path as a measured structure rather than a
  hand-drawn spline.
- **Enamel/dentin separation** — sufficiently different in density to threshold.
- **PDL space, lamina dura, cortical vs trabecular bone, maxillary sinus.**

It also dissolves the licensing question for everything it replaces: no
ShareAlike inheritance, no attribution obligation on derived meshes.

> Earlier revisions listed third molars as a fourth justification. They are
> extracted, so that value is void. The upside: 28 teeth in the CBCT matches 28
> in the current atlas exactly, making this a **drop-in hard-tissue replacement**
> rather than a schema expansion. `tools/manifest.mjs` keeps its structure, FMA
> ids stay the join key, and the notation derivation is untouched.

## What CBCT will not give us

Set expectations before investing segmentation effort:

- **Fine canal anatomy is at or below resolution.** A full-mouth FOV implies
  larger voxels than a small-FOV endodontic scan — plausibly 200–300µm against
  75–100µm. Main canals segment well; lateral canals, apical deltas and isthmuses
  largely will not be present. **Read the actual voxel size from the DICOM
  headers rather than assuming**, and read it per volume — the focused scans may
  differ substantially from the central one.
- **Restorations destroy their local neighbourhood.** See the artifact map below.
- **No soft tissue.** CBCT resolves the *canal*, not the nerve; no gingiva,
  tongue, or muscle. BodyParts3D therefore stays in the project for soft tissue
  even once the hard tissue is replaced.

---

## The multi-volume problem

The intuitive approach — splice the overlapping layers into one master volume —
fails for a reason that only becomes visible after the effort is spent.

### Why not one fused voxel volume

1. **CBCT gray values are not calibrated Hounsfield units.** They shift with FOV,
   exposure, scatter, and where the object sits in the beam. The same enamel
   reports different numbers in the central scan and in a focused scan. A spliced
   volume carries two intensity regimes, so no single threshold segments across
   the seam — which defeats the entire reason for having a volume.
2. **Resampling to a common grid is lossy in both directions.** Upsample the
   central scan and you fabricate detail that was never measured; downsample the
   focused scans and you discard the only reason they exist.
3. **The mandible is not rigid with respect to the maxilla.** Three separate
   exposures means condylar position almost certainly differs between them. No
   single rigid transform can align both jaws at once.

### The strategy: register in voxel space, fuse in mesh space

The **central volume is the anchor** and defines the coordinate frame.

Each focused volume gets its own **masked rigid registration** to it:

- **Maxilla volume** → central, with the metric masked to cranial and maxillary
  structure only.
- **Mandible volume** → central, masked to mandibular structure only.

Two independent 6-DOF transforms. Use **Mattes mutual information** as the
metric — it tolerates the differing intensity scalings that defeat thresholding.
In Slicer this is General Registration (BRAINS) with a fixed-volume mask, or the
Elastix extension.

Then **segment each arch in its own native, un-resampled grid**, where gray
values are internally consistent, and push the resulting *meshes* through the
saved transforms into the central frame. Geometry composites cleanly across
acquisitions; intensities do not.

Save the transforms as first-class artefacts. Every mesh produced from a focused
volume passes through one.

A resampled composite volume is still worth building **for a single clean
whole-skull volume render**. It should not be the thing anything is segmented
from. If built: harmonise intensities first by histogram-matching within the
overlap region, then prefer the focused volume where available with a few-voxel
linear ramp at the boundary.

### Validating a registration

Three checks, cheapest first. Do all three before trusting a transform.

1. **Invariant distance.** Measure the same landmark pair — two cusp tips on an
   unrestored tooth — independently in both volumes. Disagreement beyond ~2%
   indicates a `PixelSpacing` or slice-spacing metadata problem, not a
   registration problem. Fix that first or everything downstream inherits it.
2. **Checkerboard and difference view** across the overlap. Cortical outlines
   should run continuously through every tile boundary.
3. **Pilot-tooth A/B.** Segment the same unrestored tooth in both the central and
   the focused volume, then compare surfaces. This validates the registration
   *and* measures what the focused scan actually buys — turning "was the extra
   volume worth it" into a number instead of an assumption.

---

## Artifact map

No endodontic treatment means there is no obturated canal anywhere to be mistaken
for native pulp — a caveat earlier revisions of this document treated as a major
risk, now void. 26 of 28 teeth carry unfilled, natural pulp anatomy.

The two zirconia crowns are the whole of the artifact problem:

- **Zirconia is ~6 g/cm³ with Z=40.** Treat it as metal-equivalent for beam
  hardening, not as "ceramic, therefore benign."
- **Both crowns are mandibular, bilateral, at similar coronal level** (19 and 30
  are the mandibular first molars). The streak fan runs between them and across
  the midline.
- **Survey before trusting:** 18, 20, 29, 31, and — depending on cone angle — the
  opposing maxillary molars 3 and 14.
- **The mandible-focused volume is therefore the most compromised of the three**,
  despite being the scan meant to buy resolution in exactly that region. Weigh
  this in the pilot A/B comparison.

Turn it to advantage: zirconia thresholds well above enamel, so it isolates
cleanly. Segment it explicitly as a **prosthetic** label and exclude it from
enamel. The crown morphology on 19 and 30 is lab work, not natural anatomy, and
the atlas must not present it as such.

---

## The laterality trap

**Invariant 1 in `tools/build-assets.mjs` will not save us here.** The assertion
catches a structure *labelled* left sitting on the right. It cannot catch a
**globally mirrored volume** — if the source is flipped and the labels are
derived from the flipped source, the check passes while being wrong.

The usual escape is an asymmetric restoration, but 19 and 30 are bilaterally
symmetric and carry no laterality information at all. With third molars absent,
that asymmetry is gone too.

Establish L/R from `ImageOrientationPatient` instead. DICOM patient space is
**LPS**: +x points to the patient's *left*, so anatomical right is negative x —
which already matches the atlas convention. Then confirm against an asymmetry the
operator can independently vouch for.

---

## Export triage

Each volume ships with several export folders. Identify each before analysing
anything: file count, magic bytes, and the first file's header. Rank by fidelity,
not convenience.

| Export type | Verdict | Why |
| --- | --- | --- |
| Uncompressed DICOM, `ORIGINAL\PRIMARY\AXIAL` | **Use** | Full bit depth, real geometry, real `PixelSpacing`. The only substrate worth segmenting. |
| DICOM, lossless-compressed transfer syntax | **Use** | Equivalent once decoded. Confirm lossless JPEG / JPEG-LS / RLE, not baseline JPEG. |
| Vendor STL / OBJ auto-segmentation | Cross-check only | Useful as an independent sanity check on jaw shape and tooth count. Never the source — no pulp, unknown smoothing and thresholds. |
| Proprietary volume (`.vol`, `.inv`, …) | Fallback | Only if the DICOM export proves derived or downsampled. Reverse-engineering costs more than it returns. |
| DICOM marked `DERIVED\SECONDARY` | Skip | A re-render of the reconstruction, often windowed and re-quantised. Looks like DICOM, isn't the primary data. |
| JPEG / PNG slice stacks, PDF report | Skip | 8-bit, window-baked, lossy. Density information already destroyed; thresholding is meaningless. |
| Vendor Windows viewer `.exe` | **Do not run** | See settled decisions above. |

---

## First session on Fedora

1. **Copy the USB read-only, then work from the copy.** A full mirror of all
   three volumes and every export folder, untouched. The USB is not a backup.
   Budget ~25–30 GB of working space for three volumes plus resampled copies and
   Slicer scenes; confirm free disk and RAM before loading two high-resolution
   volumes into a registration.
2. **Header report across all three series.** Per volume: manufacturer and model,
   FOV, voxel size and isotropy, slice count, slice-spacing uniformity, bit
   depth, `ImageType`, transfer syntax, reconstruction kernel. `pydicom` or
   `dcm2niix` — no GUI needed. **This determines what is realistically
   extractable, and it may well change the plan. Do it before committing to
   step 6.**
3. **De-identify** into the working copy; never modify the originals.
4. **Convert to NRRD**, one file per volume. Watch for the irregular-slice-spacing
   warning — non-uniform spacing silently distorts every measurement made later.
5. **Artifact survey.** Step through the axial plane at the 19/30 crown level and
   quantify streak extent. Mark untrustworthy ROIs explicitly before any
   segmentation depends on them.
6. **Register.** Two masked rigid transforms against the central volume, then all
   three validation checks above.
7. **Pilot: one tooth, end to end** — enamel, dentin, pulp.
   - Start with **9** (maxillary central incisor): single large canal,
     artifact-free, proves the pipeline in about an hour.
   - Then **5 or 12** (maxillary first premolar): typically two roots and two
     canals — the multi-canal case, still well clear of the streak fan.
   - **Defer 3 and 14** (maxillary first molars) until the artifact survey says
     whether they are usable. They oppose the crowns directly.
   - Segment the pilot in *both* the central and the relevant focused volume, for
     the A/B comparison.
8. **Export → decimate → glTF** into the existing `tools/build-assets.mjs`
   pipeline. It already handles welding, smooth normals, y-up conversion,
   centring and the laterality assertion; CBCT-derived meshes go through the same
   path and satisfy the same invariants — including exact vertex welding, which
   matters more here, not less.

---

## Tooling on Fedora

- **3D Slicer** — segmentation, the main tool. Prefer the official build from
  slicer.org over the distro package; the extension manager is more reliable
  against it.
- **`python3-pydicom` / SimpleITK** — headers, de-identification, scripted volume
  work.
- **`dcm2niix`** — format conversion.
- **Blender** — mesh cleanup. **Not installed, and should stay that way until a
  pilot segmentation actually succeeds.** It is not needed for steps 1–7.

**Worth evaluating early: DentalSegmentator**, a Slicer extension using an
nnU-Net model trained on dental CBCT. It produces per-tooth instance masks, jaws,
and the mandibular canal — precisely the tedious parts. It will not split
enamel / dentin / pulp, but per-tooth masks to threshold *within* would be a
large accelerator. Verify it is current and Linux-supported rather than trusting
this note.

---

## Open items

- **Universal → FMA cross-check.** The mapping flagged in `CLAUDE.md` is
  self-consistent but unverified. Per-tooth CBCT geometry offers an independent
  test: tooth-type morphology is unmistakable, so a mapping that puts a
  premolar-shaped mesh under a molar's number shows up the moment the two sets
  are viewed side by side.
- **Whether the focused volumes earn their complexity.** Answered empirically by
  the step 7 A/B comparison, not in advance.
