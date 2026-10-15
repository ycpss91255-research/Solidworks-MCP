# Native sensor exception reported as MCP success — 2026-10-15

This is a newly correlated failure mode, not proof that all earlier DCM/MFC
close faults share one cause. The crash investigation remains incomplete.
The later controlled empty-target reproduction below now isolates a real AV to
the generated `ISensor` wrapper's SensorType property dispatch and verifies an
MCP error plus persisted quarantine. Actual sensor-IID query success, the
valid-target control and historical target state remain unverified.

## Observed evidence

- Windows Application Error1000 record24437, 2026-10-15 12:10:25.2856559 +08:00:
  SLDWORKS.exe31.5.0.52, PID48852, process creation FILETIME
  `0x1dd5c4f713cec36`, `sldapiu.dll+0x7223a2`, exception `c0000005`.
- MCP server35784 recorded the sensor-query request at12:10:24.394 and
  `Result: success=True` at12:10:40.501. The original tool response, retained
  from the actual conversation output, contains
  `sensor error (-2147417851, '伺服器丟出一個例外。', None, None)`.
- That HRESULT is `RPC_E_SERVERFAULT`. The script catches `Exception` around
  the sensor expression, prints the error and returns. Thus the outer Python
  executor sees normal return and incorrectly reports `[SUCCESS]`.
- The native event falls inside the actual call interval. This is not a
  speculative association based solely on a matching DLL name.
- OS-only GetProcessTimes confirms the exact100ns process creation FILETIME.
  By13:24 the same process handle is signalled/exited. This chat did not
  attach to its COM server, operate its windows, write its fault marker or
  close it. A preexisting live process is not assumed healthy after a native
  exception; its eventual exit cause has not been established here.
- WER1001 records24438/24449 share report GUID
  `2995bf6e-89e5-4dfc-b48b-c7e0fafcc95d`. Their listed Queue/Archive paths did
  not provide a retained dump during inspection. This is a scoped negative
  lookup, not a claim that no dump exists anywhere.

The sensor expression combines GetSpecificFeature2, interface wrapping,
SensorType, SensorAlertEnabled, SensorAlertState and GetSensorFeatureData.
There is no per-sub-call trace/dump here, so the exact failing member is not
yet proven. Do not ban an arbitrary sensor method or claim the documented
sensor API is inherently invalid from this evidence.

## TDD and containment scope

Three fake-CAD regressions were run with tracing disabled and temporary fault
storage, without connecting any real CAD:

1. A caught RPC_E_SERVERFAULT must not become a successful execute_python
   response — **RED** on the current candidate.
2. After that caught fault, the next Save3 must stop before any CAD call —
   **RED** on the current candidate; the call currently reaches fake Save3.
3. A caught ordinary TypeError remains a successful script and does not
   quarantine — **PASS**.

The previously passing298-test suite does not cover this caught-inside-script
case. The native-fault candidate catches escaping COM exceptions and stops
later requests; the pre-observer version did not observe an exception consumed
inside an arbitrary user script. The RED evidence is retained under the ignored
lab. After CM/CN completed on their unchanged runtime, the fix was integrated
as native_observation.py and its tests promoted to tests/test_native_observation.py.
Full discovery now passes311 tests in8.315s, including an additional real-stdio
caught-fault/restart regression. CO full construction and CP saved/cold acceptance
now pass on this runtime;
at that stage no new native caught-sensor reproduction was claimed.

An isolated candidate now observes native exceptions before a script can consume
them, records the existing PID/creation-bound marker, and fails the response
when the script otherwise returns normally. It passes12 fake-CAD tests,
including the two original RED regressions, tracing enabled/disabled, ordinary
TypeError, thread attribution, occupied monitoring slots and restoration of an
existing trace hook. Python3.12+ uses exception-only `sys.monitoring`; older
runtimes/occupied slots use a chained, exception-focused trace hook. The
prototype was first exercised by replacing the executor function only in its
test interpreter. Integration followed completion of CM/CN; their recorded
runtime fingerprint remains preserved in their input manifests. Other chats'
already-loaded MCP processes have not been restarted by this investigation.

