# Live Progress

**Last updated**: 2026-04-21 21:02:05  

**Total episodes**: 228  

**Success rate (last 30)**: 43%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 14/14 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/23 | 83% | +0.61 |
| `find-door` | 11/16 | 69% | +0.09 |
| `read-gauge-N` | 36/75 | 48% | +0.17 |
| `navigate-to-charge` | 9/23 | 39% | +0.17 |
| `read-any-gauge` | 15/51 | 29% | +0.11 |
| `navigate-home` | 3/24 | 12% | -0.34 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 228 | `navigate-to-charge` | ✗ | -0.10 | far: 7.26 m |
| 227 | `read-gauge-N` | ✓ | +1.00 | err 0.0% on BAR |
| 226 | `read-gauge-N` | ✓ | +0.69 | err 6.3% on °C |
| 225 | `read-gauge-N` | ✓ | +0.70 | err 5.9% on V |
| 224 | `read-any-gauge` | ✗ | -0.10 | N err 11.8% (too high) |
| 223 | `find-door` | ✓ | +0.20 | close: 0.86m |
| 222 | `navigate-to-charge` | ✗ | -0.10 | far: 3.97 m |
| 221 | `count-obstacles` | ✗ | -0.20 | pred 6 vs 4 |
| 220 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'PSI' |
| 219 | `read-gauge-N` | ✗ | -0.20 | err 46.0%, units_ok=True |
| 218 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 217 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.9% |
| 216 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'degrees' |
| 215 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 214 | `read-gauge-N` | ✓ | +0.30 | marginal err 10.3% |
