# Diagnostic storage policy — 2026-10-15

The user requested immediate disk cleanup and explicitly rejected D:. Large
completed crash-analysis artifacts have been relocated to the authorized
SanDisk_USB removable volume, E:, under
`E:/CodexData/solidworks-mcp-crash-analysis/2026-10-15`.

The initial relocation included only this chat's completed checkpoint and CN crash-dump directories.
Other chats' models, their recovery backups, MCP installations and system files
are outside this relocation. Original C: directory paths are retained as NTFS
junctions. Every regular file is SHA256-compared at source and destination before
the checked C: duplicate directory is removed. The authoritative per-file receipts
are `test-results/remaining-fault-correlation/disk-relocation-status.json`, copied
to `relocation-manifest.json` on SanDisk at completion. Check its phase and current
filesystem state; this policy alone does not prove completion.

Future full dumps/checkpoints must use the SanDisk directory helper. It checks
volume label/serial and retains at least15GiB free on C:. Capture preflight checks
free space on the actual destination. Do not silently fall back to C: or D: when
the USB is missing or full. Scripts/logs and small manifests remain in the repo;
large evidence remains accessible through its previous logical path while the
SanDisk is connected. Offline readers validate the relocation receipt and allowed
physical root before accepting the resolved junction path.

Final verification at2026-10-15 16:10:56 Taipei confirms17 relocated directories,
153 files SHA256-compared during transfer, and22,827,000,527 bytes of verified
C: duplicates removed. All original directory paths resolve to SanDisk and all
file sets/sizes match the receipts. C: free space was49,360,695,296 bytes at that
check; unrelated system activity also changed free space, so only the verified
duplicate bytes are attributed to this relocation. D: was not used.

An actual small-file write through the new capture-directory helper was verified
on SanDisk. CN's native UAF verifier and CV's later-reference/full-dump verifier
both passed after relocation, using the preserved evidence. No CAD API was called
for this cleanup. The final machine-readable result is
`test-results/remaining-fault-correlation/disk-relocation-verification.json`.
This completed storage cleanup does not certify an unfinished native fix.

## Later registered evidence audit — 17:51:55 Taipei

The [2026-10-15 current-storage audit](../test-results/remaining-fault-correlation/storage-current-audit-20261015-095155Z.json)
checks all30 registered directories, including the three CY directories and
`debug-sensor-valid-v1`. Every workspace junction resolves to its exact
registered target under the authorized E: root. E: reports label `SanDisk_USB`,
serial `6C760E76`, and exFAT; C: has45.68GiB free and E:12.76GiB at that sample.
Those free-space readings are time-specific, not reserved capacity.

All153 historically relocated file sizes and logical/physical file identities
match, with no topology or size discrepancy. This later audit reads metadata
and compact receipts; it retains the original full-file SHA256 transfer proofs
without rehashing multi-GB dumps. The registration file stayed unchanged during
the audit. CY outputs have terminal records; the sensor-valid watcher has a
ready record but no terminal record and is treated as potentially in progress,
without making an OS liveness claim.

The inspected current watcher/checkpoint routing creates an E-backed junction
before dump output and checks the exact volume identity. Missing SanDisk raises
an error; no D: path or C: dump fallback was found in that scoped routing.
The audit did not scan unrelated user data, move/delete evidence, or call CAD.
The17-directory transfer result above and the earlier25-directory audit remain
valid historical snapshots;30 is the registration count at this later check.
