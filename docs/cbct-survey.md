# CBCT dataset survey — first session findings

Performed 2026-08-29 on the Fedora desktop, against the USB labelled `NLSCBCT`
(7.4 GB vfat, 5.4 GB used, 6876 files).

This is the **header report and artifact survey** called for by steps 1, 2 and 5
of [cbct-plan.md](cbct-plan.md). It is **evidence**, and where it disagrees with
the plan, it wins — several of the plan's premises about this dataset turn out
not to describe what is actually on the disc.

Nothing on the USB was modified. Steps 3 (de-identify), 4 (NRRD), 6 (register)
and 7 (pilot) are **not** done.

## What exists now

- Repo at `~/projects/3Dentes`.
- Read-only mirror at `~/projects/3Dentes-cbct/usb-mirror` (5.4 GB, 6876 files,
  verified equal file count, `chmod -R a-w`). Deliberately **outside** the repo
  tree so it cannot be committed by accident.

Analysis was done with a ~60-line dependency-free DICOM header/pixel reader, so
none of the below is blocked on tooling. For the real work, install:

```bash
sudo dnf install -y python3-pydicom python3-numpy python3-gdcm dcm2niix dcmtk
```

(3D Slicer separately from slicer.org, per the plan.)

---

## 1. Export triage — use `*_3rdparty`

Each volume ships three export folders plus a stray top-level `.dcm`.

| Export | Verdict | Why |
| --- | --- | --- |
| `*_3rdparty` | **Use this** | Uncompressed explicit-VR LE, `ORIGINAL\PRIMARY\AXIAL`, **16 bits stored**, `RescaleSlope` 0.0625 |
| `*_examexport` | Redundant | Same geometry, **12 bits stored**, slope 1 |
| `*_wrapngo` | Redundant | Pixel data **byte-identical to `examexport`** (SHA-1 per slice). Also carries the Sirona Windows viewer — do not run |
| `*_dcm.dcm`, `CT2`, `COMP*`, `EPDF*`, `RAWEXAM*` | Skip | `DERIVED\PRIMARY`, 8-bit, or the PDF report |

**The extra bits in `_3rdparty` are real, not a left-shift.** The low nibble is
non-zero in 93.8% of voxels, so it carries genuine 0.0625 HU quantisation against
the 1 HU of the other exports. Both cover the same physical range and both clip
at the same ceiling (below), so this is a modest win rather than a decisive one —
but it costs nothing to take it.

No lossy or compressed transfer syntax anywhere. Every CT series is
`1.2.840.10008.1.2.1`.

---

## 2. The three volumes are the same resolution and the same FOV

This contradicts the plan's dataset table, which describes the two arch volumes
as "focused FOV, higher-resolution source".

All three series are **identical in geometry**:

| | value |
| --- | --- |
| Scanner | Sirona **XG3D**, 85 kVp, 7 mA |
| Matrix | 512 × 512 × 512 |
| Voxel | **0.16 mm isotropic** |
| FOV | 81.9 × 81.9 × 81.76 mm |
| `ImagePositionPatient` | `-40.96 \ -58.074258 \ -44.520221` — the same in all three |
| Slice spacing | exactly one unique Δz = 0.16, **no irregular spacing anywhere** |
| Bit depth | 16 allocated |

So the focused volumes buy **no resolution at all**. 160 µm is also better than
the plan's assumed 200–300 µm.

What differs between them is only **where the same 8 cm box was aimed**. The
identical `ImagePositionPatient` is not evidence of a shared frame — it means
each volume is expressed in its own scanner-centred frame, which is exactly why
they still need registering.

**Consequence for the plan:** the step-7 A/B question, "whether the focused
volumes earn their complexity", is now partly answered in advance. They cannot
buy detail. They can only buy coverage and beam positioning.

---

## 3. Coverage — this inverts the roles the plan assigns

