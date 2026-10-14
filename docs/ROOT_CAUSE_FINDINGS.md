# SolidWorks crash findings — 2026-10-14

The investigation reproduced three native failure paths on SOLIDWORKS 2023 SP5
(31.5.0.52), using separate owned instances and private model copies. MCP/API
operations trigger them; the faults occur inside the native CAD process.
This is evidence for specific failing API/model-state paths, not a finding that
every historic crash has one cause or that all MCP operations are safe.

| Finding | Evidence | Prevention |
| --- | --- | --- |
| Imported-reference dependency query | `IModelDocExtension.GetDependencies` with `AppendImportedPaths=true` reproduces `sldapiu.dll` access violation at offset `0x8a24c0`; false returns an invalid scalar in the control. Failure also reproduced at approximately 64% committed memory. | Typed pywin32 guard blocks this exact query before invocation. Raw native calls can bypass it. |
| Existing distance-mate conversion followed by document close | Combined `IsAdvancedMate=true` / `ModifyDefinition` edits reproduce native solver/MFC failures. Exception-time dump shows an invalid read through `rbp=0xffffffff` during mate/feature/assembly destruction servicing `CloseDoc`. | Create fresh limit mates from the existing endpoints, rather than converting the old feature kind in place. Explicit identity-change acknowledgment is required. |
| Invalid configuration after prior rebuild | Frozen pre-repair rack files reproduce error61704 and, after horizontal rebuild plus failed diagonal switch, native purecall/abort during close. AM has an actual exception-stream dump showing c0000409 subcode7 and equation/model-update/close frames. Individual-operation controls close normally. | Preserve valid working equations while recreating the inactive configuration, validate/save a private checkpoint, then restore parent binding and resolve pattern members. AX passes the full frozen-input geometry, dynamic input, actual pattern count/placement, save/close/reopen workflow. |
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

See [mate fault evidence](CONFIRMED_NATIVE_MATE_CLOSE_FAULT.md),
[dependency fault evidence](CONFIRMED_DEPENDENCY_API_FAULT.md), and
[configuration fatal-exit evidence](CONFIRMED_CONFIGURATION_FATAL_EXIT.md) for the trial
matrix, dump details, official API contract references and remaining limits.
CAD files, diagnostic logs and dumps stay local under ignored `test-results/`.

## Callable workaround

2026-10-14 18:39 produced a new, separately attributed rack-session crash:
Windows event1000 records PID40588 (0x9e8c) with unknown-module c0000005,
followed by KERNELBASE c000041d. That session's `generic-base-frame-report.json`
records RPC_E_SERVERFAULT from CloseDoc after Save3 and prototype copying,
before its subsequent restoration/editing statements. This is an exact current
call correlation, not proof of the earliest corrupting operation. This diagnostic
chat did not operate that PID. AX/AY's new owned repair processes have different
identities and no matching crash event. The new CloseDoc case remains an open
root-cause item; do not conflate it with the repaired configuration flow merely
because both involve document closure.

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

The new40588 CloseDoc case has four completed private controls, including a
pre-layer reconstruction with recorded inputs and exactly matching pre-refresh
equations/pattern/component observations. None reproduces its native crash;
post-refresh beam counts diverge (original6, replay7). Full input provenance,
fidelity limits and retained follow-up are in
[CURRENT_CLOSE_40588_CASE.md](CURRENT_CLOSE_40588_CASE.md). This case remains
unattributed rather than being declared another instance of an existing fix.

Paired stored/reconstructed pattern inspection finds matching seeds, zero skipped
instances and zero feature errors, but different generated-child inventories.
Fresh BF and retained-helper BG independently change enumeration6→7 through
balanced selection rollback/restoration without changing a feature property;
the reconstructed control remains7. Neither reproduces the native close crash.
The pattern cache/state difference is now measured, not inferred from an equation
count, and must still not be declared the heap-corruption cause.

The bounded40588 investigation subsequently confirms rear-standard selection
access/restoration alone regenerates6→7 components. An uninstrumented,
two-separate-MCP-process close control also passes. A native failing replay,
original exception dump and complete crash-time input/process state remain
unavailable across three consecutive continuations. The detailed completion
and blocker audit is retained in CURRENT_CLOSE_40588_CASE.md. The broader goal
is not achieved; the verified three paths and their fixes must not be generalized
to the still-unattributed events.

The separately received46576 batch-close case is retained in
[CURRENT_CLOSE_46576_CASE.md](CURRENT_CLOSE_46576_CASE.md). Its Windows events
establish access violation followed by heap corruption after a subsequent caller
continued Save3. Fresh private BJ/BK saved-state and eight-case dynamic controls,
plus BL's pre-mirror cold baseline, all close normally; they do not reproduce
the original native fault. Mirror, mate-reference replacement/deletion and
multi-document renaming history are retained for still-unexecuted BM/BN controls.

One confirmed diagnostic defect was corrected: execute_python failures previously
returned a traceback but persisted only success=False in the main log, losing
partial stdout/stderr. The updated handler records PID, HRESULT, script location,
traceback and partial output without another CAD call. Five failure-evidence
tests and full259-test discovery pass; a separate mocked process verifies actual
FileHandler persistence. This improves evidence collection, not native crash
prevention or attribution, and does not persistently quarantine a faulted PID.
