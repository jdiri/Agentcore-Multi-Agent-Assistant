# Relevance threshold calibration (2026-11-19)

_Synthetic data. Scores from the Bedrock managed knowledge base, `status = current` filter applied, top result per question._

**Threshold: 0.940** (gap reply when the top score is below this).

The groups overlap (highest gap 0.9625, lowest answerable 0.9409). The threshold is a floor at the lowest answerable score, so no answerable question is refused. These gap questions score above it and are left to the model's coverage check: Q25, G06, G08, G09, G11, G12.

| | Count |
|---|---|
| Answerable questions (Q01–Q24) | 24 |
| Gap questions (Q25 + G01–G12) | 13 |
| Answerable refused by the threshold | 0 / 24 |
| Gap questions caught by the threshold | 7 / 13 |
| Gap questions left to the model's coverage check | 6 / 13 |
| Answerable: top result is an expected source | 17 / 24 |
| Answerable: an expected source is in the results | 23 / 24 |

Retrieve latency over 37 calls (budget < 1 s): median 643 ms, p95 1326 ms, max 2107 ms.

## Scores (highest first)

| ID | Kind | Case | Top score | Threshold decision | Correct | Top source |
|---|---|---|---|---|---|---|
| G12 | gap | near_miss | 0.9625 | passes; model checks | model | Dividends & Distributions FAQ, 2025-12 |
| G08 | gap | near_miss | 0.9600 | passes; model checks | model | Account Types Guide v1.5, s.6 |
| Q04 | answerable | superseded | 0.9574 | answer | yes | Account Transfer Policy v3.2, s.4 |
| Q12 | answerable | standard | 0.9562 | answer | yes | Frequent Trading Policy v1.4, s.2 |
| Q11 | answerable | standard | 0.9560 | answer | yes | Contributions & Deposits Policy v2.1, s.2 |
| Q08 | answerable | standard | 0.9558 | answer | yes | Account Access & Security Policy v4.0, s.3 |
| Q01 | answerable | superseded | 0.9557 | answer | yes | Account Transfer Policy v3.2, s.4 |
| Q18 | answerable | standard | 0.9545 | answer | yes | Trading Hours & Market Holidays Notice, 2026, s.2 |
| Q10 | answerable | standard | 0.9542 | answer | yes | Withdrawals & Redemptions Policy v2.3, s.2 |
| Q17 | answerable | standard | 0.9521 | answer | yes | Dividends & Distributions FAQ, 2025-12 |
| Q03 | answerable | superseded | 0.9521 | answer | yes | Account Transfer Policy v3.2, s.5 |
| Q16 | answerable | injection_doc | 0.9517 | answer | yes | Statements & Documents FAQ, 2025-09 |
| Q15 | answerable | injection_doc | 0.9516 | answer | yes | Statements & Documents FAQ, 2025-09 |
| Q05 | answerable | superseded | 0.9503 | answer | yes | Fee Schedule FAQ, 2026-01 |
| G09 | gap | near_miss | 0.9487 | passes; model checks | model | Automatic Investment Plan FAQ, 2025-06 |
| Q02 | answerable | superseded | 0.9474 | answer | yes | Fee Schedule FAQ, 2026-01 |
| Q20 | answerable | standard | 0.9472 | answer | yes | Address & Profile Changes FAQ, 2025-04 |
| Q22 | answerable | standard | 0.9468 | answer | yes | Account Closure Policy v1.2, s.3 |
| Q09 | answerable | standard | 0.9465 | answer | yes | Account Access & Security Policy v4.0, s.4 |
| Q21 | answerable | standard | 0.9458 | answer | yes | Automatic Investment Plan FAQ, 2025-06 |
| Q24 | answerable | standard | 0.9457 | answer | yes | Statements & Documents FAQ, 2025-09 |
| Q06 | answerable | standard | 0.9452 | answer | yes | Fee Schedule FAQ, 2026-01 |
| Q25 | gap | gap | 0.9445 | passes; model checks | model | Address & Profile Changes FAQ, 2025-04 |
| Q07 | answerable | standard | 0.9444 | answer | yes | Fee Schedule FAQ, 2026-01 |
| Q13 | answerable | standard | 0.9436 | answer | yes | Fund Minimums & Investment Options FAQ, 2026-02 |
| G06 | gap | near_miss | 0.9436 | passes; model checks | model | Fund Minimums & Investment Options FAQ, 2026-02 |
| G11 | gap | near_miss | 0.9422 | passes; model checks | model | Account Types Guide v1.5, s.7 |
| Q14 | answerable | injection_doc | 0.9414 | answer | yes | Statements & Documents FAQ, 2025-09 |
| Q19 | answerable | standard | 0.9413 | answer | yes | Address & Profile Changes FAQ, 2025-04 |
| Q23 | answerable | standard | 0.9409 | answer | yes | Support Ticket Handling Policy v2.0, s.1 |
| G02 | gap | off_topic | 0.9372 | gap reply | yes | Dividends & Distributions FAQ, 2025-12 |
| G05 | gap | near_miss | 0.9324 | gap reply | yes | Fee Schedule FAQ, 2026-01 |
| G07 | gap | near_miss | 0.9301 | gap reply | yes | Account Types Guide v1.5, s.2 |
| G04 | gap | off_topic | 0.9217 | gap reply | yes | Account Access & Security Policy v4.0, s.4 |
| G01 | gap | off_topic | 0.9151 | gap reply | yes | Fee Schedule FAQ, 2026-01 |
| G10 | gap | near_miss | 0.9144 | gap reply | yes | Support Ticket Handling Policy v2.0, s.6 |
| G03 | gap | off_topic | 0.9111 | gap reply | yes | Trading Hours & Market Holidays Notice, 2026, s.3 |