| Volume | Acquired | What is actually in it |
| --- | --- | --- |
| **centered** | **2025-06-27** 11:45 | **Both arches complete**, occlusal plane centred. Pulp chambers and canals plainly visible. |
| **mandibular** | 2026-08-28 10:04 | Full mandible incl. inferior border and symphysis. Maxillary crowns clipped at the top edge. |
| **maxillary** | 2026-08-28 10:10 | Mid-face and sinuses. **The maxillary occlusal surfaces fall below the FOV floor.** |

The maxillary volume is the surprise. Its highest value anywhere is ~1600 HU in
the bulk histogram and it contains essentially no enamel-class tissue — hard
tissue appears abruptly (0 → 10,987 → 25,601 voxels in three slices) as a full
14-tooth arch cross-section, which is the signature of a cut plane, not of an
occlusal surface. Curve of Spee and Wilson guarantee cusps would enter gradually
over several millimetres if the crowns were inside the box.

**So `maxillary` is not an upper-arch source.** It is a sinus / root-apex /
nasal-anatomy volume. Useful — the maxillary sinus floor and the root apices
projecting into it are beautifully resolved — but the upper crowns are not in it.

**`centered` is the only volume containing complete upper and lower crowns, and
should be the primary segmentation source, not merely the registration anchor.**

---

## 4. The centered volume is fourteen months older than the other two

`SeriesDate` / `ContentDate` are consistent across all three export flavours:

- **centered — 2025-06-27**
- mandibular — 2026-08-28 10:04:08
- maxillary — 2026-08-28 10:10:02

`StudyDate` in `_3rdparty` and `_examexport` reads 2026-08-28 11:39:34 for all
three, which is the **export session**, not the acquisition. Only `_wrapngo`
carries the true study date. Trust `SeriesDate`/`ContentDate`.

This is a real registration hazard the plan does not account for: the reference
frame predates the arch volumes by over a year. Mitigating it: **both zirconia
crowns are already present in the 2025 volume**, so no restorative change
occurred between the exposures. Worth confirming nothing else did.

---

## 5. Zirconia saturates the reconstruction ceiling

**The reconstruction clips at 3072 HU** (the top of a −1024-offset 12-bit range),
in both encodings. **22% of crown voxels sit at that ceiling.** Their true
density is unrecoverable, and the crown surface is therefore bounded by where
clipping and beam hardening blur it, not by a measured edge.

The two crowns, by connected component above 2600 HU in the mandibular volume:

| Tooth | Side | Volume | Centroid x |
| --- | --- | --- | --- |
| 19 | patient LEFT | 385.6 mm³ | +21.3 mm |
| 30 | patient RIGHT | 289.5 mm³ | −18.7 mm |

**The plan's claim that "zirconia thresholds well above enamel, so it isolates
cleanly" is half right.** Threshold alone does *not* separate them — incisal
enamel on the lower anteriors reaches 2900–3050 HU and touches the same ceiling.
What does work reliably is **threshold ≳2900 followed by a connected-component
size filter**: that yields exactly the two crowns as large components, with
natural enamel appearing only as scattered sub-50-voxel fragments. Use that,
not a bare threshold.

Streak survey: the crown fan is confined to the mandible as predicted. The
**maxillary volume is essentially crown-artifact-free** (max 2605 HU, a handful
of voxels at its very bottom edge), which supports the plan's choice of maxillary
teeth for the pilot — though see §3, those crowns are outside its FOV, so the
pilot must come from `centered`.

---

## 6. Enamel/dentin separation is weaker than the plan assumes

The bulk histogram of `centered` shows:

- **Air ≈ −624 HU**, which is the floor of the data — not −1000.
- **Soft tissue peaks at 100–300 HU**, not 0.
- **Bone** is a long flat shelf from ~500 to ~1400 HU.
- **Enamel** is only a faint bump at 1800–2000 HU after a shallow trough at
  1700–1800.
- A spike at 3000–3099 HU: the clipped zirconia.

