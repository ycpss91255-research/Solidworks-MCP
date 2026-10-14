# Reproduced configuration-error / native fatal-exit path

Investigation: 2026-10-14, SOLIDWORKS 2023 SP5 (31.5.0.52). Private copies,
explicitly owned PIDs, backup monitor disabled, memory-warning action cancel.

A previously untested three-file package survived under the rack task's
`tmp/brace-config-repair-20261013-165339`. It was saved immediately before that
task rebuilt its invalid brace configuration. These files postdate the Oct13
11:07 Save3 fault; they are not an exact reconstruction of that earlier session.
Original source bytes remain unchanged; all loaded documents and native
recorded/resolved references were checked to remain in the private fixture.

Input SHA256:

| File | SHA256 |
| --- | --- |
| 支架.SLDASM | 0cf278172a089c142ecfdeba71f44a7307e76f2cc13375b07bc0afa1da4ec6a6 |
| 支柱.SLDPRT | c088387fedea815c6655d6554799b03d5ac7366cff0b95f86c66c2f42a0d4b28 |
| 支撐條.SLDPRT | 5c04e80a942fda55a843863e58dcbf3a2a909742596b1e2a189ba5dbd47837da |

Every controlled trial restores these inputs before private reference rebinding.

| Trial | Operations before CloseAllDocuments | Result |
| --- | --- | --- |
| AG PID24048 | Save3 returns false/error1/warning1; activate horizontal brace, read its equation manager, rebuild; ShowConfiguration2(diagonal) returns internal application error61704 | Subsequent close fails RPC_S_CALL_FAILED, event1000 ucrtbase+c0000409+0xa527e; process exits before submitted ExitApp line |
| AH PID24084 | Same save return; activate/rebuild horizontal; diagonal switch error61704; no explicit equation-manager read | Same native abort at close; debugger stopped at fast-fail subcode7 |
| AI PID33844 | Same failed Save3, no configuration switch/rebuild | Close and empty ExitApp succeed, process absent |
| AJ PID41520 | Same failed Save3; activate/rebuild horizontal; no diagonal switch | Close and empty ExitApp succeed, process absent |
| AK PID31304 | Same failed Save3; activate brace; diagonal switch error61704; no preceding horizontal rebuild | Close and empty ExitApp succeed, process absent |
| AL PID41656 | Repeat AH with restored inputs and a fresh owned process | Same native abort during close; matching stopped-thread stack |

This isolates a failing combined model-state flow. Error61704 alone, Save3's
failed return alone, and the horizontal rebuild alone are not sufficient in
these controls. Do not generalize this result to every configuration error or
all close operations. No original native mate-kind conversion was performed.

AH and AL stopped-thread dumps independently show:

```
ucrtbase!abort+0x4e                  rip ...8527e; rcx=7; int29h
VCRUNTIME140!purecall+0x1a
sldmodu!moCompCompositeCurve_c::getCurveFeature+0x12d
sldmodu!moCompSketchEntHandle_c::getProfileFeature+0x33d
... moRelation ...
sldmodu!moEqnFolder_c::buildGlobalVarNodes+0x2fa
... moAssembly_c::update ...
slduiu!uiBaseFrame_c::OnMDIActivate+0xc10
... uiModelDoc_c::OnCloseDocument+0x15d8 ...
sldappu!auAm_c::iApiQuitDoc+0x176
sldappu!auAm_c::iApiCloseDoc+0x56
```

