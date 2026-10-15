# Fresh untraced native close fault — CN full-memory evidence

The original close fault is reproduced without ScriptTrace, on a fresh owned
CAD instance and a single uninterrupted MCP. It is not a deliberate ExitApp,
a Python binding error or merely a timeout. The immediate native failure is
now visible in full memory; the earliest operation that established the wrong
native object reference remains unproven.

## Controlled trial

- CN PID39868, creation2026-10-15T05:27:29.913000Z; private seven-file fixture.
- Same immutable source hashes and CAD request ASTs as trace-on CM; original
  history0..6 and save/copy/CloseDoc scripts also match failed CG exactly.
- Equation51 reproduced before close. The actual failed request is
  `sw.CloseDoc(d.GetTitle())`; the private Save3 preceding it returned.
- Native `c0000005`, `dcu3d59.dll+0x11073`, full dump2,687,549,682 bytes.
  SHA256 `a5c111e531b17db833223d29fd164f52646719efb7f8e1dbc92f94c1ff976604`.
- Real /ma capture, debugger exit0; Memory64List6322 ranges validated. The
  exception stream's PID, creation time, context and RIP were verified before
  cleanup. Unlike the earlier small CI dump, relevant heap object bytes exist.
- MCP persisted RPC_E_SERVERFAULT against the same PID/creation identity.
  A new automation object, with no app/COM binding, was blocked by metadata
  alone while the faulted process was still live. Zero CAD APIs were used in
  this verification. After preserving/validating the dump, the held exact
  PID/start/image handle was used to retire this owned private process.

## Immediate native failure

Offline CDB analysis with the existing matching Microsoft MFC PDB shows:

1. The stack is in native model/mate/feature destruction servicing
   `auAm_c::iApiCloseDoc`, through `CObject::IsKindOf+0x1a`.
2. MFC `IsKindOf` at RVA0x23dc8e loads the object's virtual table, at0x23dc91
   loads its first entry, then dispatches through CFG. The saved return
   address is exactly0x23dc9a, immediately after that dispatch.
3. The dispatched object's preserved address is0xee4f8cf0. Its actual table
   is `dcu3d59!DCM3_node::vftable` at0x7ffa01be67d0, whose first entry is
   `DCM3_node::do_move_to_list` at0x7ffa01480ff0. Thus an MFC runtime-type
   query is dispatching into a solver node's list-moving function. This
   establishes an incompatible native object/virtual-dispatch path here.
4. The callee saves its third argument R8 in RBP; at the failing instruction,
   RBP is0x00000000ffffffff. `mov rax,[rbp+8]` attempts to read0x100000007,
   exactly matching the exception parameters.

This is stronger than the earlier missing-object small dump. It does not prove
which earlier write/reference update caused the incompatible object, whether
the allocation had been freed/reused, or the responsible vendor source line.
Nearest-export names for other vendor frames are not treated as exact source
functions. Offline `!heap -x` could not classify the allocation with the cached
NTDLL type information; that command's failure is retained, not counted as a
successful heap/use-after-free diagnosis.

CM passed the same original scripts with tracing on; CN failed with tracing
off. Neither result by itself estimates failure frequency or proves trace
causation. Error51 alone is not sufficient for inevitable failure. The full
staged binding workaround still needs fresh uninterrupted full acceptance
on the integrated runtime (CO) and an appropriate saved/cold verification.

## Local evidence and replay

Under ignored `test-results/remaining-fault-correlation/`:

- `report-cn.json`, `debug-cn-config-repair/{ready,result}.json`.
- `debug-cn-config-repair/exception.dmp`, `exception-record.json`,
  `exception-object-memory.json`, `offline-full-console.txt`,
  `offline-dispatch-console.txt`.
- `current-close-40588/cn-native-quarantine-verification.json`,
  `cn-faulted-cleanup.json`.
- `current-owned-native-event-audit.json` uses PID and manifest-millisecond
  creation intervals, preserves native100ns FILETIME, and checks failed CG as
  a positive control. CG and CN match native events; CJ/CK/CL/CM do not in
  that audited interval. This corrects an exact-timestamp comparison risk
  caused by pywin32's millisecond creation-time serialization.

The full dump stays local. No other chat's CAD was operated in this trial.
