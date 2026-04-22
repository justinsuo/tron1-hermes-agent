# Live Progress

**Last updated**: 2026-04-21 19:53:45  

**Total episodes**: 170  

**Success rate (last 30)**: 33%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 12/12 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 17/20 | 85% | +0.65 |
| `find-door` | 8/13 | 62% | +0.06 |
| `navigate-to-charge` | 9/19 | 47% | +0.23 |
| `read-gauge-N` | 23/52 | 44% | +0.14 |
| `read-any-gauge` | 13/38 | 34% | +0.16 |
| `navigate-home` | 1/14 | 7% | -0.34 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 170 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 169 | `navigate-home` | ✗ | -0.10 | far from home: 6.89m |
| 168 | `find-door` | ✓ | +0.20 | close: 1.50m |
| 167 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'unspecified' |
| 166 | `read-gauge-N` | ✓ | +0.30 | marginal err 14.9% |
| 165 | `read-any-gauge` | ✓ | +0.98 | N err 0.3% |
| 164 | `find-door` | ✓ | +0.20 | close: 1.23m |
| 163 | `read-any-gauge` | ✓ | +0.79 | N err 3.1% |
| 162 | `count-obstacles` | ✗ | -0.20 | pred 7 vs 4 |
| 161 | `read-gauge-N` | ✗ | -0.20 | err 18.5%, units_ok=True |
| 160 | `read-gauge-N` | ✓ | +0.94 | err 1.2% on V |
| 159 | `read-any-gauge` | ✗ | -0.10 | E err 23.9% (too high) |
| 158 | `read-gauge-N` | ✗ | -0.20 | err 21.5%, units_ok=True |
| 157 | `read-gauge-N` | ✗ | -0.20 | err 27.3%, units_ok=True |
| 156 | `navigate-home` | ✗ | -0.50 | hermes timed out |
