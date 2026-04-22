# Live Progress

**Last updated**: 2026-04-21 22:12:20  

**Total episodes**: 293  

**Success rate (last 30)**: 40%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 18/18 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 20/24 | 83% | +0.60 |
| `find-door` | 13/18 | 72% | +0.12 |
| `read-gauge-N` | 46/105 | 44% | +0.14 |
| `navigate-to-charge` | 10/28 | 36% | +0.13 |
| `read-any-gauge` | 19/65 | 29% | +0.11 |
| `navigate-home` | 7/33 | 21% | -0.26 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 293 | `read-any-gauge` | ✓ | +0.42 | N err 8.7% |
| 292 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 291 | `read-gauge-N` | ✗ | -0.20 | err 23.0%, units_ok=True |
| 290 | `read-gauge-N` | ✗ | -0.20 | err 8.1%, units_ok=False |
| 289 | `read-gauge-N` | ✓ | +0.64 | err 7.2% on V |
| 288 | `read-gauge-N` | ✗ | -0.20 | err 8.6%, units_ok=False |
| 287 | `count-obstacles` | ✓ | +0.30 | pred 3 vs 4 (close) |
| 286 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 285 | `read-gauge-N` | ✓ | +0.64 | err 7.3% on BAR |
| 284 | `navigate-to-charge` | ✗ | -0.10 | far: 11.89 m |
| 283 | `navigate-home` | ✓ | +0.30 | close: 0.69m |
| 282 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 281 | `read-any-gauge` | ✗ | -0.10 | N err 25.6% (too high) |
| 280 | `read-any-gauge` | ✗ | -0.10 | N err 12.6% (too high) |
| 279 | `read-gauge-N` | ✗ | -0.20 | err 15.2%, units_ok=True |
