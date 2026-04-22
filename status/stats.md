# Live Progress

**Last updated**: 2026-04-21 18:41:37  

**Total episodes**: 122  

**Success rate (last 30)**: 57%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 11/11 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 14/15 | 93% | +0.69 |
| `navigate-to-charge` | 8/14 | 57% | +0.29 |
| `read-gauge-N` | 18/34 | 53% | +0.20 |
| `find-door` | 4/9 | 44% | +0.00 |
| `read-any-gauge` | 10/29 | 34% | +0.15 |
| `navigate-home` | 1/8 | 12% | -0.31 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 122 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units '°C' |
| 121 | `read-gauge-N` | ✗ | -0.20 | err 15.2%, units_ok=True |
| 120 | `describe-scene` | ✓ | +0.80 | 8 scene keywords matched |
| 119 | `navigate-to-charge` | ✓ | +0.83 | within 0.17 m |
| 118 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 117 | `read-any-gauge` | ✗ | -0.10 | N err 44.6% (too high) |
| 116 | `find-door` | ✓ | +0.55 | door dist 0.91m bearing +18° |
| 115 | `navigate-to-charge` | ✓ | +0.72 | within 0.28 m |
| 114 | `read-any-gauge` | ✗ | -0.10 | E err 25.5% (too high) |
| 113 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 112 | `find-door` | ✓ | +0.63 | door dist 0.73m bearing +8° |
| 111 | `navigate-to-charge` | ✓ | +0.94 | within 0.06 m |
| 110 | `read-any-gauge` | ✓ | +0.85 | N err 2.2% |
| 109 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 108 | `navigate-to-charge` | ✓ | +0.72 | within 0.28 m |
