# Live Progress

**Last updated**: 2026-04-21 21:52:16  

**Total episodes**: 276  

**Success rate (last 30)**: 47%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 18/18 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/23 | 83% | +0.61 |
| `find-door` | 13/18 | 72% | +0.12 |
| `read-gauge-N` | 43/95 | 45% | +0.15 |
| `navigate-to-charge` | 10/27 | 37% | +0.14 |
| `read-any-gauge` | 18/62 | 29% | +0.11 |
| `navigate-home` | 6/31 | 19% | -0.27 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 276 | `read-gauge-N` | ✓ | +0.30 | marginal err 11.1% |
| 275 | `find-door` | ✓ | +0.20 | close: 1.03m |
| 274 | `navigate-to-charge` | ✗ | -0.10 | far: 4.20 m |
| 273 | `read-gauge-N` | ✓ | +0.69 | err 6.3% on PSI |
| 272 | `navigate-home` | ✓ | +0.30 | close: 1.34m |
| 271 | `read-gauge-N` | ✗ | -0.20 | err 16.1%, units_ok=True |
| 270 | `read-gauge-N` | ✗ | -0.20 | err 18.6%, units_ok=False |
| 269 | `read-any-gauge` | ✗ | -0.10 | E err 21.1% (too high) |
| 268 | `read-any-gauge` | ✗ | -0.10 | N err 25.5% (too high) |
| 267 | `read-gauge-N` | ✗ | -0.20 | err 36.7%, units_ok=True |
| 266 | `read-any-gauge` | ✓ | +0.69 | E err 4.7% |
| 265 | `navigate-to-charge` | ✗ | -0.10 | far: 11.85 m |
| 264 | `find-door` | ✓ | +0.59 | door dist 0.82m bearing +9° |
| 263 | `navigate-to-charge` | ✓ | +0.20 | marginally close: 0.97 m |
| 262 | `read-gauge-N` | ✓ | +0.98 | err 0.4% on BAR |
