# Live Progress

**Last updated**: 2026-04-21 23:32:33  

**Total episodes**: 369  

**Success rate (last 30)**: 50%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 22/22 | 100% | +0.80 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 25/29 | 86% | +0.59 |
| `find-door` | 15/20 | 75% | +0.15 |
| `read-gauge-N` | 65/137 | 47% | +0.18 |
| `navigate-to-charge` | 10/35 | 29% | +0.09 |
| `read-any-gauge` | 23/85 | 27% | +0.09 |
| `navigate-home` | 9/39 | 23% | -0.26 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 369 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'PSI' |
| 368 | `read-any-gauge` | ✗ | -0.10 | N err 70.0% (too high) |
| 367 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 366 | `read-gauge-N` | ✓ | +0.94 | err 1.1% on °C |
| 365 | `find-door` | ✓ | +0.65 | door dist 0.71m bearing -15° |
| 364 | `navigate-to-charge` | ✗ | -0.10 | far: 4.14 m |
| 363 | `navigate-home` | ✓ | +0.30 | close: 0.86m |
| 362 | `read-any-gauge` | ✓ | +0.58 | W err 6.2% |
| 361 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.3% |
| 360 | `read-gauge-N` | ✓ | +0.30 | marginal err 14.5% |
| 359 | `read-gauge-N` | ✓ | +0.89 | err 2.1% on PSI |
| 358 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 357 | `read-gauge-N` | ✓ | +0.94 | err 1.1% on PSI |
| 356 | `count-obstacles` | ✓ | +0.30 | pred 5 vs 4 (close) |
| 355 | `read-gauge-N` | ✗ | -0.20 | err 31.8%, units_ok=True |