This candidate detects/contains later request boundaries. Arbitrary raw Python
that catches a native exception may still execute further raw CAD calls within
that same request before it returns. It is not a sandbox or a universal
interceptor of raw COM. Controlled scripts must not catch and continue after
these native/RPC faults; the recorded marker blocks managed recovery and later
MCP requests. The later empty-target run below isolates a native failing getter;
it does not exercise a user script that catches and swallows that real fault.

Python API reference: [Execution event monitoring](https://docs.python.org/3.14/library/sys.monitoring.html).

## Private fixture setup failures before sensor reproduction

The new valid-target control uses owned PID46396/start
`2026-10-15T09:38:39.586000+00:00`. The first two setup requests failed before a native
sensor fixture/probe was accepted. Their failed receipts and separate traces
are retained; neither is converted to PASS because a later setup step worked.

The initial request at09:38:58–09:39:10Z selected
`IModelDoc2.FeatureByPositionReverse(0)` as the presumed last sketch.
The actual `IFeature.GetTypeName2` result was `MateGroup`, so the subsequent
sketch-type assertion failed. The MCP response is an ordinary `AssertionError`
with null HRESULT. The trace contains no SaveAs call. This is a positional
feature-selection assumption failing, not a sensor getter or native AV result.
See the [initial response](../test-results/remaining-fault-correlation/sensor-private-valid-v1/fixture-response.json)
and [initial trace](../test-results/remaining-fault-correlation/sensor-private-valid-v1/fixture-trace.jsonl).

The separately recorded resume request at09:49:27–09:49:39Z found the intended
sketch and dimension, then successfully saved the private baseline assembly.
Its trace records SaveAs returning and the exact saved path, followed by
`D1@SensorTarget@sensor-valid-v1.Assembly`. The source hash matches the resume
receipt; its executed SaveAs check requires a tuple, success=true and errors=0
before those later observations. The private SLDASM exists. This establishes
that save step, not complete setup or sensor acceptance.

The resume finally fails at `IFrame.GetHWndx64`, with
`DISP_E_EXCEPTION` (`-2147352567`, `0x80020009`) and a SOLIDWORKS message
stating that a write-only property cannot be read. The durable exception record
has `phase=operation` and `native_hresult=false`; it is not the original
`RPC_E_SERVERFAULT` signature. The [resume response](../test-results/remaining-fault-correlation/sensor-private-valid-v1/fixture_resume-response.json)
and [resume trace](../test-results/remaining-fault-correlation/sensor-private-valid-v1/fixture_resume-trace.jsonl)
remain failed. Their trace ends at that exception without a completed-fixture
record or later cleanup calls.

The official [GetHWndx64 contract](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFrame~GetHWndx64.html?format=P&value=)
limits this method to early binding and 64-bit SOLIDWORKS. The actual traceback,
confirmed by reading the generated wrapper file, shows its `GetHWndx64` method
calling `_oleobj_.InvokeTypes(16, LCID, 1, (20, 0), (),)` at line25074.
A generated Python wrapper does not by itself establish that the documented
native calling contract was met. This is evidence supporting an interface-route
incompatibility hypothesis for this setup failure, not proof of the original
sensor fault's cause or of all historical failures.

At review of those first two failures, the private UI-creation evidence and probe response did not yet
exist. The owned watcher's console/engine logs had no captured AV/breakpoint
marker, and no exception/breakpoint dump was present. These two failed setup
requests therefore provide no native sensor-AV reproduction evidence. The
`native_hresult=false` classification is not a universal health certificate;
the separately traced valid-target/empty-target sensor comparison remains open.

## Continuation3 and selection controls: limited setup progress

A third setup request, `saved_fixture_verify`, failed at09:56:55Z because the
script looked up `FeatureByName` on `IModelDoc2`. The generated wrapper has no
such attribute, so Python raised `AttributeError` before dispatching that
native feature lookup. The trace records null HRESULT and
`native_hresult=false`. The [failed receipt](../test-results/remaining-fault-correlation/sensor-private-valid-v1/saved_fixture_verify-response.json)
and [trace](../test-results/remaining-fault-correlation/sensor-private-valid-v1/saved_fixture_verify-trace.jsonl)
remain preserved, and continuation2 stopped without proceeding to the UI or
sensor probe. This is an incorrect interface receiver in the diagnostic script,
not a sensor exception reproduction.

Continuation3 corrects that lookup to `IAssemblyDoc.FeatureByName`, supported
by the [local type-library member audit](../test-results/remaining-fault-correlation/sensor-continuation3-typelib-verification-v1.json).
That static audit checks member availability; it is not native acceptance.
The actual [saved-fixture verification](../test-results/remaining-fault-correlation/sensor-private-valid-v1/saved_fixture_verify2-response.json)
then passes at10:02:42Z: the exact private assembly and
`D1@SensorTarget@sensor-valid-v1.Assembly` are found, the dimension is approximately
0.002m, and the owned frame HWND6753334 maps to PID46396. Its result records
`model_writes=0` and `sensor_created=false`. The frame observation uses the
owned OS-window check rather than repeating the failed GetHWndx64 dispatch.

The [open_ui2 receipt](../test-results/remaining-fault-correlation/sensor-private-valid-v1/open_ui2-response.json)
also passes: the native PropertyManager command returns true with the expected
dimension preselected. It explicitly leaves `property_manager_visually_verified`,
`target_visually_verified` and `sensor_created` false. The
[continuation3 controller](../test-results/remaining-fault-correlation/sensor-valid-continuation3-controller-v1.json)
then entered `waiting_for_native_ui`, with `passed=false` and `case_complete=false`.
Opening the command is not confirmation of a committed native sensor.

Two later selection-only receipts provide narrower observations:

- [mark0 selection](../test-results/remaining-fault-correlation/sensor-private-valid-v1/ui-target-select-response.json),
  completed at10:10:05Z, records SelectByID2 returning true for the exact dimension.
- [mark1 selection](../test-results/remaining-fault-correlation/sensor-private-valid-v1/ui-target-mark1-response.json),
  completed at10:18:31Z, independently reads the expected dimension before and
  after the operation: one selected item, selection type14, mark0 before and
  mark1 after. It records `mark1_is_hypothesis=true`; this is not proof that
  mark1 satisfies the sensor target field's contract.

Both receipts retain `target_visually_verified=false`, `sensor_committed=false`
and `model_saved=false`. Their PASS flags apply to selection and recorded
identity checks only. They do not prove target-field population, native sensor
creation, sensor getter safety, saved-state behavior, or the empty-target control.

The operator subsequently observed an Esc UI action in the conversation's
computer-use result; no separate saved UI artifact was produced for that action.
At approximately18:28 Taipei, another brief operator inspection of owned
HWND6753334 showed the Dimension PropertyManager with blank target/value fields
and Alert unchecked. The tool returned `screenshot-0` at853x481; control was
released immediately afterward. This is a conversation UI observation, not a
saved proof artifact. In that observation mark1 had not populated the target
field, and the operator reported no sensor commitment.

Acceptance or cancellation following Esc still requires verification of the
actual current feature/state. The prior selection receipts and the blank
PropertyManager cannot establish a committed sensor's existence or absence.
No successful probe receipt or committed native UI evidence has been recorded
at this checkpoint, and no sensor root-cause verdict or completion is claimed.

## Watcher expiry stopped the control; no sensor AV demonstrated

At18:28:50.817800 Taipei (10:28:50.817800Z), the continuation3 controller changed
to `stopped`, `passed=false`, `case_complete=false`. Its recorded error is
`AssertionError: Native watcher event or terminal artifact: breakpoint.dmp`.
The operator's controller terminal returned exit1; this is not a SOLIDWORKS
process exit code. The valid-target control is no longer waiting for UI input.

The original watcher was bounded to3000 seconds (default UI wait1800 plus1200).
Its expiry path calls `DebugBreakProcess` before requesting debugger detach.
The [watcher result](../test-results/remaining-fault-correlation/debug-sensor-valid-v1/result.json)
records `owned_debug_break_requested=true`, `detach_requested=true`, a detach
retry and debugger exit0. The [engine log](../test-results/remaining-fault-correlation/debug-sensor-valid-v1/engine.txt)
contains one exact `CAPTURED_OWNED_BREAKPOINT` marker, exception80000003,
`ntdll!DbgBreakPoint` / `ntdll!DbgUiRemoteBreakin`, a successfully written
1,987,802-byte mini dump, and `quit:`. There is no exact `CAPTURED_OWNED_AV`
marker or exception dump. These records support a diagnostic-requested break
during watcher expiry/detach; they do not demonstrate the original sensor AV.
The generic breakpoint artifact nevertheless caused the controller's guard to
stop. Watcher classification is being reviewed separately; no corrected live
watcher result is claimed here.

The operator subsequently reported owned PID46396 still live, no CAD request
after the earlier mark1 selection, and the newly prepared visibility helper
never executed. Those are operator observations, not new feature-state or probe
receipts. Native sensor acceptance and the exact failing sensor member remain
unverified; the historical successful selection receipts do not complete this
stopped control.

## Empty-target SensorType AV and actual error/quarantine result

The later [native UI observation record](../test-results/remaining-fault-correlation/sensor-private-valid-v1/empty-first-ui-evidence.json)
binds an explicitly **empty-target** Dimension sensor to owned PID46396/start
`2026-10-15T09:38:39.586000+00:00`. The existing private filename remains
`sensor-valid-v1.SLDASM`; that name does not make this a valid-target control.
The operator observed blank target/value fields and Alert unchecked, confirmed
the native PropertyManager at10:44:41.591Z, then observed `Sensors1` beneath
Sensors at10:44:52.208Z. This record cites the inspected tool screenshots; it
does not claim independent automated image verification. The probe performed
no save, close, launch or sensor creation.

The [27-record per-member trace](../test-results/remaining-fault-correlation/sensor-private-valid-v1/empty-first-probe-trace.jsonl)
records successful feature lookup, `GetTypeName2` returning `Sensor`,
and `GetSpecificFeature2`, followed by a returned generated-wrapper constructor
under the trace label `ISensor.QueryInterface`. Sequence26 begins
`ISensor.SensorType` at10:46:38.731291Z. Sequence27 records that same operation
throwing `RPC_E_SERVERFAULT` (`-2147417851`) at10:48:19.693831Z. There is no
successful SensorType return or later SensorAlertEnabled, SensorAlertState or
GetSensorFeatureData call.

That `ISensor.QueryInterface` label overstates what the probe measured: the
operation was `m.ISensor(raw._oleobj_)`, not an explicit IID query whose success
was separately checked. The [constructor audit](../test-results/remaining-fault-correlation/sensor-dispatch-constructor-audit-v1.json)
checks the installed pywin32 source, generated type library and actual trace
hashes. Local `DispatchBaseClass.__init__` attempts QueryInterface, but for raw
PyIDispatch input it catches `pythoncom.com_error` and retains the original
dispatch object. Its isolated Python control-flow tests, using a fake dispatch
type with no COM calls, show the constructor returning after both
`E_NOINTERFACE` and `RPC_E_SERVERFAULT`; an explicit query propagates those
errors. This proves the local fallback behavior, not that fallback actually
occurred in PID46396. Constructor return therefore does not prove a successful
query for sensor IID `{D29432D5-E401-424B-B009-F5775BBDBF65}`. A fresh controlled
comparison must verify that query explicitly before invoking a sensor property.

The [completed watcher result](../test-results/remaining-fault-correlation/debug-sensor-valid-v2/result.json)
records a3,492,402,159-byte exception dump, no breakpoint dump and debugger
exit0. Its engine contains an exact `CAPTURED_OWNED_AV` marker. The
[offline native analysis](../test-results/remaining-fault-correlation/sensor-empty-first-native-analysis-v1/result.json)
and [debugger console](../test-results/remaining-fault-correlation/sensor-empty-first-native-analysis-v1/console.txt)
confirm exception `c0000005` at `sldapiu.dll+0x7223a2`, version31.5.0.52,
module timestamp65249524. The recovered exception context has RCX=0 at
`movsxd r12,dword ptr [rcx+0AD0h]`, causing a read from0xad0. The nearest
export-symbol text `GetRuntimeClass+0xad22` is not an exact function identity.
Module build, offset and exception code match historical event24437. This
establishes the failing getter and null-base read for this controlled empty
target; it does not retrospectively establish the old sensor's target state,
its exact compound-expression sub-call, or its eventual process-exit cause.

The separate [dump validation](../test-results/remaining-fault-correlation/sensor-empty-first-native-analysis-v1/validation.json)
confirms PID46396, creation time matching the expected timestamp to the dump's
whole-second precision, valid exception context and all recorded stream/range
bounds. Its6196 Memory64 ranges end exactly at the3,492,402,159-byte file size;
one zero-byte range at0xfab9000 corresponds to the unreadable page logged by
CDB. This validates the recorded payload, not capture of every process page.
The recorded SHA256 is
`b097b628cc9b6a5bd30e3bbf03154dab68d47fe879cdb9673e19a0acea960a5e`.
The validation also confirms the original event's module version, timestamp,
fault offset and exception code. The matching signature and null RCX do not
prove successful interface negotiation or exclusive empty-target causality.

The [persisted probe response](../test-results/remaining-fault-correlation/sensor-private-valid-v1/empty-first-probe-response.json)
returned at10:48:19.757062Z with `[ERROR]`, HRESULT-2147417851 and
`native_fault_quarantined=true`. The [MCP log](../test-results/remaining-fault-correlation/sensor-private-valid-v1/mcp-51300.log)
records `Result: success=False`. The on-disk FaultStore marker
`C:/Users/yunchien.chen/.solidworks-mcp/native-faults/pid-46396.json` matches
the exact PID/start and HRESULT; reporter51300 recorded it at10:48:19.666671Z.
All recorded probe source hashes and52 production runtime hashes still match.
The controller remains `passed=false`, `request_success=false`, with its final
failure recorded at10:48:20.305988Z. The durable MCP error was saved before
the post-call native guard stopped the dispatcher.
The outer MCP `CallToolResult.isError` is still false; the verified failure is
the tool's `[ERROR]` body, server success flag and quarantine record, not that
transport flag.

This actual native run verifies error reporting and persisted quarantine,
with no later getter or CAD cleanup in the probe. It deliberately rethrows
the fault, so the caught-and-swallowed behavior still relies on the separate
regressions described above. Explicit interface negotiation, the valid-target
comparison, healthy save/close acceptance and the underlying reason this
dispatch reaches the null-base read remain open. No general sensor-method ban
or broad crash-investigation completion follows from this one reproduction.

## Reproducible evidence

In `test-results/remaining-fault-correlation/`:

- `48852-sensor-fault-audit.json` — request interval, HRESULT, exact OS identity.
- `48852-original-sensor-call-and-reply.json` — original request and tool output.
- `48852-mcp-1210-correlation-raw.json` — timestamped MCP log lines.
- `48852-wer1001.json`, `recent-native-sw-events-after-1117.json` — Windows events.
- `test_caught_native_fault_red.py`, `caught-native-fault-red.txt` — executable RED
  tests and actual output. These are local test artifacts, not a deployed fix.

CM/CN prelaunch review also caught a lab-generator substitution that changed
`current-close-40588` into `current-cmose-40588`/`current-cnose-40588`. Both runner
paths were corrected atomically before either session manifest existed, with
actual path evaluation, identical15 CAD request ASTs, source/runtime hash
checks and directory preflights. This was a test harness error, not CAD evidence.
The generator now validates the evaluated private path. Proof is retained in
`cm-cn-prelaunch-path-correction.json`.
