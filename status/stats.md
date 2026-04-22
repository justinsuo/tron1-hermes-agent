# Live Progress

**Last updated**: 2026-04-21 22:52:27  

**Total episodes**: 333  

**Success rate (last 30)**: 43%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 21/21 | 100% | +0.80 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 23/27 | 85% | +0.59 |
| `find-door` | 14/19 | 74% | +0.13 |
| `read-gauge-N` | 55/119 | 46% | +0.16 |
| `navigate-to-charge` | 10/34 | 29% | +0.09 |
| `read-any-gauge` | 21/75 | 28% | +0.10 |
| `navigate-home` | 8/36 | 22% | -0.26 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 333 | `read-gauge-N` | ✗ | -0.20 | err 15.5%, units_ok=False |
| 332 | `read-gauge-N` | ✓ | +0.76 | err 4.9% on V |
| 331 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 330 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 329 | `count-obstacles` | ✓ | +0.30 | pred 3 vs 4 (close) |
| 328 | `navigate-to-charge` | ✗ | -0.10 | far: 6.66 m |
| 327 | `read-gauge-N` | ✗ | -0.20 | err 22.2%, units_ok=True |
| 326 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'RPM' |
| 325 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 324 | `count-obstacles` | ✓ | +0.30 | pred 5 vs 4 (close) |
| 323 | `navigate-to-charge` | ✗ | -0.10 | far: 3.71 m |
| 322 | `read-any-gauge` | ✗ | -0.10 | E err 38.6% (too high) |
| 321 | `navigate-home` | ✓ | +0.30 | close: 0.73m |
| 320 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'hours' |
| 319 | `read-any-gauge` | ✗ | -0.10 | N err 422.3% (too high) |
