# Live Progress

**Last updated**: 2026-04-21 19:20:44  

**Total episodes**: 148  

**Success rate (last 30)**: 33%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 12/12 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 16/18 | 89% | +0.67 |
| `find-door` | 5/10 | 50% | +0.02 |
| `navigate-to-charge` | 9/19 | 47% | +0.23 |
| `read-gauge-N` | 20/43 | 47% | +0.15 |
| `read-any-gauge` | 11/33 | 33% | +0.14 |
| `navigate-home` | 1/11 | 9% | -0.33 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 148 | `find-door` | ✓ | +0.20 | close: 1.12m |
| 147 | `read-gauge-N` | ✗ | -0.20 | err 23.3%, units_ok=True |
| 146 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 145 | `navigate-to-charge` | ✗ | -0.10 | far: 11.72 m |
| 144 | `read-gauge-N` | ✗ | -0.20 | err 36.3%, units_ok=True |
| 143 | `read-any-gauge` | ✗ | -0.10 | N err 60.7% (too high) |
| 142 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 141 | `read-any-gauge` | ✗ | -0.10 | N err 80.3% (too high) |
| 140 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 139 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 138 | `count-obstacles` | ✗ | -0.20 | pred 8 vs 4 |
| 137 | `read-gauge-N` | ✗ | -0.20 | err 543.7%, units_ok=False |
| 136 | `read-gauge-N` | ✓ | +0.30 | marginal err 10.8% |
| 135 | `read-gauge-N` | ✓ | +0.69 | err 6.1% on BAR |
| 134 | `read-any-gauge` | ✓ | +0.60 | W err 6.0% |
