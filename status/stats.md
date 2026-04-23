# Live Progress

**Last updated**: 2026-04-22 21:57:47  

**Total episodes**: 379  

**Success rate (last 30)**: 33%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 22/22 | 100% | +0.80 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 25/29 | 86% | +0.59 |
| `find-door` | 15/20 | 75% | +0.15 |
| `read-gauge-N` | 66/143 | 46% | +0.16 |
| `navigate-to-charge` | 10/37 | 27% | +0.08 |
| `read-any-gauge` | 23/86 | 27% | +0.09 |
| `navigate-home` | 9/40 | 22% | -0.25 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 379 | `navigate-home` | ✗ | -0.10 | far from home: 6.96m |
| 378 | `read-gauge-N` | ✗ | -0.20 | err 87.5%, units_ok=False |
| 377 | `navigate-to-charge` | ✗ | -0.10 | far: 9.55 m |
| 376 | `read-gauge-N` | ✗ | -0.20 | err 20.2%, units_ok=True |
| 375 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 374 | `read-any-gauge` | ✗ | -0.30 | no JSON reading |
| 373 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 372 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 371 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.0% |
| 370 | `navigate-to-charge` | ✗ | -0.10 | far: 9.91 m |
| 369 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'PSI' |
| 368 | `read-any-gauge` | ✗ | -0.10 | N err 70.0% (too high) |
| 367 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 366 | `read-gauge-N` | ✓ | +0.94 | err 1.1% on °C |
| 365 | `find-door` | ✓ | +0.65 | door dist 0.71m bearing -15° |
