#!/bin/bash

## Modify the following paths appropriately
#Absolute paths for PIN executable and tool:
PIN_EXE="/path/to/pin-external-x.xx-xxxxx-xxxxxxxxxx-gcc-linux/pin"
PIN_TOOL="/path/to/pintool/obj-intel64/simulator.so"
# Output directory for PIN's output
outDir="/path/to/outputs"
# Base directory that contains all benchmark folders (This is the directory where all the benchmark folders are)
inputBase="/path/to/spec_benchmarks"

## Triples of <cache_size>_<associativity>_<block_size>
CONFS="512_4_128 512_8_128"

L1size=32
L1assoc=4
L1bsize=32

# Loop over every subfolder in the input base directory
for folder in "$inputBase"/*; do
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

	    # For each benchmark, run with all the different input combinations from "CONFS" list
            for conf in $CONFS; do
	    	## Get parameters
	    	L2size=$(echo $conf | cut -d'_' -f1)
	    	L2assoc=$(echo $conf | cut -d'_' -f2)
	    	L2bsize=$(echo $conf | cut -d'_' -f3)

            	# Create and set output file path
		outFile=$(printf "%s.cslab_cache_stats_L2_LRU_%04d_%02d_%03d.out" $BENCH ${L2size} ${L2assoc} ${L2bsize})
		outBenchFolder="$outDir/$BENCH"
		mkdir -p "$outBenchFolder"  # Create internal folders if they don't already exist
		pinOutFile="$outBenchFolder/$outFile"

            	# PIN command
		pin_cmd="$PIN_EXE -t $PIN_TOOL -o $pinOutFile -L1c ${L1size} -L1a ${L1assoc} -L1b ${L1bsize} -L2c ${L2size} -L2a ${L2assoc} -L2b ${L2bsize} -- $clean_cmd "
            	
		echo "PIN_CMD: $pin_cmd"
	
            	#/bin/bash -c "$pin_cmd" & # Careful! The last "&" is so that each config runs in parallel. Decide whether you want this or not.
	    	# You can also measure execution time if you run it like this: 
            	{ time /bin/bash -c "$pin_cmd" ; } &> "$outBenchFolder/$outFile.time" &
	    done

	    wait
        ) &
    fi
done

wait
echo "All benchmarks done."

