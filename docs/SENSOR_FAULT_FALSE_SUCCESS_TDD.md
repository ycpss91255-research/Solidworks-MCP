# Native sensor exception reported as MCP success — 2026-10-15

This is a newly correlated failure mode, not proof that all earlier DCM/MFC
close faults share one cause. The crash investigation remains incomplete.

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
caught-fault/restart regression. CO is testing healthy native CAD on this runtime;
no new native caught-sensor reproduction is claimed.

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
MCP requests. Full native sensor reproduction and the exact failing sub-call
remain unverified.

Python API reference: [Execution event monitoring](https://docs.python.org/3.14/library/sys.monitoring.html).

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
