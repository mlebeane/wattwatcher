#!/usr/bin/python
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
# take a  perf -x , -I performance counter log and invert it to something graphable
import csv
import os
import shutil
import sys
import collections
import argparse

def process_cntrs(stats, l3_avail, fp_avail, bin_size, TSC_FREQUENCY, num_threads):
	stats["frequency"] = TSC_FREQUENCY * float(stats["cycles"])/float(stats["ref-cycles"]) / 1000000
	
	if num_threads == 0:
		stats["total_cycles"] = bin_size * stats["frequency"] * 1000000
    	else:
        	stats["total_cycles"] = bin_size * stats["frequency"] * 1000000 * num_threads
	stats["busy_cycles"] = stats["cycles"] 
	stats["idle_cycles"] = stats["total_cycles"] - stats["busy_cycles"]
	stats["ipc"] = float(stats["instructions"])/float(stats["cycles"])
	
	stats["branch_miss_rate"] = float(stats["branches_mispredicted"])/float(stats["branches_executed"])
	
	#TODO: Add in icache miss rate
	stats["icache_miss_rate"] = 0
	stats["dcache_miss_rate"] = float(stats["dcache_read_misses"] + stats["dcache_writes"]) / float(stats["dcache_reads"] + stats["dcache_writes"])

	if l3_avail:
	    stats["l2_miss_rate"] = float(stats["l2_misses"]) / float(stats["l2_accesses"])
	    stats["l3_miss_rate"] = float(stats["l3_misses"]) / float(stats["l3_accesses"])
	else:
	    stats["l2_miss_rate"] = float(stats["l2_misses"]) / float(stats["l2_accesses"])
	    stats["l3_miss_rate"] = 0

	stats["itlb_mpki"] = float(stats["itlb_misses"]) / float(stats["instructions"]) * 1000
	stats["dtlb_mpki"] = float(stats["dtlb_misses"]) / float(stats["instructions"]) * 1000
	
	#TODO: Account for SIMD instructions here
	if fp_avail:
	    stats["fp_uops_executed"] = 16 * stats["fp_uops_executed"]
	    stats["fp_uops_retired"] = 16 * stats["fp_uops_executed"]
	else:
	    stats["fp_uops_executed"] = 0
	    stats["fp_uops_retired"] = 0

	return stats
