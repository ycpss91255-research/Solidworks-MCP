# Native crash investigation

Opt in on the diagnostic session only:

```toml
SOLIDWORKS_SCRIPT_TRACE_DIR = 'C:/absolute/chat-owned/diagnostics'
```

Restart that MCP connection. This does not launch or close CAD. Without this
setting execute_python follows its existing execution path without tracing.

Each call writes the submitted code and a unique JSONL breadcrumb file tagged
with server PID, SolidWorks target PID, timestamp, current source filename/line,
system commit usage/limit and available physical memory. Each record is flushed.
Python exceptions restore the previous tracer and mark failure. Abrupt native
exit leaves the last executed line, as verified with an isolated child process.
Tracing covers submitted/nested string code and scripts under its working
directory, excluding the MCP package and virtualenv. It does not capture locals
or COM properties and makes no CAD API calls. Submitted code is stored, just as
existing tool logs store code; use a private directory. Tracing adds per-line
disk and memory-counter overhead, so use only for diagnostic reproductions.

A line breadcrumb precedes execution. It cannot identify an individual API
inside a compound line or prove that the line caused a crash. Split CAD calls
into separate lines/steps; correlate with Windows event1000 by PID and time.
A completed tool result likewise does not prove native CAD shut down normally.

Use private copies and exactly one explicitly owned PID for CAD reproductions.
Verify all loaded document paths before any saves. Keep memory-warning action
explicit; do not continue past low-memory warnings just to provoke a crash.
Record commit headroom and the target's UserControl status. Compare shutdown
with loaded documents and after normal document closure, hook enabled/manual,
and backup disabled/enabled on separate private trials when resources allow.
Do not change shared registry/pagefile settings or another chat's worker.

Current findings are summarized in [ROOT_CAUSE_FINDINGS.md](ROOT_CAUSE_FINDINGS.md):
three native API/model-state fault paths were reproduced, and guarded alternatives
were tested. Several historical signatures and the earliest corrupting native
write remain unresolved. Detailed local evidence is under
`test-results/crash-probe-20261013/` (ignored by Git).

The live probe exposed one confirmed MCP defect: OpenDoc6 returned a document
after a low-memory No response, and the MCP reported success. The MCP now
returns failure with `operation_cancelled=true` whenever the requested cancel
handler recorded a warning, even if the dialog closed and a document was
returned. `document_returned` records that possibility; the MCP does not close
or save those documents. Handler errors likewise block a success response.
This stops callers that check success from silently proceeding into rebuild
and save work. It is not proof that every historic native crash had this cause.
Explicit `continue` remains supported only when chosen by the caller.

Diagnostic tracing excludes COM-generated `<string>` functions unless their
code belongs to a nested exec/eval submitted by user code. Filename selection
is cached and code identity uses integer IDs, avoiding repeated filesystem and
code-object hashing costs during large comtypes typelib imports. This matters:
the first historical replay wrote40,020 generated-code records and hit its
90-second client timeout without a native CAD crash. A subsequent filtered
replay completed the private weld-edit script in74.22seconds. Its read-only
Python stack sample located the wait in comtypes GetModule, not a CAD API call.
Do not interpret diagnostic overhead or client observation deadlines as proof
of native CAD deadlock/crash.
