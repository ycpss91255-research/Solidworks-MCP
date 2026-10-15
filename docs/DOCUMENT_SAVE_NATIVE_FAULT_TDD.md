# Built-in save fallback native-fault containment —2026-10-15

This is a confirmed MCP failure-handling defect, separate from the first native
rear-mate lifetime failure. The native replay uses direct Save3 calls, not these
SaveAs fallbacks, so this finding does not attribute its first corruption to
the built-in save_document handler.

## RED on current production source

save_document(filepath) catches errors from doc.SaveAs, Extension.SaveAs and
Extension.SaveAs2. A native RPC_E_SERVERFAULT is currently treated like an
ordinary binding mismatch. The first two paths can invoke another CAD save API
after the fault. The final path can leave the exception handler before returning
ERROR, losing the original exception required by the identity-bound marker.

`tests/test_document_native_save.py` uses fake CAD objects and a temporary
FaultStore, with fake PID/start identity. It makes no real CAD connection:

| Test | Actual RED behavior |
| --- | --- |
| Native fault from doc.SaveAs | Extension.SaveAs is still called |
| Native fault from Extension.SaveAs | Extension.SaveAs2 is still called |
| Native fault from final SaveAs2 | Failure returns without identity-bound native marker |
| Ordinary TypeError binding mismatch | Final fallback succeeds; no native marker (passing control) |

The actual result is3 failures/1 pass, retained under
`test-results/remaining-fault-correlation/document-native-save-red.txt`.
Baseline documents.py SHA256 is
dca111b3f543e1521ea17fd2673799fb06850680cbaa54d7eb0ad755a74fc8d7.

## Candidate and actual-source GREEN

The candidate adds the shared native_hresult classifier to exactly those three
catch handlers. Recognized native failures are rethrown immediately into the
existing outer failure handler, which records the PID/start-bound evidence and
returns ERROR. Ordinary binding errors retain their existing fallback behavior.
No CAD query, save retry or cleanup call is added to the native-failure path.

An isolated test interpreter imports a candidate copy and replaces only that
process's DocumentOperations.save_document method. The production file remains
byte-identical before/after; active CV's immutable runtime is not changed.
Complete discovery passes315 tests in22.342s, including all four new tests.
See `document-native-save-candidate-suite.txt` and
`document-native-stop-candidate.json`; candidate SHA256 is
bc82e3d837a2ed79bf77aef713c83032eeee58a3c6f91a16e90bdf3aaff91f6a.

The first candidate harness attempt used a unittest top-level directory that
required tests to be an importable package. Removing that harness-only argument
matches existing discovery and permits the complete suite. No CAD was involved.

CV subsequently ended in a non-native geometry assertion (front count4 expected,
3 observed). Before changing production source, its failed report, null HRESULT,
absent native marker, source/runtime hashes and native watcher exit were verified
in cv-failed-functional-audit.json. It was not relabeled as a successful CAD run.

The seven-line bounded guard is now applied to actual documents.py. Actual
source discovery passes315 tests in19.043s, retained in
document-native-save-production-suite.txt. Its AST exactly matches the tested
candidate; byte hashes differ because of newline serialization, not code logic.
Actual production SHA256 at verification is
5f51f6537cc0dbe00a9f5f72156660556ec83451615cc61ec4a0a7868e24a083.
See document-native-stop-applied.json. Branch publication is verified separately;
already-running other chats' MCP processes are not restarted by this change.

This containment change does not repair SolidWorks native memory, interrupt an
in-flight call or prove Save3's first lifetime-invalidating operation. It does
not change SaveAs options, in-place Save3 return interpretation or native backup
settings. Those are outside this specific rethrow guard.
