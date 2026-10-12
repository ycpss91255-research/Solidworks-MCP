# STEP reference repair validation (2026-10-12)

This is a failed repair investigation, not evidence of complete MR12 recovery.
The existing recovery guard must continue rejecting packages whose recorded
STEP references point outside their private generation.

## Isolation

The stdio client loaded the independent recovery worktree's exact TOML with
automatic CAD launch and the recovery monitor disabled. Every CAD operation
asserted test PID 3264. Only private SWR12.5-15 part and STEP copies were opened;
documents were hidden in that test application. Working PIDs 2836 and 19780
were not targeted. This does not establish zero shared CPU or memory usage.

## Results on SolidWorks 2023 SP5 (31.5.0)

- The copied part has an `MBimport` feature and `Is3DInterconnectFeature=True`.
- Native `IFeature.GetImportedFeatureParameters`, with correctly allocated
  output pointers, returned error 0 and an `IImport3DInterconnectData` object.
- `GetAuthoringInfo` reported `STEP AP203`.
- Setting the data object's filename succeeded in memory, but committing it
  through `SetImportedFeatureParameters` returned error 2 (incompatible type).
- Selecting the feature before committing produced the same error.
- Copies at short ASCII paths with both `.stp` and `.step` extensions also
  produced error 2. Thus long paths and Chinese filenames do not explain this
  particular failure.
- `ModifyDefinition` returned false. Legacy `GetImportedFileName` returned an
  empty string and `SetImportedFileName` returned false for this feature.
- No successful save or recorded-link repair was established by these probes.

The filename getter can resolve to a private copy while the saved document's
recorded dependency still names an original source. Do not use that getter,
copied STEP bytes, or a zero Pack and Go status alone as recovery acceptance.

Probe helpers and model copies are ignored under `test-results/`. The native
interface marshal generalization used for investigation is retained there as
`native_interface_probe.py`, rather than added as unused production behavior.

## Primary API contracts

- [SetImportedFeatureParameters](https://help.solidworks.com/2027/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~SetImportedFeatureParameters.html)
  documents the error enumeration and the required 3D Interconnect check.
- [Import error codes](https://help.solidworks.com/2021/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.sw3DInterconnectImportErrors_e.html)
  defines code 2 as an incorrect specified file type.
- [SetImportedFileName](https://help.solidworks.com/2027/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~SetImportedFileName.html)
  applies to imported features; its presence does not imply applicability to
  this `MBimport` feature in the tested release.

The cause of the STEP commit refusal and a lossless reference repair remain
unresolved. Do not disable the guard or break source links to claim success.

The test application closed normally through its PID-bound API. PID 3264
was subsequently absent; working PIDs 2836 and 19780 retained their creation
times. No forced process termination was used.
