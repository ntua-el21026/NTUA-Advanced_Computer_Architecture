# Automation Scripts

This directory contains Python automation for running the second assignment experiments and summarizing results.

## Scripts

- `run_4_2_l2_sweep.py`: section 4.2 L2 size/associativity/block-size sweep with LRU replacement.
- `run_4_3_replacement_policies.py`: section 4.3 replacement-policy comparison over the best 4.2 L2 configuration for each capacity.

Run scripts from the repository root so relative paths resolve consistently:

```bash
./exercises/2nd/scripts/run_4_2_l2_sweep.py
```

After 4.2 finishes, run:

```bash
./exercises/2nd/scripts/run_4_3_replacement_policies.py
```

Both scripts use `taskset` to pin worker processes to cores `0-7` by default. They run benchmarks from temporary scratch copies by default so command redirections do not modify tracked SPEC payload files.
