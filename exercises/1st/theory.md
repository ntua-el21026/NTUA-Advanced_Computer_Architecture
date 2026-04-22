# Assignment 1 Theory Notes

This file is a compact theory reference for the assignment. It is not final report prose; we update it paragraph by paragraph and use it to keep the report explanations consistent.

## General Context

Modern processors use pipelining and speculation to keep many instructions in flight. Branches create control hazards because the frontend must know both whether control flow changes and where to fetch next. Branch prediction reduces stalls by guessing this early.

There are two related prediction problems:

- Direction prediction: will the branch be `Taken` or `Not Taken`?
- Target prediction: if it is taken, what is the next PC?

Example:

```text
104: beq r1, r0, 200
108: next sequential instruction
200: branch target
```

Direction prediction decides between continuing at `108` and jumping. Target prediction supplies `200` if the branch is predicted taken.

## Basic Terms

- `PC` / `IP`: address of the current instruction.
- `Taken`: the branch redirects control flow to its target.
- `Not Taken`: execution continues sequentially.
- `Target`: destination address of a taken branch.
- `Conditional branch`: branch whose outcome depends on a condition.
- `Unconditional branch`: branch that always redirects control flow.
- `Call`: control transfer to a procedure; usually paired with a return.
- `Return`: jumps back to the instruction after the matching call.
- `Dynamic instruction`: one executed instance of an instruction. A single static loop branch can execute many times dynamically.

## PIN And Pintools

Intel PIN is dynamic binary instrumentation. The provided pintools insert callbacks into the running benchmark and use those callbacks to count instructions, classify branches, and simulate predictor state.

- `cslab_branch_stats.cpp`: branch-category statistics.
- `cslab_branch.cpp`: direction predictors, BTBs, and RAS simulations.
- `speccmds.cmd`: benchmark command line for each SPEC input directory.

## 5.1 Metrics And Averages

For sections 5.3-5.6, the assignment uses `train` inputs. Section 5.2 separately asks for both `train` and `ref`.

The main direction-prediction metric is:

```text
directionMPKI = direction_mispredictions / total_instructions * 1000
```

Example:

```text
6,000 direction misses / 2,000,000 instructions * 1000 = 3.0 MPKI
```

MPKI normalizes misses by program length. For summaries we keep two averages:

- Arithmetic mean MPKI: each benchmark has equal weight.
- Aggregate MPKI: `sum(misses) / sum(instructions) * 1000`, so each dynamic instruction has equal weight.

Example:

```text
A: 1,000 instructions, 10 misses -> 10 MPKI
B: 9,000 instructions, 18 misses -> 2 MPKI

arithmetic mean = 6 MPKI
aggregate       = 2.8 MPKI
```

The geometric-mean discussion from the paper is mainly relevant to speedup-like ratios. For MPKI, arithmetic and aggregate summaries are easier to interpret physically.

## 5.2 Branch Instruction Analysis

Section 5.2 measures the dynamic branch mix, not predictor quality yet. We record:

- total instructions,
- total branches,
- conditional taken / not-taken branches,
- unconditional branches,
- calls,
- returns.

The category percentages explain what kind of control flow each benchmark stresses. Many conditional branches stress direction predictors. Many calls and returns make target prediction and RAS behavior more important.

Branch frequency is:

```text
total_branches / total_instructions * 100
```

If branch frequency is `20%`, roughly one in five executed instructions is a branch, so poor prediction can frequently disrupt instruction fetch.

## 5.3 N-bit Predictors

Section 5.3 studies direction predictors based on a Branch History Table (BHT). A BHT is an array indexed by the branch PC. Each entry stores state about past branch outcomes.

Aliasing occurs when different branch PCs map to the same BHT entry. If those branches behave differently, they overwrite each other's state and reduce accuracy.

Example:

```text
BHT entries = 4, index = PC mod 4
PC 100 -> index 0
PC 104 -> index 0
```

Both branches share one entry.

### N-bit Saturating Counters

