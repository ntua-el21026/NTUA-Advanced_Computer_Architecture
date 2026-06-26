# Exercise 2 Pintool

This directory contains the cache simulator pintool for Exercise 2.

## Main Files

- `simulator.cpp`: PIN instrumentation, command-line options, and reporting.
- `cache.h`: cache hierarchy, statistics, and replacement-policy behavior.
- `globals.h`: shared types and global configuration.
- `makefile` and `makefile.rules`: PIN build integration.

## Build

From this directory:

```bash
make
```

The produced object files are generated under `obj-*` directories and are
ignored by Git.
