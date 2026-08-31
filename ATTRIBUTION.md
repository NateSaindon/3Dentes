# Attribution

## 3D anatomical models

All geometry in this repository is segmented from a single cone-beam CT (Sirona
XG3D, 0.16 mm isotropic) of the project's author, Nate Saindon, published with
his explicit consent. Teeth, mandible, maxilla, pulp, periodontal ligament,
gingiva and nerves — one person, one dataset.

The imaging data itself is not in this repository, and no third-party patient
data appears in it.

**No reuse licence has been granted for the anatomical meshes.** They are a
named living person's medical imaging, published for this project. The code is
MIT (see [LICENSE](LICENSE)); the anatomy is not covered by it.

## What this project adds

The 3Dentes source code, the clinical notation derivation in `tools/manifest.mjs`,
the asset build pipeline in `tools/`, and all documentation are original work by
Nate Saindon, MIT licensed.

## Foundational Model of Anatomy

Structures are indexed by **FMA identifiers**, so a filename like `FMA55697.stl`
is the right upper second permanent molar. The FMA is an anatomy ontology
maintained by the Structural Informatics Group at the University of Washington.
It supplies identifiers and nomenclature only — no geometry.

## DentalSegmentator (pretrained nnU-Net model)

Per-class segmentation of the CBCT volumes (upper skull, mandible, upper teeth,
lower teeth, mandibular canal) uses the DentalSegmentator pretrained nnU-Net
model, Dataset112_DentalSegmentator_v100.

- Model: https://zenodo.org/records/10829675 — **CC BY 4.0**
- Extension and code: https://github.com/gaudot/SlicerDentalSegmentator
- Dot, G. et al. *DentalSegmentator: Robust open source deep learning-based CT
  and CBCT image segmentation.* Journal of Dentistry (2024).
- nnU-Net: Isensee, F. et al. *nnU-Net: a self-configuring method for deep
  learning-based biomedical image segmentation.* Nature Methods 18, 203-211 (2021).

CC BY 4.0 requires attribution but carries no ShareAlike obligation, so meshes
derived through this model inherit no copyleft term. The model is used for
inference only; no weights are redistributed in this repository.

## Previously: BodyParts3D

The alpha built its geometry from **BodyParts3D** (© The Database Center for Life
Science, CC BY-SA 2.1 Japan). Every one of those meshes has since been replaced
by measured CBCT anatomy, and the vendored STLs were removed from the repository
on 2026-08-31. Nothing in the current build, and nothing distributed here, is
derived from BodyParts3D — so the ShareAlike obligation no longer reaches any
part of this project.

Recorded because it was true of releases up to and including the alpha, and
because anyone reading the git history will find those meshes there.
