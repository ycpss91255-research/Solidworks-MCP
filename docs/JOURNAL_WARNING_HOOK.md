# Journal warning connection hook

Set `SOLIDWORKS_JOURNAL_WARNING_ACTION=dismiss` to enable the hook. `manual`
remains the default because dismissal requires explicit authorization.

Both managed startup and attachment to an existing configured PID start the
watcher before COM connection, including sessions whose manifest is already
`ready`. The watcher remains active throughout that MCP connection, handles
repeated/late warnings, and stops on disconnect, failed connection, or process
exit. Reconnecting reuses a live watcher; changing targets stops the previous
watcher. A retained process handle prevents following a recycled PID.

Only visible native SolidWorks dialogs belonging to that PID with the specific
journal/AutoRecover warning text and a sole OK button are dismissed. Memory,
save, installation, and other dialogs are excluded. Native child-window APIs
avoid making a COM/UIA request against a modal application.

Connection responses expose `journal_warning_hook` with PID, running state,
events and errors. Logs distinguish sending the dismissal from observing the
window actually close. The warning can appear briefly before detection.

This does not remove the native journal lock or restore native AutoRecover.
Manual SolidWorks launches without a connected authorized MCP have no hook.
After updating code, restart each MCP connection to load this implementation;
restarting MCP does not require closing SolidWorks or changing another chat's
PID/session file. Old running MCP processes retain their old code.

Validation: unit tests cover repeated delayed warnings, exact text/PID/button
exclusions, hook reuse, manual opt-out, target changes, and hook ordering for an
already-ready managed session. No existing working SolidWorks was operated in
this validation. All 216 unit tests passed. A separate Windows test process
(PID 28596) displayed two real native MessageBoxes with the exact journal text;
the continuous watcher closed both, recorded `closed=true` twice and no errors.
Live CAD validation of the new continuous hook remains pending.

2026-10-14 live correction: startup warning in owned PID31556 was still visible
after launcher and a second BM_CLICK watcher attempt, both recording closed=false.
Sending the verified button's BN_CLICKED notification (WM_COMMAND) directly to
the exact dialog via SendMessageTimeout closed that same warning (closed=true,
no errors). BM_CLICK can fail for inactive dialogs; no activation, foreground
switch or global keyboard event is required by the replacement. PID38068 was
another session and was not operated. This validates the actual native warning,
but does not remove the underlying shared journal lock.

Microsoft references:
https://learn.microsoft.com/en-us/windows/win32/controls/bm-click
https://learn.microsoft.com/en-us/windows/win32/controls/bn-clicked
