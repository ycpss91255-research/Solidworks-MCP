# Backup completion audit

Last checked 2026-10-13. The overall goal is **not complete**.

| Requirement | Authoritative evidence | Current result |
| --- | --- | --- |
| Default reads the connected PID's native enable flags and minute interval | `recovery_policy.py`; `test_recovery_policy.py`; real `rack-private-proof/native-first-connect.json` | Passed: native AutoRecover enabled, backup disabled, one-minute interval; no preference writes |
| Separate session directories, PID and creation ownership | session-path hash policy; per-generation manifests; helper/session identity guards | Passed in private tests; no shared PID retargeting |
| MR12 STEP and assembly state repair | `mr12-isolated-proof/compact-default-complete.json` | Complete package: 1,405 primaries, 1,407 hashes, 2,853 occurrences, source disk/RAM preserved |
| Rack real timed backup and MCP reconnect | `rack-private-proof/native-timed-reconnect-proof.json` | Two complete packages; same worker/creation identity reused after MCP exit; native interval followed |
| Rack independent restore | `rack-private-proof/fresh-restore-proof.json` | 108 occurrences, reference configurations and volume matched; error/warning 0; hash inventory preserved |
| MR12 independent restore | `mr12-isolated-proof/compact-default-fresh-restore-proof.json` | Passed in fresh PID 32184: 2,853 occurrences/configurations, 1,405 private sources, volume 34.57444172181828 m³, all 1,407 hashes preserved; source's validated missing-reference flag retained |
| Settings behavior | native policy/monitor tests and real native-interval test | Minute mode proven; count mode requires explicit time override. Backup-only is supplemental periodic recovery, not native on-save revision backup |
| Support limits recorded | deployment and independent-repair documents | Source's missing suppressed/native context references are retained, not recovered; current drawing helper unsupported; native AutoRecover itself not restored |
| Fork branch published without changing main | remote `codex/pid-isolation` at `d6bdf58`; remote main at `ee8f42a1a919af5e0fa8d1dcd24270c9983ce027` | Published; main unchanged |
| Existing production sessions migrated and verified | live old MR12 worker PID 24684; its status/stack; unchanged working configs | Incomplete. Old worker stuck at GetPackAndGo; cross-chat migration authorization requested and pending |

Tests and ignored CAD artifacts are evidence for their stated scope only.
Private fixture validation does not prove the working chats are protected.
Do not mark completion while production migration is unverified. All private
test CADs have exited normally; only the two working CADs remain. Retain all
earlier failed generations as failed.
