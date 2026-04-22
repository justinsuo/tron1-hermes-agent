# Live Progress

**Last updated**: 2026-04-21 20:31:58  

**Total episodes**: 201  

**Success rate (last 30)**: 43%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 13/13 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 19/22 | 86% | +0.65 |
| `find-door` | 10/15 | 67% | +0.08 |
| `read-gauge-N` | 30/65 | 46% | +0.15 |
| `navigate-to-charge` | 9/20 | 45% | +0.21 |
| `read-any-gauge` | 13/45 | 29% | +0.11 |
| `navigate-home` | 2/19 | 11% | -0.34 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 201 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 200 | `read-gauge-N` | ✓ | +1.00 | err 0.0% on V |
| 199 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 198 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 197 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 196 | `read-gauge-N` | ✓ | +0.96 | err 0.7% on V |
| 195 | `navigate-to-charge` | ✗ | -0.10 | far: 5.57 m |
| 194 | `read-gauge-N` | ✓ | +0.63 | err 7.3% on BAR |
| 193 | `read-any-gauge` | ✗ | -0.10 | N err 10.3% (too high) |
| 192 | `read-gauge-N` | ✗ | -0.20 | err 23.4%, units_ok=True |
| 191 | `read-gauge-N` | ✓ | +0.30 | marginal err 9.2% |
| 190 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 189 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 188 | `find-door` | ✓ | +0.20 | close: 0.97m |
| 187 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.2% |
