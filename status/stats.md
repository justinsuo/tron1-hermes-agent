# Live Progress

**Last updated**: 2026-04-21 22:22:22  

**Total episodes**: 302  

**Success rate (last 30)**: 50%


## Per-task

| task | passes / total | success % | avg reward |
|---|---|---|---|
| `describe-scene` | 19/19 | 100% | +0.79 |
| `navigate-forward-2m` | 1/1 | 100% | +1.00 |
| `count-obstacles` | 21/25 | 84% | +0.61 |
| `find-door` | 13/18 | 72% | +0.12 |
| `read-gauge-N` | 50/111 | 45% | +0.14 |
| `navigate-to-charge` | 10/29 | 34% | +0.13 |
| `read-any-gauge` | 19/65 | 29% | +0.11 |
| `navigate-home` | 7/33 | 21% | -0.26 |
| `read-visible-gauge` | 0/1 | 0% | -0.20 |

## Last 15 episodes

| # | task | result | reward | reason |
|---|---|---|---|---|
| 302 | `read-gauge-N` | ✓ | +0.85 | err 3.1% on BAR |
| 301 | `describe-scene` | ✓ | +0.80 | 7 scene keywords matched |
| 300 | `navigate-to-charge` | ✗ | -0.10 | far: 5.46 m |
| 299 | `read-gauge-N` | ✗ | -0.20 | err 40.9%, units_ok=False |
| 298 | `read-gauge-N` | ✗ | -0.20 | err 24.5%, units_ok=False |
| 297 | `read-gauge-N` | ✓ | +0.30 | marginal err 11.4% |
| 296 | `read-gauge-N` | ✓ | +0.30 | marginal err 13.6% |
| 295 | `read-gauge-N` | ✓ | +0.30 | marginal err 11.3% |
| 294 | `count-obstacles` | ✓ | +1.00 | correct count = 4 |
| 293 | `read-any-gauge` | ✓ | +0.42 | N err 8.7% |
| 292 | `read-gauge-N` | ✗ | -0.30 | no JSON reading in transcript |
| 291 | `read-gauge-N` | ✗ | -0.20 | err 23.0%, units_ok=True |
| 290 | `read-gauge-N` | ✗ | -0.20 | err 8.1%, units_ok=False |
| 289 | `read-gauge-N` | ✓ | +0.64 | err 7.2% on V |
| 288 | `read-gauge-N` | ✗ | -0.20 | err 8.6%, units_ok=False |
