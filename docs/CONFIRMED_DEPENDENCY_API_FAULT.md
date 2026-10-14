# Confirmed dependency-query native fault

Installed environment: SOLIDWORKS2023SP5 (31.5.0.52), Python3.14.8, typed
pywin32 IModelDocExtension wrapper. This is one identified failure category,
not proof of a common root cause of all historic crashes.

Historical owned PID35832:
- 2026-10-13 02:16:16.246 Asia/Taipei: execute_python invokes
  `extension.GetDependencies(True, True, False, True, True)`.
- 02:16:17.601 Windows event1000: sldapiu.dll, c0000005, offset0x8a24c0.
- 02:16:23.830: RPC_E_SERVERFAULT (-2147417851) returned to MCP.

Controlled owned PID36872, private JNPN10 imported native part:
- `GetDependencies2(True,True,False)` returns a valid string inventory.
- Extension query with traversal/search true and AppendImportedPaths false
  returns an unexpected float1.401298464324817e-44, not the documented array.
- Changing only AppendImportedPaths to true, with ListBrokenRefs false,
  returns RPC_E_SERVERFAULT. Windows event1000 at 2026-10-14 11:24:04.126:
  same sldapiu.dll, c0000005, same offset0x8a24c0. Commit usage ~64.2%; no
  low-memory warning or backup worker in this test. Thus commit exhaustion and
  ListBrokenRefs true are not necessary to reproduce this particular fault.
- Runtime and cached method DISPID both306; no evidence of a wrong cached ID.
  This does not isolate native implementation vs lower-level COM marshaling.
- CAD calls stopped after the native fault. The faulted private process was
  terminated only after executable, PID creation identity and unchanged input
  hashes were verified. Other session PID38068 was not operated.

MCP mitigation: the typed DispatchBaseClass invocation for the exact model
extension IID99F4D4AF-F268-4EE1-8C55-041F7BECF879 and method306 is rejected
before InvokeTypes. The whole method is blocked because its false-import-path
result was invalid too. No automatic alternate dependency API is substituted.
Other interfaces and method IDs forward unchanged. This covers the typed
pywin32 route used by the reproduced script, including nested scripts. Direct
raw Invoke or native/comtypes calls are not intercepted by this guard and must
not be used to bypass the known fault.

Fresh owned PID40524 real-MCP validation: opening a private copy succeeds;
the formerly faulting query raises the intended guard error before native
invocation; GetDependencies2 returns valid inventory; normal close/exit succeeds
with no new fault event for that PID. Unit suite227 passes. Restart existing MCP
connections to load the guard; no CAD restart required for healthy instances.

The production recovery path already uses PackAndGo metadata and native closed
reference inventories. GetDependencies2/GetDocumentDependencies2 are narrower
and are not substitutes for a complete suppressed/STEP dependency package.

Further investigation reproduced a separate native mate-edit/CloseDoc failure,
including the historical dcu3d59.dll c0000005 offset0x11073 signature. See
CONFIRMED_NATIVE_MATE_CLOSE_FAULT.md. Individual edit controls pass; the full
edit sequence fails. The precise native operation/lifetime defect and an
appropriate prevention still require isolation. Do not mark the overall
root-cause investigation complete from the dependency-query guard alone.

Official API parameter/result contract:
https://help.solidworks.com/2019/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetDependencies.html

Local evidence: test-results/session-35832-8768.log; crash-probe-20261014-i/
resume-report.json and runtime-dispid.txt; crash-probe-20261014-j/report.json;
Windows Application event1000 for PIDs35832 and36872.
