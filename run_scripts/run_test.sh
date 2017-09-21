#!/bin/bash

export WATTWATCHER_HOME="$HOME/Dropbox/Research/wattwatcher_prototype"
TEST="$HOME/test"

. $WATTWATCHER_HOME/cluster_functions.sh

echo starting perf
run_perf "local" haswell 1
echo running program

$TEST

echo stopping perf
stop_perf "local"
marshal_perf "local" "$HOME/results/" test haswell 1 2200000000 4 2
