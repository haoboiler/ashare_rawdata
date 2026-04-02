# Progress

## 2026-03-25

- Started diagnosis of missing TG send after researcher evolve benchmark.
- Confirmed report file exists for `ashare_rawdata_b`, but the sent-reports ledger has not been updated.
- Reproduced the hourly loop bug locally: the script scheduled the next run about 7 hours later instead of the next hour.
- Confirmed the benchmark report was in fact sent by the researcher: `2026-03-25_apm_momentum_evolve_benchmark.md sent (msg_id=1028)`.
- Confirmed the benchmark cycle completed normally, transitioned `ashare_rawdata_b` to `idle`, and wrapper entered cycle 2 after cooldown.
- Patched `researcher_wrapper.sh` to add a shell-side TG report fallback based on the latest report path and `.last_sent_reports`.
- Patched `hourly_report_loop.sh` to compute the next top-of-hour using epoch arithmetic.
- Restarted `ashare_rawdata_hourly_report`; it immediately sent a status update plus a new unsent screening report and now sleeps about 37 minutes to `19:00`.
- Restarted `ashare_rawdata_b` so the new wrapper logic is loaded, and cleared the stale one-shot `leader_instruction`.
