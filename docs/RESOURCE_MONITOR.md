# Resource waiting for owned native tests

User correction, 2026-10-15: temporary environment pressure must not stop the
investigation. Keep an observable monitor running and resume private tests when
the environment recovers. This replaces treating temporary headroom as an
external blocker without a waiting mechanism.

`python -m solidworks_mcp.diagnostics.resource_wait` samples commit and available
physical memory every five seconds. Three consecutive readings of at most90%
commit and at least4096MB available are required before invoking one explicitly
provided command. Unknown/failed readings remain waiting. These are laboratory
thresholds, not a machine-wide SolidWorks instance cap.

State and cancellation files must be absolute and chat-owned. The status records
the monitor PID and creation time. An OS-held file lock prevents duplicate
monitors for one state; a terminal/running state prevents automatic command
replay after restart. Every observation/transition is retained in the adjacent
events.jsonl. Command failure is terminal for that invocation, not retried on
partially modified CAD. A cancellation marker cancels waiting; it does not kill
a command/CAD already running. No CAD API is called by the monitor itself.

The current owned pipeline is retained under ignored
`test-results/remaining-fault-correlation/`: `run_monitored_bisect.py` invokes
`launch_run_bisect.py` through separate resource gates for BO and BP. Each uses
its own guarded-launcher session, private frozen-input copy, explicit PID/log,
memory-warning cancellation and native exception watcher. No other session PID
or shared configuration is modified.

Runtime verification: BO's resource gate reached running and completed with a
successful native mirror-only save/close/exit. BP's gate subsequently observed
commit above90%, stayed waiting, then logged three safe readings and changed to
running automatically. Worker35896 and its recorded creation identity were
verified live. This proves waiting and automatic continuation in the real
environment, not merely a mock gate test. Native BP results are separate evidence.

Five retained unit tests cover pressure/stability, invalid readings, cancellation,
failure without replay and duplicate lock exclusion. Full discovery passes264
tests. The pipeline's active exec handle is19958; later turns must verify that
handle or the recorded worker identity before deciding it is stopped or starting
another copy. Persistent goal status remains active while this monitored work
is live. Never mark the crash investigation complete from resource-monitor tests.
