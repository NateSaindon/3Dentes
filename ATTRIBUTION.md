# Attribution

## 3D anatomical models

All anatomical geometry in this project comes from **BodyParts3D**, produced by
the Database Center for Life Science (DBCLS), Japan.

> BodyParts3D, © The Database Center for Life Science
> licensed under CC Attribution-Share Alike 2.1 Japan

- Official project / downloads: https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html
- GitHub mirror used by this project (STL conversion by Kevin Mattheus Moerman):
  https://github.com/Kevin-Mattheus-Moerman/BodyParts3D
- Data release: version 3.0 (2011-09-15)

The mirror's README notes that release 3.0 was chosen over 4.0 because it has
fewer self-intersecting surfaces. This project inherits that choice.

Models are indexed by **Foundational Model of Anatomy (FMA)** identifiers, so a
filename like `FMA55697.stl` is the right upper second permanent molar. The FMA
ontology is maintained by the Structural Informatics Group at the University of
Washington.

## What this project adds

The 3Dentes source code, the clinical notation mapping in `data/teeth.json`, the
asset build pipeline in `tools/`, and all documentation are original work by
Nate Saindon, MIT licensed.

## Provenance of the model data

BodyParts3D is derived from imaging of **a single adult individual**. The
morphology is genuine human anatomy, not an idealized textbook composite. Root
counts, root curvature, and crown morphology reflect that one person's dentition
and will differ from textbook norms in places. See README.md for the full list of
what the source data does and does not contain.

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

CC BY 4.0 requires attribution but, unlike the BodyParts3D licence, carries no
ShareAlike obligation -- so meshes derived through this model do not inherit a
copyleft term. The model is used for inference only; no weights are redistributed
in this repository.
