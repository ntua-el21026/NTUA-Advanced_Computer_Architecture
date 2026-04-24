#include "pin.H"

#include <iostream>
#include <fstream>
#include <cassert>

using namespace std;

#include "branch_predictor.h"
#include "pentium_m_predictor/pentium_m_branch_predictor.h"
#include "ras.h"

/* ===================================================================== */
/* Commandline Switches                                                  */
/* ===================================================================== */
KNOB<string> KnobOutputFile(KNOB_MODE_WRITEONCE,    "pintool",
    "o", "cslab_branch.out", "specify output file name");
KNOB<string> KnobPredictorSet(KNOB_MODE_WRITEONCE, "pintool",
    "predictor_set", "5.3", "predictor set to instantiate: 5.3, 5.4, 5.5, 5.6.1, 5.6.2, 5.7, pentium-m, all");
/* ===================================================================== */

/* ===================================================================== */
/* Global Variables                                                      */
/* ===================================================================== */
std::vector<BranchPredictor *> branch_predictors;
typedef std::vector<BranchPredictor *>::iterator bp_iterator_t;

//> BTBs have slightly different interface (they also have target predictions)
//  so we need to have different vector for them.
std::vector<BTBPredictor *> btb_predictors;
typedef std::vector<BTBPredictor *>::iterator btb_iterator_t;

std::vector<RAS *> ras_vec;
typedef std::vector<RAS *>::iterator ras_vec_iterator_t;

UINT64 total_instructions;
std::ofstream outFile;

/* ===================================================================== */

INT32 Usage()
{
    cerr << "This tool simulates various branch predictors.\n\n";
    cerr << KNOB_BASE::StringKnobSummary();
    cerr << endl;
    return -1;
}

/* ===================================================================== */

VOID count_instruction()
{
    total_instructions++;
}

VOID call_instruction(ADDRINT ip, ADDRINT target, UINT32 ins_size)
{
    ras_vec_iterator_t ras_it;

    for (ras_it = ras_vec.begin(); ras_it != ras_vec.end(); ++ras_it) {
        RAS *ras = *ras_it;
        ras->push_addr(ip + ins_size);
    }
}

VOID ret_instruction(ADDRINT ip, ADDRINT target)
{
    ras_vec_iterator_t ras_it;

    for (ras_it = ras_vec.begin(); ras_it != ras_vec.end(); ++ras_it) {
        RAS *ras = *ras_it;
        ras->pop_addr(target);
    }
}

VOID cond_branch_instruction(ADDRINT ip, ADDRINT target, BOOL taken)
{
    bp_iterator_t bp_it;
    BOOL pred;

    for (bp_it = branch_predictors.begin(); bp_it != branch_predictors.end(); ++bp_it) {
        BranchPredictor *curr_predictor = *bp_it;
        pred = curr_predictor->predict(ip, target);
        curr_predictor->update(pred, taken, ip, target);
    }
}

VOID branch_instruction(ADDRINT ip, ADDRINT target, BOOL taken)
{
    btb_iterator_t btb_it;
    BOOL pred;

    for (btb_it = btb_predictors.begin(); btb_it != btb_predictors.end(); ++btb_it) {
        BTBPredictor *curr_predictor = *btb_it;
        pred = curr_predictor->predict(ip, target);
        curr_predictor->update(pred, taken, ip, target);
    }
}

VOID Instruction(INS ins, void * v)
{
    if (INS_Category(ins) == XED_CATEGORY_COND_BR)
        INS_InsertCall(ins, IPOINT_BEFORE, (AFUNPTR)cond_branch_instruction,
                       IARG_INST_PTR, IARG_BRANCH_TARGET_ADDR, IARG_BRANCH_TAKEN,
                       IARG_END);
    else if (INS_IsCall(ins))
        INS_InsertCall(ins, IPOINT_BEFORE, (AFUNPTR)call_instruction,
                       IARG_INST_PTR, IARG_BRANCH_TARGET_ADDR,
                       IARG_UINT32, INS_Size(ins), IARG_END);
    else if (INS_IsRet(ins))
        INS_InsertCall(ins, IPOINT_BEFORE, (AFUNPTR)ret_instruction,
                       IARG_INST_PTR, IARG_BRANCH_TARGET_ADDR, IARG_END);

    // For BTB we instrument all branches and calls except returns.
    if ((INS_IsBranch(ins) || INS_IsCall(ins)) && !INS_IsRet(ins))
    INS_InsertCall(ins, IPOINT_BEFORE, (AFUNPTR)branch_instruction,
                   IARG_INST_PTR, IARG_BRANCH_TARGET_ADDR, IARG_BRANCH_TAKEN,
                   IARG_END);

    // Count each and every instruction
    INS_InsertCall(ins, IPOINT_BEFORE, (AFUNPTR)count_instruction, IARG_END);
}

