#!/bin/bash
# RUN TRAIN STATS

# Absolute paths for PIN executable and tool:
PIN_EXE="/path/to/pin-external-4.2-99776-g21d818fa2-gcc-linux/pin"
PIN_TOOL="/path/to/pintool/obj-intel64/cslab_branch_stats.so"
# Output directory for PIN's output -- BE CAREFUL! THE PATH NEEDS TO EXIST!!!
outDir="/path/to/outputs_stats/train"
# Base directory that contains all benchmark folders (This is the directory where all the benchmark folders are)
inputBase="/path/to/spec_execs_train_inputs"


# Loop over every subfolder in the input base directory.
# By uncommenting the respective lines below you can run either only one benchmark or all benchmarks inside a directory
# Uncomment following line (and "done" at the end of loop) for looping
for folder in "$inputBase"/*; do

# Uncomment following line to check only 403.gcc (also comment the "done" at the end of the loop). Give the benchmark folder name as the first argument when running
#folder="$inputBase/$1" # $1 is the first argument
    if [ -d "$folder" ]; then
        BENCH=$(basename "$folder")
        (
            cd "$folder" || { echo "Failed to enter $folder"; exit 1; }

            echo "=============================================="
            echo "Contents of speccmds.cmd for $BENCH:"
            echo "----------------------------------------------"
            # display only the first line
            head -n 1 speccmds.cmd
            echo "=============================================="
            echo ""

	    # Old speccmds.cmd where mutliple lines (new ones are only 1 line). Read the first line from speccmds.cmd
            line=$(head -n 1 speccmds.cmd)

            # Old speccmds.cmd has arguments before the ./ execution. We don't want these. Extract everything from the first occurrence of "./", including "./"
            clean_cmd=$(echo "$line" | sed -n 's/.*\(\.\/.*\)/\1/p')

            # PIN output file
            pinOutFile="$outDir/${BENCH}.cslab_branch_stats_train.out"

            # Construct the complete PIN command.
            pin_cmd="$PIN_EXE -t $PIN_TOOL -o $pinOutFile -- $clean_cmd 1> stdout.log 2> stderr.log"
            echo "PIN_CMD: $pin_cmd"

            # Execute the command while measuring time; timing output goes to a log file.
            { /bin/bash -c "$pin_cmd" ; }
	    # You can also measure execution time if you run it like this: 
            # { time /bin/bash -c "$pin_cmd" ; } &> "$outDir/${BENCH}_timing.log"
        ) &
    fi
done

wait
echo "Train Stats. All benchmarks done."

