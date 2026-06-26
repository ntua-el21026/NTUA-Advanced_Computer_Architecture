# Section 4.3 Results

This directory contains the replacement-policy comparison for Exercise 2.

## Contents

- `summary.csv`: per-benchmark results for each selected cache
  configuration/policy pair.
- `summary_by_policy.csv`: aggregate view grouped by replacement policy.
- `summary_by_config_policy.csv`: aggregate view grouped by configuration and
  policy.
- `summary_best_policy_by_config.csv`: best policy per selected cache
  configuration.
- `summary.txt`: human-readable summary.
- `logs/`: benchmark stdout/stderr logs.
- `times/`: timing information for each run.

## Regeneration

Run section 4.2 first, then from the repository root:

```bash
./exercises/2nd/scripts/run_4_3_replacement_policies.py
```
