# IFeature reference keeper

Hold `IFeature` COM wrappers until no document is open. Prevents a use-after-free inside SolidWorks that
crashes `CloseDoc`.

## Problem

SolidWorks 2023 SP5.0 keeps an **unowned pointer** to the API wrapper object (`slduiu!auFeature_c`, a 0x130-byte
block) inside the internal feature object. When the client releases its last `IFeature` reference the wrapper is
destroyed, but the internal pointer is not cleared. The freed block is reused (by `moMateSupplement`,
`DCM3_node`, matrix data, ...). Closing the document later destroys the feature and uses the stale pointer:

- `CObject::IsKindOf` reads the reused block as an object (`mfc140u` RVA `0x23dc91`, `c0000005`)
- `DCM3_node::do_move_to_list` writes through it (`dcu3d59` RVA `0x11086`/`0x1108d`, `c0000005`)
- `moMateInPlace::removeOldConfigObjects` frees garbage (heap corruption fail-fast, `c0000374`)

Whether it crashes depends on what occupies the freed block at close time, so the same recipe sometimes
passes. pywin32 releases a wrapper as soon as the Python object dies, which is the end of every
`execute_python` script, so MCP users hit this regularly.

Evidence: a hardware write watch on the stale block recorded the client `Release` -> `~auFeature_c`, the
re-creation through `moFeature_c::getAuFeature`, and the reuse by the DCM solver; a heap listing at fixed
stages showed the block going busy -> free -> busy while the owner's `+0x170` kept pointing at it.

## Fix

`solidworks_mcp/com_keepalive.py` patches `DispatchBaseClass.__init__` (the only point every typed wrapper
passes through; makepy methods call a `Dispatch(...)` bound at import time, and scripts also construct
`m.IFeature(obj._oleobj_)` directly). `IFeature` wrappers are kept in a list. They are released only when
`ISldWorks.GetDocumentCount()` returns `0`, checked after each `execute_python` and after `close_document`.
That is the only added CAD call, it is read-only, and it is skipped while a native fault is quarantined or
when nothing is held.

| `SOLIDWORKS_HOLD_COM_REFS` | Behaviour |
|---|---|
| unset / `feature` | hold `IFeature` (default) |
| `all` | hold every COM wrapper, including dynamic `CDispatch` |
| `0` / `off` / `false` | disabled |

## Verification

Same script, same private model copy, a fresh chat-owned SolidWorks per run, arms interleaved ABBA.

| Route | Fix off | Fix on |
|---|---|---|
| MR12 recipe, Python via the real MCP server (`execute_python`) | 6 / 8 crashes | **0 / 8** |
| MR12 recipe, standalone typed C# harness (hold all return values) | 5 / 8 crashes | **0 / 8** |
| CN replay (rear mounting height, 通用貨架), original history through the real MCP server | 6 / 8 crashes | **0 / 8** |

Fisher exact one-sided p is about 0.0035 for the MR12 Python route and for the CN replay. Every fix-on run
logged `IFeature reference keeper installed`.

The CN replay rebuilds a private seven-file copy from immutable sources for every run, replays the original
history (`history_00`..`history_06`) and then saves, copies and closes. All six fix-off crashes were in the
`CloseDoc` step with `RPC_E_SERVERFAULT` and `c0000005` at `dcu3d59.dll+0x11073`, the same signature as the
original CN crash on 2026-10-15 (`moFeature_c` destructor reading the freed `+0x170` block of feature
`後側_安裝高度`). Both arms used the same MCP code; only `SOLIDWORKS_HOLD_COM_REFS` differed (`0` versus default).
Dump structure was not validated for the CN runs, only existence, size, exception code and address.

## Limits

- This is a client-side workaround. SolidWorks still does not clear its pointer.
- Verified for two reconstructed recipes: MR12 (distance mates + `ModifyDefinition` + drag + `CloseDoc`) and the
  CN replay (rear mounting height), 8 runs per arm each. Other historical crash families (sensor dispatch,
  equations, backup, support-bar configuration) are not covered.
- Default mode protects typed wrappers only. Without a makepy cache, wrappers are dynamic `CDispatch`; use
  `SOLIDWORKS_HOLD_COM_REFS=all` there. Features reached only through comtypes are not intercepted.
- Held wrappers keep SolidWorks objects alive while documents stay open. A warning is logged at 50,000.
- Not shown to be related to the drawing-view `0x800706E6` RPC error seen in another session; it could not be
  reproduced in 490 loop cycles, 28 in-process replays and 21 MCP replays on a private copy.