An n-bit predictor stores one saturating counter per BHT entry:

```text
min = 0
max = 2^n - 1
taken     -> increment unless already max
not taken -> decrement unless already 0
```

The most significant bit gives the prediction:

```text
MSB = 0 -> Not Taken
MSB = 1 -> Taken
```

Classic 2-bit counter:

```text
0: strongly not taken
1: weakly not taken
2: weakly taken
3: strongly taken
```

The point of 2-bit hysteresis is that one unusual outcome does not immediately flip a strong prediction. This is especially useful for loops, whose branch pattern is often:

```text
T T T T N
```

A 1-bit predictor often misses at loop exit and again at the next loop start. A 2-bit predictor usually misses at loop exit but often keeps predicting taken for the next start.

### 5.3(i): Fixed 16K BHT Entries

Here the number of entries is fixed at 16K and `N=1,2,3,4` changes the bits per entry. More bits increase hysteresis but also hardware cost. Past 2 bits, extra hysteresis may give little benefit or may adapt too slowly.

The final choice should be based on measured MPKI and whether the improvement justifies the extra storage.

### 5.3(ii): Nair 2-bit FSMs

Nair's paper studies alternative 4-state finite state machines (FSMs) for 2-bit prediction. A 2-bit FSM has four states:

```text
A, B, C, D
```

Each state has a prediction and two transitions: one for actual not-taken and one for actual taken.

Encoding example:

```text
BCBAADCD:3
```

The 8 letters are grouped by state:

```text
A: BC
B: BA
C: AD
D: CD
```

For each pair, the first letter is the next state after `Not Taken`, and the second is the next state after `Taken`.

The number after `:` is the output mask in `A B C D` order:

```text
3 = 0011 -> A,B predict Not Taken; C,D predict Taken
```

So for state `C` in `BCBAADCD:3`, prediction is taken; actual taken moves to `D`, actual not-taken moves to `A`.

The first Table VI FSM, `ABACBDCD:3`, is the standard 2-bit saturating counter. The other FSMs have the same storage cost but different transition behavior, so we compare them experimentally.

### 5.3(iii): Fixed 32K-bit Hardware

Now total storage is fixed at 32K bits. This creates a direct tradeoff:

```text
1-bit predictor -> 32K entries
2-bit predictor -> 16K entries
4-bit predictor -> 8K entries
```

More entries reduce aliasing. More bits per entry improve hysteresis. The best predictor depends on whether the benchmark behavior is limited more by aliasing or by insufficient counter stability.

The scripts should not decide the winner automatically; the report should justify the final choice using MPKI and plots.

## 5.4 BTB Study

The Branch Target Buffer (BTB) is a small cache-like structure accessed during instruction fetch. From the lecture, a BTB conceptually stores:

```text
{ branch instruction address, branch type, predicted target address }
```

For our implementation, the essential information is the branch PC, stored target, valid bit, and replacement metadata.

Simple BTB behavior:

```text
BTB hit  -> predict Taken and fetch from stored target
BTB miss -> predict Not Taken and continue sequentially
```

Example:

```text
BTB entry: PC 0x400104 -> target 0x400200
fetch PC 0x400104 -> hit -> predict taken to 0x400200
```

### Direction Miss vs Target Miss

A direction miss means the taken/not-taken decision was wrong:

```text
BTB hit  -> predicted Taken, actual Not Taken
BTB miss -> predicted Not Taken, actual Taken
```

A target miss means the BTB correctly predicted taken, but the stored target was wrong:

```text
BTB hit, actual Taken, stored target != actual target
```

Example:

```text
stored: PC 0x400300 -> 0x500000
actual: PC 0x400300 -> 0x600000
```

The direction is correct because the branch was taken, but the target is wrong. This can happen for indirect branches or other branches with changing dynamic targets.

### Entries, Sets, And Associativity

A BTB is organized like a cache:

- entries: total number of branch records,
- sets: indexed groups,
- ways: slots per set,
- associativity: number of ways per set.

