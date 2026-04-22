# Live Progress

**Last updated**: 2026-04-21 18:51:39  

**Total episodes**: 127  

**Success rate (last 30)**: 53%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 11/11 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 15/16 | 94% | +0.71 |
| `navigate-to-charge` | 9/15 | 60% | +0.32 |
| `read-gauge-N` | 18/36 | 50% | +0.18 |
| `find-door` | 4/9 | 44% | +0.00 |
| `read-any-gauge` | 10/30 | 33% | +0.14 |
| `navigate-home` | 1/8 | 12% | -0.31 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 127 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 126 | `read-gauge-N` | ✗ | -0.20 | err 41.2%, units_ok=True |
| 125 | `navigate-to-charge` | ✓ | +0.69 | within 0.31 m |
| 124 | `read-gauge-N` | ✗ | -0.20 | err 44.4%, units_ok=True |
| 123 | `read-any-gauge` | ✗ | -0.10 | N err 21.7% (too high) |
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
