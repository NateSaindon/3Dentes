# CBCT-derived anatomy — plan

Agreed 2026-08-27, to be started on the Fedora desktop at a later date.

The alpha's ceiling is its source data: BodyParts3D is external morphology of a
single individual, with no pulp, no nerves, and no third molars. The plan is to
replace the hard tissue with a **CBCT volume the operator supplies** — a
full-mouth Vol. 1 study, roughly 600–700 DICOM slices.

This supersedes several options in [phase-2-options.md](phase-2-options.md); in
particular the procedural pulp-offset approach becomes a fallback rather than the
recommendation, since real measured anatomy beats an approximation.

## Why this is the right data

- **Pulp chambers and main canals** — the headline gap, from real anatomy.
- **The mandibular canal**, traceable from mandibular foramen to mental foramen:
  the inferior alveolar nerve path as a measured structure rather than a
  hand-drawn spline.
- **Third molars**, absent entirely from BodyParts3D.
- **Enamel/dentin separation** — sufficiently different in density to threshold.
- **PDL space, lamina dura, cortical vs trabecular bone, maxillary sinus.**

It also dissolves the licensing question for everything it replaces: no
ShareAlike inheritance, no attribution obligation on derived meshes.

## What CBCT will not give us

Set expectations before investing segmentation effort:

- **Fine canal anatomy is at or below resolution.** A full-mouth FOV implies
  larger voxels than a small-FOV endodontic scan — plausibly 200–300µm against
  75–100µm. Main canals segment well; lateral canals, apical deltas and isthmuses
  largely will not be present. **Read the actual voxel size from the DICOM
  headers rather than assuming.**
- **Restorations destroy their local neighbourhood.** Beam hardening from metal
  produces streak artifact that makes segmentation unusable nearby. Survey which
  teeth are affected before trusting anything segmented from those regions.
- **Radiopaque canal filling material images as the fill, not as native pulp.**
  Any endodontically treated tooth yields an excellent cast of the obturated
  canal space, which is not the same thing as natural pulp anatomy. Identify
  these teeth up front and label any resulting mesh accordingly.
- **No soft tissue.** CBCT resolves the *canal*, not the nerve; no gingiva,
  tongue, or muscle. BodyParts3D therefore stays in the project for soft tissue
  even once the hard tissue is replaced.

## Privacy — decide before the first commit

**This repo is public and auto-deploys to GitHub Pages.**

Stripping DICOM headers (name, DOB, institution, accession, device serials) is
necessary but not sufficient. **Dentition is forensically identifying** — that is
what it is used for. A published mesh of a specific person's jaw is identifiable
health data about them, permanently, in a public git history.

Options, all viable, operator's choice:

1. Keep DICOMs and derived meshes out of the repo entirely; generate locally,
   gitignored. The public build continues to use BodyParts3D.
2. Split: this repo stays public with BodyParts3D; a separate private repo holds
   the personal dataset and derived anatomy.
3. Make this repo private.

**This must be settled before any imaging-derived artefact is committed.** Git
history does not forget, and a public Pages deploy is immediate.

Related: bring only the operator's own imaging. No third-party patient data,
ever, regardless of de-identification.

## What to bring to the Fedora box

- **The DICOM series only.**
- **Not the vendor `.exe`.** It is a Windows viewer, irrelevant on Fedora, and
  unnecessary — DICOM is an open standard with better Linux tooling. Do not
  execute it.

## First session

1. **Read the headers before anything else** and report: scanner/manufacturer,
   FOV, voxel size, slice count and spacing, bit depth, reconstruction kernel.
   This determines what is realistically extractable and whether the rest of the
   plan is worth the effort. `pydicom` or `dcm2niix` — no GUI needed.
2. **De-identify** into a working copy; never modify the originals.
3. **Artifact survey** — identify restored and endodontically treated teeth, and
   mark which regions are untrustworthy.
4. **Segment** in 3D Slicer (free, Linux, strong volume-rendering and
   segment-editor tooling). Start with one tooth end-to-end — enamel, dentin,
   pulp — to prove the workflow before scaling to the full dentition.
5. **Export → decimate → glTF**, into the existing `tools/build-assets.mjs`
   pipeline. It already handles welding, smooth normals, y-up conversion,
   centring and the laterality assertion; CBCT-derived meshes should go through
   the same path and satisfy the same invariants.

Expect step 1 to change the plan. Do it before committing to step 4.

## Tooling on Fedora

`3d-slicer` (segmentation, the main tool), `python3-pydicom` / `SimpleITK`
(headers, de-identification, scripted volume work), `dcm2niix` (format
conversion), Blender (mesh cleanup — install when this work starts, not before).
