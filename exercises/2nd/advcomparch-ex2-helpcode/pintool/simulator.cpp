#include "pin.H"

#include <iostream>
#include <fstream>
#include <cassert>

using namespace std;

#include "globals.h"
#define STORE_ALLOCATION STORE_ALLOCATE
#include "cache.h"

/* ===================================================================== */
/* Commandline Switches                                                  */
/* ===================================================================== */
KNOB<string> KnobOutputFile(KNOB_MODE_WRITEONCE,    "pintool",
    "o", "cslab_cache.out", "specify dcache file name");

// L1Cache
KNOB<UINT32> KnobL1CacheSize(KNOB_MODE_WRITEONCE, "pintool",
    "L1c","32", "L1 cache size in kilobytes");
KNOB<UINT32> KnobL1BlockSize(KNOB_MODE_WRITEONCE, "pintool",
    "L1b","64", "L1 cache block size in bytes");
KNOB<UINT32> KnobL1Associativity(KNOB_MODE_WRITEONCE, "pintool",
    "L1a","8", "L1 cache associativity (1 for direct mapped)");

// L2Cache
KNOB<UINT32> KnobL2CacheSize(KNOB_MODE_WRITEONCE, "pintool",
    "L2c","256", "L2 cache size in kilobytes");
KNOB<UINT32> KnobL2BlockSize(KNOB_MODE_WRITEONCE, "pintool",
    "L2b","64", "L2 cache block size in bytes");
KNOB<UINT32> KnobL2Associativity(KNOB_MODE_WRITEONCE, "pintool",
    "L2a","8", "L2 cache associativity (1 for direct mapped)");

// Prefetcher (Hardcoded 0, see below)
//KNOB<UINT32> KnobL2PrefetchLines(KNOB_MODE_WRITEONCE, "pintool",
//    "L2prf","0", "Number of lines to prefetch to L2 (0 disables prefetching)");

/* ===================================================================== */

/* ===================================================================== */
/* Global Variables                                                      */
/* ===================================================================== */

typedef TWO_LEVEL_CACHE<CACHE_SET::LRU> CACHE_T; // This is where the replacement policy is chosen
CACHE_T *two_level_cache;

UINT64 total_cycles, total_instructions;
std::ofstream outFile;

/* ===================================================================== */

INT32 Usage()
{
    //cerr << "This tool represents a 2-level tlb & cache simulator.\n\n";
    cerr << "This tool represents a 2-level cache simulator.\n\n";
    cerr << KNOB_BASE::StringKnobSummary();
    cerr << endl;
    return -1;
}

/* ===================================================================== */

VOID Load(ADDRINT addr)
{
    // get the address translation from Virtual to Physical address space
    // note: only for timing simulation purpose
    // "addr" is virtual and remains unchanged for accessing the cache hierarchy

    // load the data from the cache hierarchy
    total_cycles += two_level_cache->Access(addr, CACHE_T::ACCESS_TYPE_LOAD);
}

VOID Store(ADDRINT addr)
{
    // get the address translation from Virtual to Physical address space
    // note: only for timing simulation purpose
    // "addr" is virtual and remains unchanged for accessing the cache hierarchy
    
    // store the data to the cache hierarchy
    total_cycles += two_level_cache->Access(addr, CACHE_T::ACCESS_TYPE_STORE);
}

VOID count_instruction()
{
    total_instructions++;
    total_cycles++;
}

VOID Instruction(INS ins, void * v)
{
    UINT32 memOperands = INS_MemoryOperandCount(ins);

    // Instrument each memory operand. If the operand is both read and written
    // it will be processed twice.
    // Iterating over memory operands ensures that instructions on IA-32 with
    // two read operands (such as SCAS and CMPS) are correctly handled.
    for (UINT32 memOp = 0; memOp < memOperands; memOp++) {
        if (INS_MemoryOperandIsRead(ins, memOp)) {
            INS_InsertPredicatedCall(ins, IPOINT_BEFORE, (AFUNPTR) Load,
                                     IARG_MEMORYOP_EA, memOp, IARG_END);
        }
        if (INS_MemoryOperandIsWritten(ins, memOp)) {
            INS_InsertPredicatedCall(ins, IPOINT_BEFORE, (AFUNPTR) Store,
                                     IARG_MEMORYOP_EA, memOp, IARG_END);
        }
    }

    // Count each and every instruction
    INS_InsertCall(ins, IPOINT_BEFORE, (AFUNPTR)count_instruction, IARG_END);
}

/* ===================================================================== */

VOID Fini(int code, VOID * v)
{
    // Report total instructions and total cycles
    outFile << "--------\n";
    outFile << "Total Statistics\n";
    outFile << "--------\n";
    outFile << "Total Instructions: " << total_instructions << "\n";
    outFile << "Total Cycles: " << total_cycles << "\n";
    outFile << "IPC: " << (double)total_instructions / (double)total_cycles << "\n";
    outFile << "\n";

    outFile << two_level_cache->PrintCache("");
    outFile << two_level_cache->StatsLong("");

    outFile.close();
}

VOID roi_begin()
{
    INS_AddInstrumentFunction(Instruction, 0);
}


/* ===================================================================== */

int main(int argc, char *argv[])
{
    PIN_InitSymbols();

    if(PIN_Init(argc,argv))
        return Usage();

    // Open output file
    outFile.open(KnobOutputFile.Value().c_str());

   // Initialize two level Cache
    two_level_cache = new CACHE_T("Two level Cache hierarchy",
                                  KnobL1CacheSize.Value() * KILO,
                                  KnobL1BlockSize.Value(),
                                  KnobL1Associativity.Value(),
                                  KnobL2CacheSize.Value() * KILO,
                                  KnobL2BlockSize.Value(),
                                  KnobL2Associativity.Value(),
				  0,
                                  1,
                                  10,
                                  200);
				  //KnobL2PrefetchLines.Value()); (I don't want prefetching at all in this run, so hardcode 0)

    INS_AddInstrumentFunction(Instruction, 0);

    // Called when the instrumented application finishes its execution
    PIN_AddFiniFunction(Fini, 0);

    // Never returns
    PIN_StartProgram();
    
    return 0;
}

/* ===================================================================== */
/* eof */
/* ===================================================================== */
