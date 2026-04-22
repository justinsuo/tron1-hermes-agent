# Live Progress

**Last updated**: 2026-04-21 20:52:02  

**Total episodes**: 217  

**Success rate (last 30)**: 43%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 14/14 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/22 | 86% | +0.65 |
| `find-door` | 10/15 | 67% | +0.08 |
| `read-gauge-N` | 33/70 | 47% | +0.16 |
| `navigate-to-charge` | 9/21 | 43% | +0.20 |
| `read-any-gauge` | 15/49 | 31% | +0.12 |
| `navigate-home` | 3/24 | 12% | -0.34 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 217 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.9% |
| 216 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'degrees' |
| 215 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 214 | `read-gauge-N` | ✓ | +0.30 | marginal err 10.3% |
| 213 | `navigate-to-charge` | ✗ | -0.10 | far: 1.63 m |
| 212 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 211 | `read-gauge-N` | ✗ | -0.20 | err 25.7%, units_ok=True |
| 210 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 209 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 208 | `read-gauge-N` | ✗ | -0.20 | err 24.3%, units_ok=True |
| 207 | `read-gauge-N` | ✓ | +0.86 | err 2.7% on °C |
| 206 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 205 | `navigate-home` | ✓ | +0.30 | close: 0.51m |
| 204 | `read-any-gauge` | ✓ | +0.80 | N err 2.9% |
| 203 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'HOUR' |
