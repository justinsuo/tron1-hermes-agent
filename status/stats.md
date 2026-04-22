# Live Progress

**Last updated**: 2026-04-21 21:12:07  

**Total episodes**: 238  

**Success rate (last 30)**: 27%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 15/15 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/23 | 83% | +0.61 |
| `find-door` | 11/16 | 69% | +0.09 |
| `read-gauge-N` | 37/79 | 47% | +0.16 |
| `navigate-to-charge` | 9/24 | 38% | +0.16 |
| `read-any-gauge` | 15/54 | 28% | +0.09 |
| `navigate-home` | 3/25 | 12% | -0.34 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 238 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 237 | `navigate-to-charge` | ✗ | -0.10 | far: 3.59 m |
| 236 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'PSI' |
| 235 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'PSI' |
| 234 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'bars' |
| 233 | `read-gauge-N` | ✗ | -0.20 | err 29.1%, units_ok=True |
| 232 | `read-gauge-N` | ✓ | +0.30 | marginal err 12.8% |
| 231 | `read-gauge-N` | ✗ | -0.20 | err 10.8%, units_ok=False |
| 230 | `read-gauge-N` | ✗ | -0.20 | err 16.7%, units_ok=True |
| 229 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 228 | `navigate-to-charge` | ✗ | -0.10 | far: 7.26 m |
| 227 | `read-gauge-N` | ✓ | +1.00 | err 0.0% on BAR |
| 226 | `read-gauge-N` | ✓ | +0.69 | err 6.3% on °C |
| 225 | `read-gauge-N` | ✓ | +0.70 | err 5.9% on V |
| 224 | `read-any-gauge` | ✗ | -0.10 | N err 11.8% (too high) |
