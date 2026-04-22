# Live Progress

**Last updated**: 2026-04-21 20:21:56  

**Total episodes**: 193  

**Success rate (last 30)**: 47%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 13/13 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 18/21 | 86% | +0.63 |
| `find-door` | 10/15 | 67% | +0.08 |
| `navigate-to-charge` | 9/19 | 47% | +0.23 |
| `read-gauge-N` | 27/61 | 44% | +0.12 |
| `read-any-gauge` | 13/45 | 29% | +0.11 |
| `navigate-home` | 2/17 | 12% | -0.32 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 193 | `read-any-gauge` | ✗ | -0.10 | N err 10.3% (too high) |
| 192 | `read-gauge-N` | ✗ | -0.20 | err 23.4%, units_ok=True |
| 191 | `read-gauge-N` | ✓ | +0.30 | marginal err 9.2% |
| 190 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 189 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 188 | `find-door` | ✓ | +0.20 | close: 0.97m |
| 187 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.2% |
| 186 | `read-any-gauge` | ✗ | -0.10 | E err 10.8% (too high) |
| 185 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'bars' |
| 184 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 183 | `read-any-gauge` | ✗ | -0.10 | N err 14.7% (too high) |
| 182 | `read-gauge-N` | ✓ | +0.30 | marginal err 12.1% |
| 181 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 180 | `read-gauge-N` | ✗ | -0.20 | err 15.1%, units_ok=True |
| 179 | `read-any-gauge` | ✗ | -0.30 | no JSON reading |
