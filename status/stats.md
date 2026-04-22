# Live Progress

**Last updated**: 2026-04-21 21:32:11  

**Total episodes**: 257  

**Success rate (last 30)**: 37%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 18/18 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/23 | 83% | +0.61 |
| `find-door` | 11/16 | 69% | +0.09 |
| `read-gauge-N` | 40/89 | 45% | +0.14 |
| `navigate-to-charge` | 9/24 | 38% | +0.16 |
| `read-any-gauge` | 17/57 | 30% | +0.11 |
| `navigate-home` | 4/28 | 14% | -0.32 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 257 | `describe-scene` | ✓ | +0.80 | 9 scene keywords matched |
| 256 | `read-gauge-N` | ✓ | +0.92 | err 1.5% on °C |
| 255 | `describe-scene` | ✓ | +0.80 | 7 scene keywords matched |
| 254 | `read-gauge-N` | ✗ | -0.20 | err 22.4%, units_ok=True |
| 253 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 252 | `read-gauge-N` | ✗ | -0.20 | err 32.1%, units_ok=True |
| 251 | `navigate-home` | ✓ | +0.51 | home dist 0.49m |
| 250 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 249 | `read-gauge-N` | ✗ | -0.20 | err 26.3%, units_ok=True |
| 248 | `read-any-gauge` | ✗ | -0.10 | E err 55.2% (too high) |
| 247 | `describe-scene` | ✓ | +0.80 | 7 scene keywords matched |
| 246 | `read-any-gauge` | ✓ | +0.82 | E err 2.7% |
| 245 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.1% |
| 244 | `read-gauge-N` | ✗ | -0.20 | err 18.3%, units_ok=True |
| 243 | `read-gauge-N` | ✓ | +0.30 | marginal err 14.9% |
