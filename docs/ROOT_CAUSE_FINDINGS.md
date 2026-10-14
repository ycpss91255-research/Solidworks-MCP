# SolidWorks crash findings — 2026-10-14

The investigation reproduced two native failures on SOLIDWORKS 2023 SP5
(31.5.0.52), using separate owned instances and private model copies. MCP/API
operations trigger them; the faults occur inside the native CAD process.
This is evidence for specific failing API/model-state paths, not a finding that
every historic crash has one cause or that all MCP operations are safe.

| Finding | Evidence | Prevention |
| --- | --- | --- |
| Imported-reference dependency query | `IModelDocExtension.GetDependencies` with `AppendImportedPaths=true` reproduces `sldapiu.dll` access violation at offset `0x8a24c0`; false returns an invalid scalar in the control. Failure also reproduced at approximately 64% committed memory. | Typed pywin32 guard blocks this exact query before invocation. Raw native calls can bypass it. |
| Existing distance-mate conversion followed by document close | Combined `IsAdvancedMate=true` / `ModifyDefinition` edits reproduce native solver/MFC failures. Exception-time dump shows an invalid read through `rbp=0xffffffff` during mate/feature/assembly destruction servicing `CloseDoc`. | Create fresh limit mates from the existing endpoints, rather than converting the old feature kind in place. Explicit identity-change acknowledgment is required. |
| Memory pressure | Windows resource-exhaustion event independently establishes historical commit exhaustion. Native fault controls above also reproduce without exhaustion; successful fresh-mate control ran at higher commit usage than one failing control. | Respect explicit open-document memory-warning cancellation. Memory pressure does not explain every native failure. |
| Timeout | One traced replay timed out during comtypes type-library loading. Filtering generated-code tracing allowed completion. | A timeout alone does not prove a CAD crash. Correlate the PID, last API, native event and process exit. |

The fresh-mate control preserves 68 component transforms exactly and completes
the original four-mate follow-up, save, close, reopen, saved-range verification,
second close and normal exit. The callable MCP implementation passes the same
workflow in trials AE and AF, including all three feature replacements. AF uses
a new owned process and restored frozen inputs. Both exit normally, with no
corresponding Windows crash event. The 233-test unit suite passes. The tool leaves
changes unsaved; the test explicitly saves only its private copies.

Important limits:

- Individual mate conversions passed; the combined conversion/close flow failed.
  Do not generalize this into a ban on all `ModifyDefinition` or all `CloseDoc`.
- The exception dump proves the native destruction fault, but does not identify
  the earliest corrupting write. Private vendor symbols and another-version
  comparison were not available. Vendor defect versus an unsupported conversion
  contract is not conclusively distinguished.
- Several older crash signatures have not been independently reproduced. A
  multi-hour gap after `ExitApp` does not establish that call as the cause.
- Backup overlap, typed-wrapper changes and explicit Python collection were
  tested in controls; these results are narrower than a universal exclusion.
- Model inputs were frozen private copies. Other sessions concurrently changed
  formal source files; source-hash drift was recorded, not represented as proof
  that the tests wrote those files. All loaded paths were checked before saves.

See [mate fault evidence](CONFIRMED_NATIVE_MATE_CLOSE_FAULT.md) and
[dependency fault evidence](CONFIRMED_DEPENDENCY_API_FAULT.md) for the trial
matrix, dump details, official API contract references and remaining limits.
CAD files, diagnostic logs and dumps stay local under ignored `test-results/`.

## Callable workaround

`recreate_distance_mate_as_limit` requires an already connected configured PID
and an already open assembly. It never starts CAD, saves or closes documents.
Arguments: absolute `filepath`, exact `mate_name`, `minimum_m`, `maximum_m`,
`distance_m` in meters, and `allow_identity_change=true`. It validates ordinary
mate type, endpoint selections and bounds before deleting, preserves endpoint
order/alignment/flip/name, creates a fresh limit mate with `AddMate5`, and
checks its range and rebuild status.

Feature identity and ordering can change; downstream references must be reviewed.
Failures after deletion report `partial_change=true`; callers must stop rather
than retrying blindly or saving the incomplete result. This optional tool does
not rewrite arbitrary `execute_python` scripts or migrate another session's
caller. Restart that session's MCP connection to load the updated tool.