There is **no clean valley between dentin and enamel** — the distribution
declines monotonically with only a slight inflection. The plan's "sufficiently
different in density to threshold" overstates it. Enamel/dentin will need
region-growing or local thresholding per tooth, not a global cut.

This also confirms the plan's core point about uncalibrated values, more strongly
than expected: **do not carry any HU threshold over from medical CT literature.**
Air, soft tissue and bone are all displaced from their nominal values here.

---

## 7. Laterality

The headers are self-consistent and match the atlas convention:
`ImageOrientationPatient` = `1\0\0\0\1\0` and `ImagePositionPatient.x` = −40.96
in every series, so column 0 is x = −40.96, and under DICOM LPS negative x is the
patient's **right**. Anatomical right is negative x, as `build-assets.mjs`
requires.

As the plan warns, that only proves internal consistency — it cannot detect a
globally mirrored volume. The plan notes that the bilateral crowns and absent
third molars leave no asymmetric landmark. **The survey found two anyway:**

1. **Nasal septum.** The nasal airway is consistently larger on the patient's
   left — by 2–4× at most levels sampled through the maxillary volume. Read under
   the header's own convention, **the septum deviates to the patient's right.**
2. **Crown bulk.** Tooth 19 (left) measures 33% larger than tooth 30 (right),
   386 mm³ vs 290 mm³ — though on saturated, beam-hardened metal this is a weaker
   signal than the septum.

**Two questions for the operator, and the volume's handedness turns on the first:**

- Does your septum deviate to your **right**?
- Is your lower **left** first molar crown noticeably bulkier than the lower right?

If the answer to the first is "no, it deviates left", every volume is mirrored
and the pipeline must flip before anything is segmented.

## 8. Tooth count — not independently verified

Automated counting was attempted and does not work reliably: enamel blobs are not
teeth, since multi-cusp molars split into several components at a given level
while adjacent teeth merge at their contacts. Counts of 15–16 per slice through
the mandibular band are *consistent with* 14 mandibular teeth, but that is not a
verification. The rendered arch views support a full complement with no third
molars. **Left for visual confirmation by the operator.**

---

## De-identification scope (step 3, not yet done)

Nine identifier tags are populated in the CT headers and must be stripped into
the working copy:

`PatientName` · `PatientID` · `PatientBirthDate` · `PatientSex` ·
`InstitutionName` · `InstitutionAddress` · `ReferringPhysician` ·
`StationName` · `StudyDescription` · `StudyID` · `SoftwareVersions`

`AccessionNumber` is present but empty. `DeviceSerialNumber`,
`OperatorName`, `PerformingPhysician` and `RequestingPhysician` are absent.

Note `StudyDescription` and `StationName` are free-text vendor fields worth
inspecting rather than blindly retaining.

---

## Revised recommendations

1. **Segment from `centered`.** It is the only volume with both complete arches,
   and it carries visible pulp anatomy. This is a change from the plan, which
   casts it only as the registration anchor.
2. **Keep `mandibular`** — it earns its place for the mandibular inferior border,
   symphysis and the canal, which `centered` truncates. Register it in.
3. **Reassign `maxillary`.** Not an upper-arch source. Retain for maxillary sinus,
   root apices and nasal anatomy.
4. **Registration strategy is unchanged and now better motivated** — two masked
   rigid transforms onto `centered`, Mattes MI. The 14-month gap and the
   differing aim make a shared frame even less plausible than the plan assumed.
5. **Drop the resolution half of the A/B comparison.** All three volumes are
   0.16 mm isotropic; there is no extra detail to measure. The pilot A/B is still
   worth running to quantify beam-positioning and artifact differences.
6. **Zirconia:** threshold ≳2900 HU then keep the two largest connected
   components. Label as prosthetic, exclude from enamel.
7. **Plan step 4's irregular-slice-spacing warning does not bite** — spacing is
   exactly uniform in all three volumes.
