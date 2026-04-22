# Live Progress

**Last updated**: 2026-04-21 20:11:54  

**Total episodes**: 185  

**Success rate (last 30)**: 43%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 13/13 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 18/21 | 86% | +0.63 |
| `find-door` | 9/14 | 64% | +0.07 |
| `navigate-to-charge` | 9/19 | 47% | +0.23 |
| `read-gauge-N` | 25/57 | 44% | +0.13 |
| `read-any-gauge` | 13/43 | 30% | +0.12 |
| `navigate-home` | 2/16 | 12% | -0.31 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 185 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'bars' |
| 184 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 183 | `read-any-gauge` | ✗ | -0.10 | N err 14.7% (too high) |
| 182 | `read-gauge-N` | ✓ | +0.30 | marginal err 12.1% |
| 181 | `describe-scene` | ✓ | +0.80 | 6 scene keywords matched |
| 180 | `read-gauge-N` | ✗ | -0.20 | err 15.1%, units_ok=True |
| 179 | `read-any-gauge` | ✗ | -0.30 | no JSON reading |
| 178 | `count-obstacles` | ✓ | +0.30 | pred 5 vs 4 (close) |
| 177 | `read-any-gauge` | ✗ | -0.10 | N err 22.1% (too high) |
| 176 | `read-gauge-N` | ✓ | +0.63 | err 7.5% on PSI |
| 175 | `read-any-gauge` | ✗ | -0.10 | E err 52.7% (too high) |
| 174 | `read-gauge-N` | ✗ | -0.20 | err 23.1%, units_ok=True |
| 173 | `navigate-home` | ✓ | +0.30 | close: 1.34m |
| 172 | `find-door` | ✓ | +0.20 | close: 0.29m |
| 171 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
