# Live Progress

**Last updated**: 2026-04-21 19:41:49  

**Total episodes**: 158  

**Success rate (last 30)**: 27%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 12/12 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 16/18 | 89% | +0.67 |
| `find-door` | 6/11 | 55% | +0.04 |
| `navigate-to-charge` | 9/19 | 47% | +0.23 |
| `read-gauge-N` | 21/49 | 43% | +0.13 |
| `read-any-gauge` | 11/34 | 32% | +0.13 |
| `navigate-home` | 1/13 | 8% | -0.35 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 158 | `read-gauge-N` | ✗ | -0.20 | err 21.5%, units_ok=True |
| 157 | `read-gauge-N` | ✗ | -0.20 | err 27.3%, units_ok=True |
| 156 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 155 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 154 | `read-any-gauge` | ✗ | -0.10 | E err 29.2% (too high) |
| 153 | `find-door` | ✓ | +0.20 | close: 0.10m |
| 152 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 151 | `read-gauge-N` | ✗ | -0.20 | err 9.6%, units_ok=False |
| 150 | `read-gauge-N` | ✗ | -0.20 | err 15.3%, units_ok=True |
| 149 | `read-gauge-N` | ✓ | +0.86 | err 2.8% on °C |
| 148 | `find-door` | ✓ | +0.20 | close: 1.12m |
| 147 | `read-gauge-N` | ✗ | -0.20 | err 23.3%, units_ok=True |
| 146 | `navigate-home` | ✗ | -0.50 | hermes timed out |
| 145 | `navigate-to-charge` | ✗ | -0.10 | far: 11.72 m |
| 144 | `read-gauge-N` | ✗ | -0.20 | err 36.3%, units_ok=True |