/* ===================================================================== */

VOID Fini(int code, VOID * v)
{
    bp_iterator_t bp_it;
    btb_iterator_t btb_it;
    ras_vec_iterator_t ras_it;

    // Report total instructions and total cycles
    outFile << "Total Instructions: " << total_instructions << "\n";
    outFile << "\n";

    outFile <<"RAS: (Correct - Incorrect)\n";
    for (ras_it = ras_vec.begin(); ras_it != ras_vec.end(); ++ras_it) {
        RAS *ras = *ras_it;
        outFile << ras->getNameAndStats() << "\n";
    }
    outFile << "\n";

    outFile <<"Branch Predictors: (Name - Correct - Incorrect)\n";
    for (bp_it = branch_predictors.begin(); bp_it != branch_predictors.end(); ++bp_it) {
        BranchPredictor *curr_predictor = *bp_it;
        outFile << "  " << curr_predictor->getName() << ": "
                << curr_predictor->getNumCorrectPredictions() << " "
                << curr_predictor->getNumIncorrectPredictions() << "\n";
    }
    outFile << "\n";

    outFile <<"BTB Predictors: (Name - Correct - Incorrect - TargetCorrect - TargetIncorrect)\n";
    for (btb_it = btb_predictors.begin(); btb_it != btb_predictors.end(); ++btb_it) {
        BTBPredictor *curr_predictor = *btb_it;
        outFile << "  " << curr_predictor->getName() << ": "
                << curr_predictor->getNumCorrectPredictions() << " "
                << curr_predictor->getNumIncorrectPredictions() << " "
                << curr_predictor->getNumCorrectTargetPredictions() << " "
                << curr_predictor->getNumIncorrectTargetPredictions() << "\n";
    }

    outFile.close();
}

/* ===================================================================== */

