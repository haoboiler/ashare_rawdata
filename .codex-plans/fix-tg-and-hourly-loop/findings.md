# Findings

- The last researcher cycle wrote the screening report but did not append the report basename into `orchestration/state/.last_sent_reports`.
- The researcher prompt requires TG send in Step 4, but that guarantee exists only at prompt level.
- `hourly_report_loop.sh` currently computes `next_hour_epoch` with a `date -d` expression that resolves to the next day `01:00`, not the next hour.
- Deeper inspection showed the specific `ashare_rawdata_b` benchmark cycle did actually send TG successfully: `msg_id=1028`, and the report basename was appended into `.last_sent_reports`.
- The apparent “no next round” symptom was timing-related. The benchmark cycle completed, updated state to `idle`, then the wrapper cooled down and entered cycle 2.
- Even though the specific cycle succeeded, the researcher report send path was still fragile because it depended entirely on the model remembering Step 4.
