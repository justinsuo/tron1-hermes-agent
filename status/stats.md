# Live Progress

**Last updated**: 2026-04-21 22:42:25  

**Total episodes**: 326  

**Success rate (last 30)**: 43%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 20/20 | 100% | +0.80 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 22/26 | 85% | +0.60 |
| `find-door` | 14/19 | 74% | +0.13 |
| `read-gauge-N` | 54/116 | 47% | +0.16 |
| `navigate-to-charge` | 10/33 | 30% | +0.10 |
| `read-any-gauge` | 21/75 | 28% | +0.10 |
| `navigate-home` | 8/35 | 23% | -0.25 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 326 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'RPM' |
| 325 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 324 | `count-obstacles` | ✓ | +0.30 | pred 5 vs 4 (close) |
| 323 | `navigate-to-charge` | ✗ | -0.10 | far: 3.71 m |
| 322 | `read-any-gauge` | ✗ | -0.10 | E err 38.6% (too high) |
| 321 | `navigate-home` | ✓ | +0.30 | close: 0.73m |
| 320 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'hours' |
| 319 | `read-any-gauge` | ✗ | -0.10 | N err 422.3% (too high) |
| 318 | `find-door` | ✓ | +0.20 | close: 1.13m |
| 317 | `read-any-gauge` | ✗ | -0.10 | E err 13.2% (too high) |
| 316 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units '°C' |
| 315 | `read-gauge-N` | ✓ | +0.95 | err 1.1% on BAR |
| 314 | `navigate-to-charge` | ✗ | -0.10 | far: 4.53 m |
| 313 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 312 | `read-any-gauge` | ✓ | +0.64 | N err 5.4% |