Public/native export names without private symbols have attribution limits.
The AL100-frame expansion connects model activation/update to native document
close, matching the pending CloseAllDocuments call rather than a submitted
ExitApp. Event1000 records this AL failure at16:53:02 Asia/Taipei, PID41656.
Nevertheless, the actual stopped instruction, purecall/abort chain, equation
and model-update frames prove a native CAD fatal-exit path, rather than a
Python exception simply being mistaken for process shutdown. Microsoft
documents that [_purecall terminates a program by default](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/get-purecall-handler-set-purecall-handler?view=msvc-170).
The [fail-fast code c0000409](https://learn.microsoft.com/en-us/shows/inside/c0000409)
also does not by itself prove a security violation or stack-buffer overwrite;
its subcode matters. Here CDB reports FAST_FAIL_FATAL_APP_EXIT, subcode7.

AH/AL's automatic handler initially had only a first-chance command. This
fast-fail arrived at second chance and stopped CDB; the 120-second MCP deadline
therefore expired while CAD was paused. Separate MiniDumpWithThreadInfo captures
preserved the real stopped thread/register/stack, but contain no exception
stream; do not claim `.ecxr` was verified on these dumps. CDB detached, then CAD
exited natively; no TerminateProcess was used. The watcher now includes `-c2`
for fast-fail and heap failure, following the [documented debugger command](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/sx--sxd--sxe--sxi--sxn--sxr--sx---set-exceptions-).
Live validation of that corrected exception-stream handler remains pending.

Follow-up AM PID22752 verifies the corrected second-chance handler. Recreate
inactive diagonal configuration and restore its parameter inputs while keeping
the original equations: switch still raises61704. Close fails RPC_S_CALL_FAILED;
corrected CDB handler captures exception.dmp (1,970,805bytes), detaches exit0,
and CAD exits natively. Offline `.exr -1` / `.ecxr` both succeed: c0000409,
parameter0=7, ucrtbase abort, VCRUNTIME140 purecall, native equation/model-update
and OnCloseDocument/iApiCloseDoc frames. The caller's indirect virtual call at
4b7313b7 is `call qword ptr [rdx+120h]`; exact object lifetime remains unresolved.
This is a real exception stream, distinct from AH/AL's paused-thread dumps.

AN PID47680 resumed repair rebuilds29 equations into18 configuration-aware
equations, removes the old instance alias/helper chain, and recreates the
inactive diagonal configuration. Expected length1332.097557mm and hole offset
656.0487785mm verify; original horizontal-rebuild/diagonal-switch, all three
Save3 calls, close and empty ExitApp pass. Source snapshots unchanged. The
first attempt had a verifier mismatch: installed Delete returned deleted index28
despite the current API page documenting zero. A subsequent Add3 attempt with
only one configuration failed. Corrected count verification and creating both
configurations before Add3 allowed continuation on the same owned PID. This
resumed sequence is not a pristine fresh-input proof of a completed repair.

AO PID48992 fresh inputs contradict a blanket repair claim: switch succeeds,
but ForceRebuild3 returns false and native feature errors51 are observed while
equations/dimensions appear correct. Parent in-context binding restoration also
returns false. Therefore AN's passing partial-state control cannot establish
full acceptance. The production model was not replaced. A later opt-in live
regression run was cancelled by the exact PID's memory warning (No/button7,
closed=true, document_returned=false); no geometry verification followed that
cancellation. Owned AO closed normally; other PIDs40588/42248 remain untouched.
The pending red/green, BRep, roundtrip and cold-instance gates are retained in
[CONFIGURATION_TDD_PLAN.md](CONFIGURATION_TDD_PLAN.md).

AK initially stopped because the memory-warning UIAutomation handler returned
error -2147220991. It did not report a successful open. Fresh MCP attachment to
the SAME PID, with a fresh debugger capture and the same explicit cancellation
policy, successfully verified open with no handler errors. No extra CAD instance
was launched. AK's successful result is this resumed control, not a pristine
single-pass startup. Its detach breakpoint dump is debugger-generated, not a
CAD fault.

System commit was approximately87–88%, no memory warnings were acknowledged,
and no backup monitor was active in these trials. This does not reproduce
exhaustion or test every add-in; it establishes this combined flow without the
independent MCP backup worker. Other live PIDs40588/42248 were never operated.

The old Oct13 PID28724 has the same ucrtbase failure signature but a nearly
three-hour gap after its last located MCP call. Signature equality alone cannot
attribute that historical failure to this flow. Likewise the SLDMODU Save3
access violation still requires an exact contemporaneous state/trace.

Appropriate handling: do not treat a failed configuration switch as a completed
edit, then blindly save/rebuild/close as if the native state were valid. Repair
or recreate the invalid configuration on a backed-up copy, validate equations,
and verify a fresh-session close/reopen. This is a model-specific repair, not a
global ban on configuration APIs. The rack task's recorded repair rebuilt the
diagonal configuration from its working horizontal configuration and restored
equation scopes; that production task was not changed by this investigation.
Independent validation of an equivalent private repair remains pending.

Local evidence: report-ag-diagnostic, ag-cleanup, report-ah/ai/aj/ak2/al,
debug-ah/ai/aj/ak2/al directories, owned-ah/al paused dumps and stack analyses,
config-fault-events.xml. CAD data and dumps are ignored and are not published.