VOID InitPredictors()
{
    string predictor_set = KnobPredictorSet.Value();

    if (predictor_set == "5.3" || predictor_set == "all") {
        // 5.3(i): fixed 16K-entry BHT, standard n-bit saturating counters.
        branch_predictors.push_back(new NbitPredictor(14, 1));
        branch_predictors.push_back(new NbitPredictor(14, 2));
        branch_predictors.push_back(new NbitPredictor(14, 3));
        branch_predictors.push_back(new NbitPredictor(14, 4));

        // 5.3(ii): Nair Table VI alternatives. ABACBDCD:3 is the standard
        // 2-bit saturating counter above, so only the four non-standard FSMs
        // are instantiated here.
        branch_predictors.push_back(new NairTwoBitFsmPredictor(14, "BCBAADCD", 3));
        branch_predictors.push_back(new NairTwoBitFsmPredictor(14, "BCBABDCD", 3));
        branch_predictors.push_back(new NairTwoBitFsmPredictor(14, "CBBDACBA", 10));
        branch_predictors.push_back(new NairTwoBitFsmPredictor(14, "BACADBDC", 12));

        // 5.3(iii): fixed 32K-bit hardware budget variants.
        branch_predictors.push_back(new NbitPredictor(15, 1));
        branch_predictors.push_back(new NbitPredictor(13, 4));
    }

    if (predictor_set == "5.6.1" || predictor_set == "all") {
        // 5.6.1: perceptron predictors for all assignment M and n pairs.
        UINT32 perceptron_counts[] = {32, 512, 1024};
        UINT32 history_lengths[] = {4, 8, 32, 60, 72};

        for (UINT32 i = 0; i < sizeof(perceptron_counts) / sizeof(perceptron_counts[0]); i++) {
            for (UINT32 j = 0; j < sizeof(history_lengths) / sizeof(history_lengths[0]); j++) {
                branch_predictors.push_back(new PerceptronPredictor(perceptron_counts[i], history_lengths[j]));
            }
        }
    }

    if (predictor_set == "5.6.2" || predictor_set == "all") {
        // 5.6.2: final cross-family comparison. Most predictors are sized
        // near 32K bits, except Pentium-M (~30K) and Alpha21264 (~29K).
        branch_predictors.push_back(new StaticAlwaysTakenPredictor());
        branch_predictors.push_back(new StaticBTFNTPredictor());

        // Best fixed-32K n-bit predictor from 5.3(iii).
        branch_predictors.push_back(new NbitPredictor(14, 2));

        branch_predictors.push_back(new PentiumMBranchPredictor());

        // Local-history two-level predictors:
        // PHT = 8192 2-bit counters = 16K bits, BHT = X * Z = 16K bits.
        branch_predictors.push_back(new LocalHistoryTwoLevelPredictor(2048, 8, 8192, 2));
        branch_predictors.push_back(new LocalHistoryTwoLevelPredictor(4096, 4, 8192, 2));
        branch_predictors.push_back(new LocalHistoryTwoLevelPredictor(8192, 2, 8192, 2));

        // Global-history two-level predictors:
        // PHT = 16K 2-bit counters = 32K bits; BHR overhead is ignored.
        branch_predictors.push_back(new GlobalHistoryTwoLevelPredictor(16384, 4, 2));
        branch_predictors.push_back(new GlobalHistoryTwoLevelPredictor(16384, 8, 2));
        branch_predictors.push_back(new GlobalHistoryTwoLevelPredictor(16384, 12, 2));

        // Perceptrons near 32K bits:
        // cost = M * (n + 1) * (1 + floor(log2(theta))).
        branch_predictors.push_back(new PerceptronPredictor(728, 8));
        branch_predictors.push_back(new PerceptronPredictor(141, 32));
        branch_predictors.push_back(new PerceptronPredictor(56, 72));

        branch_predictors.push_back(new Alpha21264Predictor());

        // Tournament hybrids: meta predictor overhead is ignored; P0 and P1
        // are each approximately 16K bits.
        branch_predictors.push_back(
            new TournamentHybridPredictor(
                1024,
                new NbitPredictor(14, 1),
                new GlobalHistoryTwoLevelPredictor(8192, 8, 2),
                "Tournament-M1024-Nbit16K1-Global8K-BHR8"));
        branch_predictors.push_back(
            new TournamentHybridPredictor(
                1024,
                new LocalHistoryTwoLevelPredictor(2048, 4, 4096, 2),
                new GlobalHistoryTwoLevelPredictor(8192, 8, 2),
                "Tournament-M1024-Local2048x4-Global8K-BHR8"));
        branch_predictors.push_back(
            new TournamentHybridPredictor(
                2048,
                new NbitPredictor(13, 2),
                new PerceptronPredictor(364, 8),
                "Tournament-M2048-Nbit8K2-Perceptron16K-N8"));
        branch_predictors.push_back(
            new TournamentHybridPredictor(
                2048,
                new LocalHistoryTwoLevelPredictor(1024, 6, 4096, 2),
                new PerceptronPredictor(364, 8),
                "Tournament-M2048-Local1024x6-Perceptron16K-N8"));
    }

    if (predictor_set == "5.7" || predictor_set == "all") {
        // 5.7: ref-input validation of the top three predictors selected
        // from the 5.6.2 train-input comparison.
        branch_predictors.push_back(new Alpha21264Predictor());
        branch_predictors.push_back(new PerceptronPredictor(141, 32));
        branch_predictors.push_back(new PerceptronPredictor(56, 72));
    }

    if (predictor_set == "pentium-m" || predictor_set == "all") {
        // Pentium-M predictor
        PentiumMBranchPredictor *pentiumPredictor = new PentiumMBranchPredictor();
        branch_predictors.push_back(pentiumPredictor);
    }

    if (predictor_set == "5.4" || predictor_set == "all") {
        // 5.4: total BTB entries, associativity.
        btb_predictors.push_back(new BTBPredictor(512, 1));
        btb_predictors.push_back(new BTBPredictor(512, 2));
        btb_predictors.push_back(new BTBPredictor(256, 2));
        btb_predictors.push_back(new BTBPredictor(256, 4));
        btb_predictors.push_back(new BTBPredictor(128, 2));
        btb_predictors.push_back(new BTBPredictor(128, 4));
        btb_predictors.push_back(new BTBPredictor(64, 4));
        btb_predictors.push_back(new BTBPredictor(64, 8));
    }

    if (branch_predictors.empty() && btb_predictors.empty() && predictor_set != "5.5") {
        cerr << "Unknown -predictor_set value: " << predictor_set << "\n";
        cerr << "Valid values: 5.3, 5.4, 5.5, 5.6.1, 5.6.2, 5.7, pentium-m, all\n";
        PIN_ExitProcess(1);
    }
}

VOID InitRas()
{
    string predictor_set = KnobPredictorSet.Value();

    if (predictor_set == "5.5" || predictor_set == "all") {
        UINT32 sizes[] = {4, 8, 16, 32, 48, 64};
        for (UINT32 i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++)
            ras_vec.push_back(new RAS(sizes[i]));
        return;
    }

    for (UINT32 i = 1; i <= 32; i*=2)
        ras_vec.push_back(new RAS(i));
}

int main(int argc, char *argv[])
{
    PIN_InitSymbols();

    if(PIN_Init(argc,argv))
        return Usage();

    // Open output file
    outFile.open(KnobOutputFile.Value().c_str());

    // Initialize predictors and RAS vector
    InitPredictors();
    InitRas();

    // Instrument function calls in order to catch __parsec_roi_{begin,end}
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
