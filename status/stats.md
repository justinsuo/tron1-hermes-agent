# Live Progress

**Last updated**: 2026-04-21 20:01:52  

**Total episodes**: 175  

**Success rate (last 30)**: 40%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 12/12 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 17/20 | 85% | +0.65 |
| `find-door` | 9/14 | 64% | +0.07 |
| `navigate-to-charge` | 9/19 | 47% | +0.23 |
| `read-gauge-N` | 23/54 | 43% | +0.12 |
| `read-any-gauge` | 13/39 | 33% | +0.15 |
| `navigate-home` | 2/15 | 13% | -0.29 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 175 | `read-any-gauge` | ✗ | -0.10 | E err 52.7% (too high) |
| 174 | `read-gauge-N` | ✗ | -0.20 | err 23.1%, units_ok=True |
| 173 | `navigate-home` | ✓ | +0.30 | close: 1.34m |
| 172 | `find-door` | ✓ | +0.20 | close: 0.29m |
| 171 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 170 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 169 | `navigate-home` | ✗ | -0.10 | far from home: 6.89m |
| 168 | `find-door` | ✓ | +0.20 | close: 1.50m |
| 167 | `read-any-gauge` | ✗ | -0.20 | no gauge matches units 'unspecified' |
| 166 | `read-gauge-N` | ✓ | +0.30 | marginal err 14.9% |
| 165 | `read-any-gauge` | ✓ | +0.98 | N err 0.3% |
| 164 | `find-door` | ✓ | +0.20 | close: 1.23m |
| 163 | `read-any-gauge` | ✓ | +0.79 | N err 3.1% |
| 162 | `count-obstacles` | ✗ | -0.20 | pred 7 vs 4 |
| 161 | `read-gauge-N` | ✗ | -0.20 | err 18.5%, units_ok=True |
