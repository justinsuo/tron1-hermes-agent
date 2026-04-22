# Live Progress

**Last updated**: 2026-04-21 20:42:00  

**Total episodes**: 210  

**Success rate (last 30)**: 47%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 14/14 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/22 | 86% | +0.65 |
| `find-door` | 10/15 | 67% | +0.08 |
| `read-gauge-N` | 31/67 | 46% | +0.16 |
| `navigate-to-charge` | 9/20 | 45% | +0.21 |
| `read-any-gauge` | 15/48 | 31% | +0.13 |
| `navigate-home` | 3/22 | 14% | -0.32 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 210 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 209 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 208 | `read-gauge-N` | ✗ | -0.20 | err 24.3%, units_ok=True |
| 207 | `read-gauge-N` | ✓ | +0.86 | err 2.7% on °C |
| 206 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 205 | `navigate-home` | ✓ | +0.30 | close: 0.51m |
| 204 | `read-any-gauge` | ✓ | +0.80 | N err 2.9% |
| 203 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'HOUR' |
| 202 | `read-any-gauge` | ✓ | +0.61 | N err 5.8% |
| 201 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 200 | `read-gauge-N` | ✓ | +1.00 | err 0.0% on V |
| 199 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 198 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 197 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 196 | `read-gauge-N` | ✓ | +0.96 | err 0.7% on V |
