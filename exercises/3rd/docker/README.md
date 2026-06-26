# Exercise 3 Docker Image

This directory contains the Dockerfile used to build the reproducible Sniper
8.0 image for Exercise 3.

## Image

- Local image tag: `advca-sniper:8.0`.
- Base image: `snipersim/snipersim`, pinned by digest in `Dockerfile`.
- Added helper: `advcomparch_mcpat.py`, copied into Sniper's tools directory.

The image keeps Sniper itself unchanged except for permission compatibility
needed to run the container as the host WSL user.

## Workflow

Use the controller script from the repository root:

```bash
./exercises/3rd/scripts/run_sniper_docker.sh pull
./exercises/3rd/scripts/run_sniper_docker.sh build-image
./exercises/3rd/scripts/run_sniper_docker.sh check
./exercises/3rd/scripts/run_sniper_docker.sh smoke
```

On WSL, the CentOS 6 based Sniper image may require
`kernelCommandLine=vsyscall=emulate` in `%UserProfile%\.wslconfig`.
