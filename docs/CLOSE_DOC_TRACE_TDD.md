# Exact CloseDoc breadcrumbs

When `SOLIDWORKS_SCRIPT_TRACE_DIR` is set, `ScriptTrace` now records the title
passed to the loaded generated pywin32 `ISldWorks.CloseDoc` method. Previously,
one source line such as `for title in titles: sw.CloseDoc(title)` could identify
the API but not the failing loop iteration.

Each matching call emits `close_doc_begin`, followed by `close_doc_end` on normal
return or `close_doc_fail` on a Python exception. Rows include `title`,
`caller_filename`, `caller_line`, `api`, and the existing timestamp/server PID/
configured SolidWorks PID fields. If the process ends abruptly, the flushed
begin row still identifies the last attempted title. The recorded title is the
argument supplied by the caller; no CAD query resolves it to a document path.

Recognition requires the loaded `win32com.gen_py` module, its `ISldWorks` class
and IID, the actual `CloseDoc` function/code object, and an exact instance type.
Only a plain `str` named `Name` is copied from the Python frame. No COM attribute,
arbitrary `repr`, argument coercion, wrapper patch or additional CAD call is
used. Stored state contains scalars, not frames or COM wrappers. Other methods,
ordinary same-name objects and other threads do not produce these breadcrumbs.
Raw/dynamic COM calls and wrapper subclasses are outside this narrow scope.

The original opt-in setting remains the switch; there is no new global hook.
This improves evidence for future failures and does not repair native CloseDoc
faults, retrospectively identify old failing titles, or guarantee that a title
is unique. An API return is not a full document/process health check.
Failure to write an additional CloseDoc breadcrumb does not prevent the API
call or replace its return/exception; subsequent writable rows report
`close_doc_breadcrumb_errors`. A nonzero count marks incomplete breadcrumb
coverage. The pre-existing general source-line trace behavior is unchanged.

Evidence is local under ignored `test-results/close-doc-trace/`:

- `red.json`, `red.txt`, preserved baseline source and original regression source:
  three failures on base5266061 demonstrate the missing title/outcome records.
- [Regression tests](../tests/test_script_trace_close_doc.py) cover different
  loop titles, failures, fake methods/objects, non-string values, current-thread
  isolation, a caught failure followed by another call, and a harmless child
  process exiting before the wrapper returns.
- `red-write-failure.txt` reproduces all three original-error replacement cases
  before the narrow fail-open correction; the regression now preserves API
  calls and the original exception for begin/end/fail write failures.
- `actual-generated-wrapper.json` exercises this machine's actual generated
  SW2023 wrapper with a fake `InvokeTypes` backend, bypassing COM construction.
  It confirms real wrapper recognition without connecting to SolidWorks.
- `green-targeted.txt` and `final-green.json` record the bounded and full suites.

The isolated branch is not deployed. No CAD process, actual session metadata or
backup reservation was changed by these tests.
