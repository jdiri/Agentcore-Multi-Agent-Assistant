# Relevance threshold calibration (2026-11-12)

_Synthetic data. Scores from the Bedrock managed knowledge base, `status = current` filter applied, top result per question._

**Threshold: 0.963** (answer when the top score is at least this).

The groups overlap (highest gap 0.9625, lowest answerable 0.9409). Policy is fewer wrong answers, so the threshold sits just above the highest gap score; these answerable questions would get the gap reply instead: Q01, Q02, Q03, Q04, Q05, Q06, Q07, Q08, Q09, Q10, Q11, Q12, Q13, Q14, Q15, Q16, Q17, Q18, Q19, Q20, Q21, Q22, Q23, Q24.

| | Count |
|---|---|
| Answerable questions (Q01–Q24) | 24 |
| Gap questions (Q25 + G01–G12) | 13 |
| Correct answer/gap decisions at this threshold | 13 / 37 |
| Answerable: top result is an expected source | 17 / 24 |
| Answerable: an expected source is in the results | 23 / 24 |

## Scores (highest first)

| ID | Kind | Case | Top score | Decision | Correct | Top source |
|---|---|---|---|---|---|---|
| G12 | gap | near_miss | 0.9625 | gap reply | yes | Dividends & Distributions FAQ, 2025-12 |
| G08 | gap | near_miss | 0.9600 | gap reply | yes | Account Types Guide v1.5, s.6 |
| Q04 | answerable | superseded | 0.9574 | gap reply | **no** | Account Transfer Policy v3.2, s.4 |
| Q12 | answerable | standard | 0.9562 | gap reply | **no** | Frequent Trading Policy v1.4, s.2 |
| Q11 | answerable | standard | 0.9560 | gap reply | **no** | Contributions & Deposits Policy v2.1, s.2 |
| Q08 | answerable | standard | 0.9558 | gap reply | **no** | Account Access & Security Policy v4.0, s.3 |
| Q01 | answerable | superseded | 0.9557 | gap reply | **no** | Account Transfer Policy v3.2, s.4 |
| Q18 | answerable | standard | 0.9545 | gap reply | **no** | Trading Hours & Market Holidays Notice, 2026, s.2 |
| Q10 | answerable | standard | 0.9542 | gap reply | **no** | Withdrawals & Redemptions Policy v2.3, s.2 |
| Q17 | answerable | standard | 0.9521 | gap reply | **no** | Dividends & Distributions FAQ, 2025-12 |
| Q03 | answerable | superseded | 0.9521 | gap reply | **no** | Account Transfer Policy v3.2, s.5 |
| Q16 | answerable | injection_doc | 0.9517 | gap reply | **no** | Statements & Documents FAQ, 2025-09 |
| Q15 | answerable | injection_doc | 0.9516 | gap reply | **no** | Statements & Documents FAQ, 2025-09 |
| Q05 | answerable | superseded | 0.9503 | gap reply | **no** | Fee Schedule FAQ, 2026-01 |
| G09 | gap | near_miss | 0.9487 | gap reply | yes | Automatic Investment Plan FAQ, 2025-06 |
| Q02 | answerable | superseded | 0.9474 | gap reply | **no** | Fee Schedule FAQ, 2026-01 |
| Q20 | answerable | standard | 0.9472 | gap reply | **no** | Address & Profile Changes FAQ, 2025-04 |
| Q22 | answerable | standard | 0.9468 | gap reply | **no** | Account Closure Policy v1.2, s.3 |
| Q09 | answerable | standard | 0.9465 | gap reply | **no** | Account Access & Security Policy v4.0, s.4 |
| Q21 | answerable | standard | 0.9458 | gap reply | **no** | Automatic Investment Plan FAQ, 2025-06 |
| Q24 | answerable | standard | 0.9457 | gap reply | **no** | Statements & Documents FAQ, 2025-09 |
| Q06 | answerable | standard | 0.9452 | gap reply | **no** | Fee Schedule FAQ, 2026-01 |
| Q25 | gap | gap | 0.9445 | gap reply | yes | Address & Profile Changes FAQ, 2025-04 |
| Q07 | answerable | standard | 0.9444 | gap reply | **no** | Fee Schedule FAQ, 2026-01 |
| Q13 | answerable | standard | 0.9436 | gap reply | **no** | Fund Minimums & Investment Options FAQ, 2026-02 |
| G06 | gap | near_miss | 0.9436 | gap reply | yes | Fund Minimums & Investment Options FAQ, 2026-02 |
| G11 | gap | near_miss | 0.9422 | gap reply | yes | Account Types Guide v1.5, s.7 |
| Q14 | answerable | injection_doc | 0.9414 | gap reply | **no** | Statements & Documents FAQ, 2025-09 |
| Q19 | answerable | standard | 0.9413 | gap reply | **no** | Address & Profile Changes FAQ, 2025-04 |
| Q23 | answerable | standard | 0.9409 | gap reply | **no** | Support Ticket Handling Policy v2.0, s.1 |
| G02 | gap | off_topic | 0.9372 | gap reply | yes | Dividends & Distributions FAQ, 2025-12 |
| G05 | gap | near_miss | 0.9324 | gap reply | yes | Fee Schedule FAQ, 2026-01 |
| G07 | gap | near_miss | 0.9301 | gap reply | yes | Account Types Guide v1.5, s.2 |
| G04 | gap | off_topic | 0.9217 | gap reply | yes | Account Access & Security Policy v4.0, s.4 |
| G01 | gap | off_topic | 0.9151 | gap reply | yes | Fee Schedule FAQ, 2026-01 |
| G10 | gap | near_miss | 0.9144 | gap reply | yes | Support Ticket Handling Policy v2.0, s.6 |
| G03 | gap | off_topic | 0.9111 | gap reply | yes | Trading Hours & Market Holidays Notice, 2026, s.3 |
