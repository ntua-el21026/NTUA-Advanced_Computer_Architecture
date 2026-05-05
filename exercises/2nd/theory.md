# Assignment 2 Theory Notes

This file is a compact theory reference for the second assignment. It is not final report prose; we update it paragraph by paragraph and use it to keep the report explanations consistent.

## General Context

The assignment studies how memory hierarchy parameters affect application performance. The simulator models an in-order processor with a two-level inclusive data-cache hierarchy:

```text
CPU -> L1 Data Cache -> L2 Cache -> Main Memory
```

The model is intentionally simple:

```text
Cycles = Instructions
       + L1_Accesses * L1_hit_cycles
       + L2_Accesses * L2_hit_cycles
       + Mem_Accesses * Mem_acc_cycles
```

For this assignment:

```text
L1 hit latency      = 1 cycle
L2 hit latency      = 10 cycles
Main memory latency = 200 cycles
```

The simulator counts dynamic instructions and memory accesses with PIN. Each instruction contributes one base cycle. Loads and stores add memory-hierarchy cycles depending on where the requested cache block is found.

## Locality And Cache Parameters

Caches exploit two forms of locality:

- Temporal locality: recently used data is likely to be reused soon.
- Spatial locality: data near recently used data is likely to be used soon.

The main cache design parameters in section 4.2 are:

- Cache size: total capacity. Larger caches can reduce capacity misses, but cost more area and access energy.
- Associativity: number of candidate lines per set. Higher associativity can reduce conflict misses, but can make lookup and replacement more expensive.
- Block size: number of bytes moved per cache line. Larger blocks exploit spatial locality, but can waste bandwidth and capacity if neighboring data is not reused.

The optimal choice is workload-dependent. A streaming benchmark can benefit from larger blocks, while a benchmark with poor spatial locality can suffer from them. A benchmark with many hot addresses mapping to the same sets can benefit from higher associativity, while a benchmark dominated by capacity misses may benefit more from a larger L2.

## Metrics

The primary performance metric is IPC:

```text
IPC = Total Instructions / Total Cycles
```

Higher IPC is better because the instruction count is fixed for a given benchmark and input. In this model, IPC decreases when memory stalls add cycles.

Miss rates explain why IPC changes:

```text
L1 miss rate = L1 misses / L1 accesses
L2 miss rate = L2 misses / L2 accesses
```

MPKI normalizes misses by instruction count:

```text
L1 MPKI = L1 misses / total instructions * 1000
L2 MPKI = L2 misses / total instructions * 1000
```

L2 misses are also main-memory accesses in this simulator, so L2 MPKI is a direct indicator of expensive 200-cycle accesses.

## Section 4.2 L2 Study

Section 4.2 keeps the L1 fixed:

```text
L1 size          = 32 KB
L1 associativity = 4
L1 block size    = 32 B
```

Only L2 size, associativity, and block size change. The required L2 design space is:

```text
L2 size 256 KB:  associativity 4
L2 size 512 KB:  associativity 4, 8, 16
L2 size 1024 KB: associativity 8, 16
L2 size 2048 KB: associativity 16
Block sizes for every row: 64 B, 128 B, 256 B
```

This gives 21 L2 configurations. With 7 benchmarks, section 4.2 requires 147 simulations.

The report should answer two questions:

1. Which parameter has the largest performance impact?
2. For each L2 capacity, which cache configuration is the best choice?

The first answer should compare trends across size, associativity, and block size. The second answer should be capacity-specific, because the assignment asks for the best cache within each capacity group.
