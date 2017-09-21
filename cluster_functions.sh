#!/bin/bash
# Copyright (c) 2015, Michael LeBeane
# The University of Texas at Austin
# The Laboratory for Computer Architecture (LCA)
# All rights reserved.
#
# Redistribution of this source or derived binaries is not authorized without
# the express written consent of the original copyright holders.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AN
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Utility functions used to control perf and launch the WattWatcher post processor

PERF_START_TIME=""
PERF_END_TIME=""

EXIT_CODE=0

function execute {
 echo $1
 if [ "$QUIET_MODE" != "y" ]
 then
   eval $1
   EXIT_CODE=$?
 fi
}

# Launches a remote or local perf monitor (full system aggregated cores)
# $1 = Full name of remote host node, "local" if we are doing a local run
# $2 = Microarch
# $3 = Performance counter sample rate in seconds (decimals ok)
function run_perf {
    NODE=$1
    CNTR_FILE=$WATTWATCHER_HOME/counter_lists/$2.txt
    SAMPLE_RATE=`bc -l <<< "scale=0; $3 *1000" | xargs printf "%1.0f"`
    QUIET_MODE=$5
    CNTRS=`grep ^[^#] $CNTR_FILE | awk 'BEGIN { ORS=","; FS=","; } { print $1}' | sed 's/.$//'`
    if [ $NODE == "local" ]
    then
        rm -f counters.csv
	execute "perf stat -x , -I $SAMPLE_RATE -a -A -e $CNTRS  -o counters.csv sleep infinity &"
    else
        ssh -p 3131 lca@$NODE "rm counters.csv"
        echo "sleep infinity" > wait.sh 
        chmod +x wait.sh
        scp -P 3131 wait.sh lca@$NODE:~/
        rm wait.sh
        PERF_CMD="perf stat -x , -I $SAMPLE_RATE -a -A -e $CNTRS ./wait.sh"
        ssh -n -p 3131 lca@$NODE "nohup $PERF_CMD > /dev/null 2>> counters.csv &" 
    fi
    PERF_START_TIME=`date +%s`
}

# Stops a local or remote perf daemon
# $1 = Full name of remote host node, "local" if we are doing a local run
function stop_perf {
    NODE=$1
    QUITE_MODE=$2
    if [ $NODE == "local" ]
    then
        execute "pkill sleep"
    else
        ssh -n -p 3131 lca@$NODE "pkill sleep"
    fi
    PERF_END_TIME=`date +%s`
}

# Aggregates together all of the relevant stats from perf and post processes them
# Also uses the performance counters to launch McPat analysis
# $1 = Full name of remote host node, "local" if we are doing a local run
# $2 = Output directory
# $3 = Name prefix for outputs
# $4 = microarch
# $5 = Histogram bin size (in seconds).  Will smooth out the performance counters to 
#      the requested bin size, reguardless of the sample rate
# $6 = TSC_FREQUENCY (Hz)
# $7 = CORES
# $8 = THREADS_PER_CORE
# $9 = Quite mode actually doesn't run

function marshal_perf {
    NODE=$1
    RESULTS_DIR=$2
    BENCH_NAME=$3
    MICROARCH=$4
    BIN_SIZE=$5
    TSC_FREQUENCY=$6
    CORES=$7
    THREADS_PER_CORE=$8
    QUIET_MODE=$9

    # move the results to the run directory
    mkdir -p $RESULTS_DIR
    if [ $NODE == "local" ]
    then
        execute "mv counters.csv $RESULTS_DIR/$BENCH_NAME-counters.csv 2> /dev/null" 
    else
        scp -P 3131 lca@$NODE:~/counters.csv $RESULTS_DIR/$BENCH_NAME-counters.csv
    fi
  
    # Post the start and end times for this run
    if [ $EXIT_CODE == "0" ]
    then
        echo "START TIME,$PERF_START_TIME" >> $RESULTS_DIR/$BENCH_NAME-counters.csv
        echo "END TIME,$PERF_END_TIME" >> $RESULTS_DIR/$BENCH_NAME-counters.csv
    fi

    # Post process correctly
    sed -i '/Terminated/d' $RESULTS_DIR/$BENCH_NAME-counters.csv
    sed -i '/^\s*$/d' $RESULTS_DIR/$BENCH_NAME-counters.csv
    sed -i '/^#/ d' $RESULTS_DIR/$BENCH_NAME-counters.csv
    sed -i "s/^[ \t]*//" $RESULTS_DIR/$BENCH_NAME-counters.csv
    
    execute "PYTHONPATH=:$PYTHONPATH:$WATTWATCHER_HOME/sniper_libs $WATTWATCHER_HOME/process.py 
				       $RESULTS_DIR/$BENCH_NAME-counters.csv 
				       $RESULTS_DIR 
     		                       $MICROARCH 
                                       $BIN_SIZE 
				       $TSC_FREQUENCY
                                       $CORES
				       $THREADS_PER_CORE"   
}

# same thing as marshal perf, but it assumes the config files already exist in the right place and we just need to redo the analysis
function analyze_perf {

    NODE=$1
    RESULTS_DIR=$2
    NAME=$3
    MICROARCH=$4
    BIN_SIZE=$5
    TSC_FREQUENCY=$6
    CORES=$7
    THREADS_PER_CORE=$8
    QUIET_MODE=$9
 
   
    execute "PYTHONPATH=:$PYTHONPATH:$WATTWATCHER_HOME/sniper_libs $WATTWATCHER_HOME/process.py 
				       $RESULTS_DIR/$NAME-counters.csv 
				       $RESULTS_DIR 
     		                       $MICROARCH 
                                       $BIN_SIZE 
				       $TSC_FREQUENCY
                                       $CORES
				       $THREADS_PER_CORE"     

}
