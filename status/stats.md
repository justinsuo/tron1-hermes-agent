# Live Progress

**Last updated**: 2026-04-21 19:11:43  

**Total episodes**: 142  

**Success rate (last 30)**: 40%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 12/12 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 16/18 | 89% | +0.67 |
| `navigate-to-charge` | 9/18 | 50% | +0.25 |
| `read-gauge-N` | 20/41 | 49% | +0.17 |
| `find-door` | 4/9 | 44% | +0.00 |
| `read-any-gauge` | 11/32 | 34% | +0.15 |
| `navigate-home` | 1/10 | 10% | -0.31 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 142 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 141 | `read-any-gauge` | ✗ | -0.10 | N err 80.3% (too high) |
| 140 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 139 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 138 | `count-obstacles` | ✗ | -0.20 | pred 8 vs 4 |
| 137 | `read-gauge-N` | ✗ | -0.20 | err 543.7%, units_ok=False |
| 136 | `read-gauge-N` | ✓ | +0.30 | marginal err 10.8% |
| 135 | `read-gauge-N` | ✓ | +0.69 | err 6.1% on BAR |
| 134 | `read-any-gauge` | ✓ | +0.60 | W err 6.0% |
| 133 | `navigate-to-charge` | ✗ | -0.10 | far: 2.62 m |
| 132 | `read-gauge-N` | ✗ | -0.20 | err 45.7%, units_ok=False |
| 131 | `navigate-home` | ✗ | -0.10 | far from home: 4.14m |
| 130 | `navigate-to-charge` | ✗ | -0.10 | far: 15.99 m |
| 129 | `navigate-to-charge` | ✗ | -0.10 | far: 10.15 m |
| 128 | `read-gauge-N` | ✗ | -0.20 | err 24.3%, units_ok=False |
