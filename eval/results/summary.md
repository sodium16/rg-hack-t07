# Evaluation summary

Transcript source: clip1.mp3 (cached)

| Test | Metric | Result | Verdict |
|---|---|---|---|
| A1 | WER | 1.50% (S4 I0 D0) | PASS |
| A1 | timestamps monotonic | True | PASS |
| A2 | within 5s | 10/10 (100.0%) | PASS |
| A2 | correct answers | 10/10 | PASS |
| A3 | not_covered_unrelated | 5/5 refused | PASS |
| A3 | not_covered_near_miss | 5/5 refused | PASS |
| A3 | leading_false_premise | 3/3 refused | PASS |
| A3 | key terms present | 5/5 | PASS |

Targets: A1 WER <= 10%; A2 >= 90% of covered questions within +/-5s; A3 100% unrelated refused, >= 90% near-miss refused, 100% key terms present.

Report misses honestly in the Evidence Sheet and say what changed.