For total entries `E` and associativity `A`:

```text
sets = E / A
```

Examples:

```text
BTB-512-1 -> 512 entries, 1-way, 512 sets
BTB-512-2 -> 512 entries, 2-way, 256 sets
BTB-64-8  -> 64 entries, 8-way, 8 sets
```

More entries help capacity misses: the active branch working set is too large. More ways help conflict misses: several hot branches map to the same set.

For fixed total entries:

```text
more ways -> fewer sets
more sets -> fewer ways
```

So the best BTB organization is empirical. The report should compare direction misses, target misses, total miss MPKI, and hardware complexity before choosing.

### Replacement

When a set is full, we use LRU replacement: evict the least recently used entry in that set. LRU is a standard cache-like policy and fits the idea that recently used branch PCs are likely to be reused soon.

## 5.5 RAS Study

The Return Address Stack (RAS) predicts targets of return instructions. Returns are difficult for a normal BTB because the same static return instruction can have different dynamic targets depending on which call site invoked the function.

Example:

```c
void f() { return; }

void a() { f(); }  // f returns here
void b() { f(); }  // f returns here instead
```

The return instruction inside `f` is the same static instruction, but its correct target changes with the caller.

The lecture observation is that returns usually follow LIFO behavior:

```text
call   -> push address of the instruction after the call
return -> pop the most recent address and predict it as target
```

Nested-call example:

```text
main calls A -> push return_to_main
A calls B    -> push return_to_A
B returns    -> pop return_to_A
A returns    -> pop return_to_main
```

RAS size matters because deep or irregular call nesting can overflow the stack. If a RAS with 2 entries sees 3 nested calls, the oldest return address may be lost, causing a later return miss.

The main metric for 5.5 is:

```text
RAS miss rate = incorrect_returns / (correct_returns + incorrect_returns) * 100
```

We also keep RAS miss MPKI:

```text
RAS miss MPKI = incorrect_returns / total_instructions * 1000
```

The assignment asks us to compare 4, 8, 16, 32, 48, and 64 entries. The best choice is not necessarily the largest size. In the report, we should choose the smallest RAS size near the point where increasing entries gives little additional miss-rate reduction.

## 5.6.1 Perceptrons

A perceptron predictor is still a direction predictor, but instead of keeping a small saturating counter per branch, it learns correlations between the current branch and the recent global branch history.

For each dynamic conditional branch, the branch instruction PC selects one perceptron from a table:

```text
index = branch_PC % M
```

Here `M` is the number of perceptrons. The PC is the address of the branch instruction itself, not the branch target. Different branch PCs can map to the same perceptron, so larger `M` reduces aliasing.

Each perceptron stores `n + 1` weights:

```text
w0, w1, w2, ..., wn
```

`w0` is the bias. The other weights correspond to the last `n` global branch outcomes. Each history bit is encoded as:

```text
Taken     -> +1
Not Taken -> -1
```

The output is:

```text
y = w0 + x1*w1 + x2*w2 + ... + xn*wn
```

If `y >= 0`, the predictor chooses taken. If `y < 0`, it chooses not taken. The magnitude of `y` is the predictor's confidence.

Example with `n = 3`:

```text
history: T, N, T -> x = [+1, -1, +1]
weights: w0=1, w1=2, w2=3, w3=-1
y = 1 + 1*2 + (-1)*3 + 1*(-1) = -1
prediction: Not Taken
```

Training happens when the prediction is wrong or when the prediction is correct but weak:

```text
abs(y) <= theta
theta = floor(1.93 * n + 14)
```

For example, with `n = 8`, `theta = floor(29.44) = 29`.

The key tradeoff in 5.6.1 is:

- larger `M`: less aliasing between different static branches,
- larger `n`: longer history and more correlation information, but more weights per perceptron and potentially harder training.

The report should compare the 15 required `(M, n)` pairs using direction MPKI and choose based on measured behavior, not by assuming that the largest configuration is automatically best.
