# Backup worker migration plan

Prepared on 2026-10-13; not applied to another chat.

## MR12 current state

- Working CAD: PID 2836. Do not terminate, save, close documents or retarget it.
- Existing worker: PID 24684, creation identity
  `2026-10-12T13:30:14.968000+00:00` (revalidate at execution).
- Status file: `C:/Users/yunchien.chen/.codex/worktrees/a946/solidworks_data/.codex/recovery/mr12-session/monitor.json`.
- The worker is live, its status remains `snapshot_in_progress`, and it does
  not follow native preferences. A nonblocking external stack dump locates it
  in the old `NativePack.__init__`, at `extension.GetPackAndGo()` (old line 34).
  This stack is before package file saves; no native stack was collected because
  the diagnostic tool cannot do that without pausing the process.

## Proposed actions, requiring cross-chat authorization

1. Revalidate status ownership, Python executable and worker creation identity.
2. Write only the existing worker's private `requested.stop` marker. Wait for a
   normal stop and confirm its actual process has exited. Do not start a second
   worker while the old one remains live.
3. If still stuck in the same getter, stop here unless the user explicitly
   authorizes terminating that identified Python worker. Never terminate CAD.
4. Preserve the MR12 source PID/session configuration. Configure a separate
   explicitly owned repair helper state file in that chat, with role
   `recovery_repair` and source-session ownership. Its CAD is separate and uses
   the guarded launcher; it never opens the working source model.
5. Reconnect its MCP with current code and native preference mode. Existing
   recovery files remain retained. Keep native preferences unchanged and use
   the default session-hashed recovery directory.
6. Require an observed complete backup, source-preservation evidence, helper
   privacy checks, worker identity and reconnect reuse before claiming this
   working session is protected. A successful connection alone is insufficient.

The current user permission covers isolated tests. The supplied session rules
prohibit using another chat's PID/session file, so this plan is not authority to
perform steps 2–6 against MR12. No working session configuration was changed.

