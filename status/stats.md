# Live Progress

**Last updated**: 2026-04-21 23:02:29  

**Total episodes**: 342  

**Success rate (last 30)**: 40%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 21/21 | 100% | +0.80 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 24/28 | 86% | +0.60 |
| `find-door` | 14/19 | 74% | +0.13 |
| `read-gauge-N` | 57/123 | 46% | +0.17 |
| `navigate-to-charge` | 10/34 | 29% | +0.09 |
| `read-any-gauge` | 22/78 | 28% | +0.10 |
| `navigate-home` | 8/37 | 22% | -0.26 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 342 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 341 | `read-any-gauge` | ✗ | -0.10 | E err 15.7% (too high) |
| 340 | `read-any-gauge` | ✓ | +0.87 | N err 1.9% |
| 339 | `read-gauge-N` | ✓ | +1.00 | err 0.0% on V |
| 338 | `read-gauge-N` | ✓ | +0.93 | err 1.4% on PSI |
| 337 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 336 | `read-gauge-N` | ✗ | -0.20 | err 20.6%, units_ok=True |
| 335 | `read-any-gauge` | ✗ | -0.10 | N err 19.3% (too high) |
| 334 | `read-gauge-N` | ✗ | -0.20 | err 9.1%, units_ok=False |
| 333 | `read-gauge-N` | ✗ | -0.20 | err 15.5%, units_ok=False |
| 332 | `read-gauge-N` | ✓ | +0.76 | err 4.9% on V |
| 331 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 330 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 329 | `count-obstacles` | ✓ | +0.30 | pred 3 vs 4 (close) |
| 328 | `navigate-to-charge` | ✗ | -0.10 | far: 6.66 m |
