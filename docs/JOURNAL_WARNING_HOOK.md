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
