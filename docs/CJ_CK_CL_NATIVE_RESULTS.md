# Current native continuation and cold controls —2026-10-15

The staged binding workaround passes the completed CJ continuation and separate
CK saved/cold acceptance. An untraced CL continuation also closes successfully
without that workaround, despite reproducing equation51. The latter result
limits causal attribution: equation51 alone does not establish an inevitable
native close fault. Fresh same-runtime trace-on control CM now also passes;
trace-off control CN reproduces the original native close fault.
The crash goal is not complete.

| Trial | Actual result | Scope/limits |
| --- | --- | --- |
| CJ PID37192 | Initial six-case prefix passed; a local IModelDoc2/assembly-interface diagnostic error interrupted its MCP process. Same CAD state resumed, next six cases, full first-floor construction, five physical cases, Save3/CloseDoc/batch close/ExitApp all pass. | Two MCP processes and a resource wait; not an uninterrupted fresh full replay. |
| CK PID26304 | Seven saved models frozen/copied from exited CJ; closed references rebound privately. As-loaded geometry/feature/mate baseline passes before explicit rebuild/property edits. Five first-floor cases plus2900/3000mm length cases, save/close/exit pass. | An independent cold verification of CJ's saved output. |
| CL PID44012 | Initial local FileNotFoundError before history00's CAD mutations: test backup directory was missing. No native dump/HRESULT. Folder fixed, same healthy CAD resumed from history00. Exact original equation51 reproduced, then Save3/CloseDoc/batch close/ExitApp pass. | ScriptTrace off, but MCP restarted after the setup failure. This is a native close control, not functional acceptance of the unrepaired model. |
| CM PID28424 | Fresh CAD, one uninterrupted MCP, tracing on; original0..6 reproduces equation51, then Save3/root CloseDoc/batch close/ExitApp all pass. Actual /ma readiness, no native exception dump, debugger exit0; immutable sources preserved. | Native close control, not valid geometry acceptance. |
| CN PID39868 | Same runtime/input/request ASTs, tracing off. Equation51 reproduced; root CloseDoc fails with RPC_E_SERVERFAULT/native dcu3d59+0x11073. Full2.69GB dump validates actual object/dispatch memory, marker acceptance and exact-identity cleanup. | Proves tracing is not necessary for this fault; one pass/fail pair does not estimate failure frequency or identify the first corrupting operation. |

All three completed continuations preserve immutable source hashes. CJ/CK have
no matching Application Error1000 with their PID AND millisecond creation
identity in the queried interval. Actual debugger results have no exception
dump; detach breakpoint files are not counted as native faults. All request
paths/saves are private. Other sessions' CAD processes were not operated.

`cj-ck-physical-comparison.json` independently compares the resumed six cases
with the original historical six-case geometry (SHA256
253bc6ff991817db092370a98ad65f578f504d027b1fe3468fecece9c2ab10d7), validates all
five first-floor height/count/spacing intentions, compares warm/cold values,
and checks both cold length cases against historical geometry. Positions match
within1e-5mm, including counts/pattern/configuration/constraint flags and empty
feature errors. Names and full orientation matrices are not compared.

## Resource gate calibration

The earlier CJ continuation worker was alive and waiting, not hung or terminal.
Its default90% gate had no absolute commit-reserve option. The preserved CB
blocking trace had2.333GiB remaining commit before its192.743s gap and2.995GiB
afterward; that source line contains activation/Set2/rebuild, so the trace alone
does not isolate a specific sub-call or exact warning threshold.

For the already-loaded CJ/CL continuation, the explicit lab policy now requires
at least4GiB commit reserve AND4GiB available physical memory, at most95% committed,
for three consecutive five-second samples. New-instance controls require6GiB
of both reserves, budgeting roughly2GiB for the observed owned CAD footprint
while preserving the4GiB margin. The general default remains90%; Windows memory
settings and other sessions are unchanged. These are measured engineering gates,
not proof that future memory pressure cannot occur.

The old waiting worker was intentionally cancelled for this documented policy
change. Its cancelled terminal state, exited creation identity and absence of a
continuation report were checked before the replacement worker started the SAME
CAD instance/model state. The shell wrapper returned1; native worker exit2 was
not directly observed and is not claimed. This was not a replay after an
observation timeout. CJ/CK/CL actual capture readiness confirms /ma.

## Next causal comparison

CM/CN use fresh own CAD processes, a single MCP process throughout each trial,
the same seven immutable inputs and identical15 CAD request ASTs. The whole MCP
Python package is hashed before launch; source changes invalidate the pair.
ScriptTrace is enabled only in CM. Both have full exception capture and identical
extended observation timeouts, avoiding artificial truncation of a still-busy
native build. No model API is replaced or omitted to make the control pass.

Independent embedded-script comparison confirms all seven original0..6 scripts
and the original save/copy/CloseDoc script are byte-identical between failed CG
and passing CM; their seven immutable source-file hashes also match exactly.
The current MCP runtime is newer than CG, and heap/timing/resource conditions
are not identical. CG had4.141GiB commit reserve just before CloseDoc versus
CM's5.162GiB. This difference does not establish a memory threshold or prove
memory caused the old failure. Source: `cg-cm-embedded-cad-fidelity.json` and
`cg-cm-close-memory-comparison.json` in the ignored evidence directory.

CG versus CL cannot by itself isolate ScriptTrace: reconnection, the updated MCP
runtime, resource conditions and native object/COM reference lifetimes also
differ. A new uninterrupted full staged-build replay is still required after
the causal controls. Native-fault quarantine has unit/real-stdio/fake-CAD and
healthy native-path evidence; actual native-marker acceptance now passes on CN.
CO is running the fresh uninterrupted full staged-build replay with the newly
integrated caught-exception observer. See
[CN_FULL_DUMP_NATIVE_DISPATCH.md](CN_FULL_DUMP_NATIVE_DISPATCH.md).

Private evidence under ignored `test-results/remaining-fault-correlation/`:
`report-cj-resume.json`, `report-ck.json`, `report-cl.json`, `report-cl-resume.json`,
full-capture readiness/results, `current-close-40588/cj-ck-physical-comparison.json`,
`cj-ck-native-event-audit.json`, immutable manifests, resource gate event histories,
`cj-resource-policy-calibration.json` and `cm-cn-trace-pair-preparation.json`.
