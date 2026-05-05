# Automation Scripts

This directory contains Python automation for running the second assignment experiments and summarizing results.

## Scripts

- `run_4_2_l2_sweep.py`: section 4.2 L2 size/associativity/block-size sweep with LRU replacement.

Run scripts from the repository root so relative paths resolve consistently:

```bash
./exercises/2nd/scripts/run_4_2_l2_sweep.py
```

The section 4.2 script uses `taskset` to pin worker processes to cores `0-7` by default. It runs benchmarks from temporary scratch copies by default so command redirections do not modify tracked SPEC payload files.
