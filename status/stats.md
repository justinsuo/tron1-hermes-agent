# Live Progress

**Last updated**: 2026-04-21 19:00:30  

**Total episodes**: 133  

**Success rate (last 30)**: 43%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 11/11 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 15/16 | 94% | +0.71 |
| `navigate-to-charge` | 9/18 | 50% | +0.25 |
| `read-gauge-N` | 18/38 | 47% | +0.16 |
| `find-door` | 4/9 | 44% | +0.00 |
| `read-any-gauge` | 10/30 | 33% | +0.14 |
| `navigate-home` | 1/9 | 11% | -0.29 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 133 | `navigate-to-charge` | ✗ | -0.10 | far: 2.62 m |
| 132 | `read-gauge-N` | ✗ | -0.20 | err 45.7%, units_ok=False |
| 131 | `navigate-home` | ✗ | -0.10 | far from home: 4.14m |
| 130 | `navigate-to-charge` | ✗ | -0.10 | far: 15.99 m |
| 129 | `navigate-to-charge` | ✗ | -0.10 | far: 10.15 m |
| 128 | `read-gauge-N` | ✗ | -0.20 | err 24.3%, units_ok=False |
| 127 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 126 | `read-gauge-N` | ✗ | -0.20 | err 41.2%, units_ok=True |
| 125 | `navigate-to-charge` | ✓ | +0.69 | within 0.31 m |
| 124 | `read-gauge-N` | ✗ | -0.20 | err 44.4%, units_ok=True |
| 123 | `read-any-gauge` | ✗ | -0.10 | N err 21.7% (too high) |
| 122 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units '°C' |
| 121 | `read-gauge-N` | ✗ | -0.20 | err 15.2%, units_ok=True |
| 120 | `describe-scene` | ✓ | +0.80 | 8 scene keywords matched |
| 119 | `navigate-to-charge` | ✓ | +0.83 | within 0.17 m |
