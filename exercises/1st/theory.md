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

## 5.6.2 Predictor Comparison

Section 5.6.2 is the final direction-predictor comparison. The goal is not to study one parameter in isolation, but to compare different prediction ideas under similar hardware budgets.

### Static Predictors

`AlwaysTaken` always predicts taken. It is a useful baseline because many loop branches are taken most of the time.

`BTFNT` means backward taken, forward not taken:

```text
target < branch_PC -> predict Taken
target > branch_PC -> predict Not Taken
```

Backward conditional branches often close loops, while forward branches often skip over code.

### Two-level Predictors

Two-level predictors use history plus a Pattern History Table (PHT). The PHT entries are usually 2-bit saturating counters.

Local-history predictors keep a separate recent-history value per branch:

```text
branch PC -> BHT entry -> local history -> PHT counter
```

This helps when one static branch has its own repeating pattern.

Global-history predictors keep one shared Branch History Register (BHR):

```text
last n branch outcomes -> BHR -> PHT counter
```

This helps when the outcome of one branch is correlated with earlier branches.

In our implementation, the shared PHT index uses PC bits XOR history bits. This is the usual gshare-style idea: it keeps history information but also spreads different branch PCs across the PHT to reduce aliasing.

### Hardware Calculations

For the assignment local-history predictors:

```text
PHT = 8192 entries * 2 bits = 16K bits
Total budget = 32K bits
BHT budget = 16K bits
BHT cost = X * Z
```

So:

```text
X=2048 -> Z=8
X=4096 -> Z=4
X=8192 -> Z=2
```

This trades longer per-branch history against more BHT entries.

For global-history predictors, the BHR cost is ignored:

```text
PHT entries * 2 bits = 32K bits
PHT entries = 16K
```

We compare BHR lengths `4`, `8`, and `12`.

For perceptrons, the approximate cost is:

```text
M * (n + 1) * weight_bits
weight_bits = 1 + floor(log2(theta))
theta = floor(1.93*n + 14)
```

The selected near-32K examples are:

```text
M=728, n=8   -> 32760 bits
M=141, n=32  -> 32571 bits
M=56,  n=72  -> 32704 bits
```

### Hybrid Predictors

Alpha 21264 is a classic hybrid idea: it combines local and global predictors with a choice predictor. The choice predictor learns which component is more reliable for the current branch/context.

In our implementation, `Alpha21264Predictor` uses the lecture-style organization:

```text
local history table: 1024 entries * 10 bits
local PHT:           1024 entries * 3 bits
global PHT:          4096 entries * 2 bits
choice PHT:          4096 entries * 2 bits
```

This is about 29K bits.

Tournament predictors use the same general idea:

```text
P0 predicts
P1 predicts
meta-predictor chooses P0 or P1
```

If `P0` and `P1` disagree, the meta-predictor is trained toward the component that was correct. The assignment allows us to ignore the meta-predictor overhead, so we size `P0` and `P1` at roughly 16K bits each.

The four implemented tournament predictors are:

```text
Tournament-M1024-Nbit16K1-Global8K-BHR8
  P0 = 1-bit 16K-entry predictor
  P1 = 8K-entry global-history predictor, BHR=8

Tournament-M1024-Local2048x4-Global8K-BHR8
  P0 = local-history predictor, BHT=2048 entries, Z=4, PHT=4K
  P1 = 8K-entry global-history predictor, BHR=8

Tournament-M2048-Nbit8K2-Perceptron16K-N8
  P0 = 2-bit 8K-entry predictor
  P1 = perceptron predictor M=364, n=8

Tournament-M2048-Local1024x6-Perceptron16K-N8
  P0 = local-history predictor, BHT=1024 entries, Z=6, PHT=4K
  P1 = perceptron predictor M=364, n=8
```

We implemented these ourselves through a generic `TournamentHybridPredictor` class. We also implemented the static predictors, the local/global two-level predictors, and the Alpha-style hybrid predictor. The existing `NbitPredictor`, `PentiumMBranchPredictor`, and `PerceptronPredictor` are reused as components where appropriate.

The final report should compare the 18 predictors using direction MPKI and hardware complexity. The best final choice is empirical: a more complex predictor is only worth it if it gives a meaningful MPKI improvement over simpler alternatives.

## 5.7 Ref-input Validation

The experiments in 5.3-5.6 use the `train` inputs. These runs are useful because they finish in reasonable time, but they are still samples of each benchmark's behavior. The `ref` inputs are longer and usually more representative, so 5.7 checks whether our train-based conclusions remain valid.

The question is not only "what is the MPKI on ref?" but also:

```text
Did the ordering of the predictors change?
Did a predictor that looked good on train become worse on ref?
Are the train conclusions stable enough to justify the final choice?
```

We selected the strict top 3 predictors from the 5.6.2 train comparison:

```text
Alpha21264
Perceptron-M141-N32
Perceptron-M56-N72
```

This is a clean selection rule because 5.7 is a validation step: first choose candidates from train, then test them on ref. We avoid the larger 5.6.1 perceptrons because they use much more than the intended 32K-bit budget and would not be comparable to the 5.6.2 predictors.

The expected analysis is:

- compare each predictor's train and ref direction MPKI,
- compare the ranking on train versus ref,
- explain any changes using benchmark behavior and predictor structure,
- make the final report choice based on ref behavior, hardware cost, and implementation complexity.
