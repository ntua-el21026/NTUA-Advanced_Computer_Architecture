# Exercise 3 Automation

The runners in this directory execute and summarize the synchronization
experiments required by Assignment 3.

## Scripts

- `run_4_1_sniper_scalability.py`: 75 Sniper runs covering five lock
  implementations, thread counts `1,2,4,8,16`, and grain sizes `1,10,100`.
- `run_4_1_real_scalability.py`: repeated real-machine runs using one logical
  CPU representative from each physical core.
- `run_4_2_topologies.py`: 15 Sniper runs covering the three four-core cache
  sharing topologies.
- `exercise3_common.py`: shared parsing, command construction, McPAT, and CSV
  helpers.
- `run_sniper_docker.sh`: Docker controller for pulling, building, checking,
  smoke-testing, and running Sniper matrices.
- `sniper_docker_exec.sh` and `mcpat_docker_exec.sh`: low-level container
  wrappers used by the controller and Python runners.

## Real-machine runs

Run the target-laptop preflight first:

```bash
./exercises/3rd/scripts/preflight_16core.py
```

It expects 16 physical and 24 logical CPUs, validates Git LFS and Docker, and
prints the physical-core representatives selected for affinity.

Inspect the physical-core mapping first:

```bash
./exercises/3rd/scripts/run_4_1_real_scalability.py --list-cpus
```

The runner groups logical CPUs by `(socket, core)` using `lscpu`, chooses one
representative per physical core, and passes the selected mapping to the
program through `LOCKS_CPU_LIST`. SMT-capable cores are ordered first, which is
important on a 16-physical/24-logical hybrid processor.

Run a small smoke test:

```bash
./exercises/3rd/scripts/run_4_1_real_scalability.py \
  --thread-counts 1,2,4 \
  --implementations tas_cas,ttas_cas,mutex \
  --grain-sizes 1 \
  --iterations 10000 \
  --repeats 2
```

Run the full matrix after calibrating `--iterations` so a one-thread run lasts
several seconds:

```bash
./exercises/3rd/scripts/run_4_1_real_scalability.py \
  --iterations <calibrated-iterations> \
  --repeats 5 \
  --warmups 1
```

Outputs are stored under `benchmarks/4.1/real/`. `machine.json` records the
CPU topology and the exact representative mapping.

## Sniper Docker compatibility

The assignment's `snipersim/snipersim:latest` image is Sniper 8.0 but uses
CentOS 6.10. Modern WSL kernels may start its shell with exit status 139 because
CentOS 6 requires legacy `vsyscall` emulation.

On Windows, create or update `%UserProfile%\.wslconfig`:

```ini
[wsl2]
kernelCommandLine=vsyscall=emulate
```

Then restart WSL and Docker Desktop from PowerShell:

```powershell
wsl --shutdown
```

After Docker Desktop restarts, verify:

```bash
docker run --rm --entrypoint /bin/bash \
  snipersim/snipersim:latest -lc 'echo PASS'
```

The repository pins the tested image digest in `exercises/3rd/docker/Dockerfile`
and adds the assignment's McPAT helper without modifying Sniper itself.

## Sniper runs

Build the reproducible local image:

```bash
./exercises/3rd/scripts/run_sniper_docker.sh pull
./exercises/3rd/scripts/run_sniper_docker.sh build-image
./exercises/3rd/scripts/run_sniper_docker.sh check
```

Run one complete Sniper smoke simulation:

```bash
./exercises/3rd/scripts/run_sniper_docker.sh smoke
```

The McPAT runner passes `--no-graph`; report diagrams are generated separately,
so the obsolete container does not need an additional `gnuplot` installation.

Inspect the generated simulation matrices without executing:

```bash
./exercises/3rd/scripts/run_4_1_sniper_scalability.py --dry-run --limit 5
./exercises/3rd/scripts/run_4_2_topologies.py --dry-run --limit 5
```

Execute the full experiments:

```bash
./exercises/3rd/scripts/run_sniper_docker.sh run-4.1
./exercises/3rd/scripts/run_sniper_docker.sh run-4.2
```

Each simulation runs in a disposable container while the Python orchestrator
runs on the WSL host. This avoids requiring Python 3 inside the CentOS 6 image.
Sniper result directories preserve `sim.out`, `sim.cfg`, `sim.info`,
`sim.stats.sqlite3`, command logs, and McPAT outputs.

Common options include:

```text
--dry-run
--force
--summarize-only
--implementations
--limit
--timeout
```

## Diagrams

After the Sniper and real-machine summaries exist, generate report figures with:

```bash
python3 exercises/3rd/benchmarks/diagrams/make_diagrams.py
```
