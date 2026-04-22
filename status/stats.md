# Live Progress

**Last updated**: 2026-04-21 21:42:14  

**Total episodes**: 266  

**Success rate (last 30)**: 50%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 18/18 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/23 | 83% | +0.61 |
| `find-door` | 12/17 | 71% | +0.12 |
| `read-gauge-N` | 41/90 | 46% | +0.15 |
| `navigate-to-charge` | 10/26 | 38% | +0.15 |
| `read-any-gauge` | 18/60 | 30% | +0.12 |
| `navigate-home` | 5/30 | 17% | -0.29 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 266 | `read-any-gauge` | ✓ | +0.69 | E err 4.7% |
| 265 | `navigate-to-charge` | ✗ | -0.10 | far: 11.85 m |
| 264 | `find-door` | ✓ | +0.59 | door dist 0.82m bearing +9° |
| 263 | `navigate-to-charge` | ✓ | +0.20 | marginally close: 0.97 m |
| 262 | `read-gauge-N` | ✓ | +0.98 | err 0.4% on BAR |
| 261 | `read-any-gauge` | ✗ | -0.10 | E err 71.1% (too high) |
| 260 | `read-any-gauge` | ✗ | -0.10 | E err 11.9% (too high) |
| 259 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 258 | `navigate-home` | ✓ | +0.90 | home dist 0.10m |
| 257 | `describe-scene` | ✓ | +0.80 | 9 scene keywords matched |
| 256 | `read-gauge-N` | ✓ | +0.92 | err 1.5% on °C |
| 255 | `describe-scene` | ✓ | +0.80 | 7 scene keywords matched |
| 254 | `read-gauge-N` | ✗ | -0.20 | err 22.4%, units_ok=True |
| 253 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 252 | `read-gauge-N` | ✗ | -0.20 | err 32.1%, units_ok=True |
