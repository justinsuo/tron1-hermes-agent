# Live Progress

**Last updated**: 2026-04-21 23:12:31  

**Total episodes**: 351  

**Success rate (last 30)**: 40%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 22/22 | 100% | +0.80 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 24/28 | 86% | +0.60 |
| `find-door` | 14/19 | 74% | +0.13 |
| `read-gauge-N` | 60/128 | 47% | +0.17 |
| `navigate-to-charge` | 10/34 | 29% | +0.09 |
| `read-any-gauge` | 22/81 | 27% | +0.10 |
| `navigate-home` | 8/37 | 22% | -0.26 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 351 | `read-gauge-N` | ✗ | -0.20 | err 34.5%, units_ok=True |
| 350 | `read-any-gauge` | ✗ | -0.10 | N err 457.9% (too high) |
| 349 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'deg' |
| 348 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 347 | `read-gauge-N` | ✓ | +0.30 | marginal err 9.0% |
| 346 | `read-gauge-N` | ✓ | +0.30 | marginal err 9.2% |
| 345 | `read-any-gauge` | ✗ | -0.10 | N err 72.5% (too high) |
| 344 | `describe-scene` | ✓ | +0.80 | 7 scene keywords matched |
| 343 | `read-gauge-N` | ✓ | +0.99 | err 0.2% on PSI |
| 342 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 341 | `read-any-gauge` | ✗ | -0.10 | E err 15.7% (too high) |
| 340 | `read-any-gauge` | ✓ | +0.87 | N err 1.9% |
| 339 | `read-gauge-N` | ✓ | +1.00 | err 0.0% on V |
| 338 | `read-gauge-N` | ✓ | +0.93 | err 1.4% on PSI |
| 337 | `navigate-home` | ✗ | -0.50 | hermes timed out |
