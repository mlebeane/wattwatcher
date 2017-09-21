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
# Main driver for WattWatcher 
# @date: 11/21/2014
import csv
import os
import shutil
import sys
import collections
import process_cntrs
import generate_mcpat
import argparse
import run_mcpat

WATTWATCHER_HOME = os.environ['WATTWATCHER_HOME']
print WATTWATCHER_HOME

def create_total_category(stats):
    # Just for ease of use, create a TOTAL category for the sum of all cores...
    cores = stats.keys()
    time_stamps = stats.itervalues().next().keys()
    all_stats = stats.itervalues().next().itervalues().next().keys()
    stats["TOTAL"] = collections.OrderedDict()
    for time_stamp in time_stamps:
        stats["TOTAL"][time_stamp] = collections.OrderedDict()
        for stat in all_stats:
            total = 0
            for core in cores: 
                total += stats[core][time_stamp][stat]
            stats["TOTAL"][time_stamp][stat] = total

def normalize_stats(bin_size, stats, START_TIME):
    # Ok, so our sample rate may not be perfect, or may not be what we want to bin with.
    # We want to massage the numbers into uniform bin sizes.
    scaled_stats = collections.OrderedDict()
    for stat in stats.itervalues().next().keys():
        even_bin = 1
        even_bin_time_left = bin_size
        even_bin_stat_value = 0
        real_bin_time_left = 0
        prev_time_stamp = 0
        for time_stamp in stats.keys():
            while real_bin_time_left > 0:
            # If we have enough time left to fill the even bin....
                if even_bin_time_left < real_bin_time_left:
                    # what is left in the real_bin afterwards?
                    next_real_bin_time_left = real_bin_time_left - even_bin_time_left
                    next_real_bin_stat_value = ( next_real_bin_time_left / real_bin_time_left) * real_bin_stat_value
                    # fill up the current bin
                    even_bin_stat_value += real_bin_stat_value - next_real_bin_stat_value
                    scaled_stats.setdefault(even_bin + START_TIME, collections.OrderedDict())[stat] = even_bin_stat_value
                    # update the real bin and the current bin
                    even_bin_time_left = bin_size
                    even_bin += bin_size
                    even_bin_stat_value = 0
                    real_bin_time_left = next_real_bin_time_left
                    real_bin_stat_value = next_real_bin_stat_value
                    # We don't have enough time to fill the even bin........
                else:
                    even_bin_stat_value += real_bin_stat_value
                    even_bin_time_left -= real_bin_time_left
                    real_bin_time_left = 0
            real_bin_stat_value = stats[time_stamp][stat]
            real_bin_time_left = time_stamp - prev_time_stamp
            prev_time_stamp = time_stamp
    # might need an assert here to check the size of scaled_stats
    return scaled_stats


#  So we want this function the following
#  - Define the variables
#    (time: refers to timestep of interest)
#    (core: refers to core of interest) (CORE0...COREN,TOTAL)
#    (component: refers to subcomponent in the power dictionaries
#    (type: refers to the type of power (static,dynamic,total)
#       - stats[core][time][stat]           
#       - cpu_mcpat[time][component][type]
#       - cpu_rapl[time][stat]
#  - Move the stats from the input file to the data frame
#  - Normalize the stats according to the bin time
#  - Add the per core power information to the stats data frame
def process(raw_cntr_file, output_dir,  microarch, bin_size,  TSC_FREQUENCY, NUM_CORES, THREADS_PER_CORE):
    
    # Format is {time:{core:{stat:value}}}
    stats = collections.OrderedDict()
    cpu_mcpat = collections.OrderedDict()   
    cpu_rapl = collections.OrderedDict()

    START_TIME=0
    END_TIME=0
    
    # translate counter events to names WattWatcher knows about
    stat_map = {}
    with open(WATTWATCHER_HOME + "/counter_lists/" + microarch + ".txt", 'rb') as input_f:
        reader = csv.reader(input_f)
        for row in reader:
            if row:
                if not row[0].startswith('#'):
                    stat_map[row[0]] = row[1]
        input_f.close()

    # read the stats from the file into the stats dictionary
    with open(raw_cntr_file, 'rb') as input_f:
        reader = csv.reader(input_f)
        for row in reader:
            if not row:
                continue
            if row[0] == "START TIME":
                START_TIME=float(row[1])
            elif row[0] == "END TIME":
                END_TIME=float(row[1])
            else:
                translated_stat_name = stat_map[row[-1]]
                if row[2] == "<not counted>":
                    stats.setdefault(row[1], collections.OrderedDict()).setdefault(float(row[0]),collections.OrderedDict())[translated_stat_name] = 1
                elif translated_stat_name == "energy_cores" or translated_stat_name == "energy_pkg" or translated_stat_name == "energy_ram" or translated_stat_name == "energy_gpu":
                    cpu_rapl.setdefault(float(row[0]), collections.OrderedDict())[translated_stat_name] = float(row[2])
                else:
                    stats.setdefault(row[1], collections.OrderedDict()).setdefault(float(row[0]),collections.OrderedDict())[translated_stat_name] = float(row[2])
    
    create_total_category(stats)
    
    # test for the existance of RAPL,FP,and L3 cache
    RAPL_AVAIL = 0
    L3_AVAIL = 0
    FP_AVAIL = 0
    if "energy_cores" in stats.itervalues().next().itervalues().next():
        RAPL_AVAIL = 1
    if "l3_misses" in stats.itervalues().next().itervalues().next():
        L3_AVAIL = 1
    if "fp_uops_executed" in stats.itervalues().next().itervalues().next():
        L3_AVAIL = 1
    
    # smooth based on the requested_bin_size
    for core in stats.keys():
        stats[core] = normalize_stats(bin_size,stats[core],START_TIME)
    if RAPL_AVAIL:
        cpu_rapl = normalize_stats(bin_size,cpu_rapl,START_TIME)

    # for each core, compute the derived stats
    for core in stats.keys(): 
        for time_stamp in stats[core].keys():

            # compute derived statistics for each core (and in total)
            if core == "TOTAL":
                process_cntrs.process_cntrs(stats[core][time_stamp], L3_AVAIL, FP_AVAIL, bin_size, TSC_FREQUENCY, NUM_CORES * THREADS_PER_CORE)
            else:
                process_cntrs.process_cntrs(stats[core][time_stamp], L3_AVAIL, FP_AVAIL, bin_size, TSC_FREQUENCY, 0 )

    if RAPL_AVAIL:
        for time_stamp in cpu_rapl.keys():
            # Create a power category from energy and bin_size
            cpu_rapl[time_stamp]["power_pkg"] = float(cpu_rapl[time_stamp]["energy_pkg"]) / bin_size
            cpu_rapl[time_stamp]["power_cores"] = float(cpu_rapl[time_stamp]["energy_cores"]) / bin_size

    generate_mcpat.generate_mcpat(stats, output_dir + "/mcpat", WATTWATCHER_HOME + "/mcpat_procs/" + microarch + ".xml", L3_AVAIL, bin_size, NUM_CORES, NUM_CORES * THREADS_PER_CORE, TSC_FREQUENCY)
    # run the McPAT engine 
    cpu_mcpat = run_mcpat.run_mcpat(output_dir + "/mcpat/", WATTWATCHER_HOME + "/fast_mcpat", stats, NUM_CORES, NUM_CORES * THREADS_PER_CORE)
    
    
    # Print the core stats
    for core in stats.keys():
        with open(output_dir + "/cntrs_processed_" + core + ".csv", 'wb') as output_f:
            header = ["timestamp"] + stats.itervalues().next().itervalues().next().keys()
            writer = csv.writer(output_f)
            writer.writerow(header)
            for time_stamp in stats.itervalues().next().keys():
                line = [time_stamp] + stats[core][time_stamp].values()
                writer.writerow(line)
        output_f.close
        
    # Print the rapl stats
    if RAPL_AVAIL:
        with open(output_dir + "/rapl.csv", 'wb') as output_f:
            header = ["timestamp"] + cpu_rapl.itervalues().next().keys()
            writer = csv.writer(output_f)
            writer.writerow(header)
            for time_stamp in cpu_rapl.keys():
                line = [time_stamp] + cpu_rapl[time_stamp].values()
                writer.writerow(line)
            output_f.close
    
    
    # Print the McPat stats, and massage for idle vs active
    for core in range(0,NUM_CORES):
        with open(output_dir + "/mcpat_" + str(core) + ".csv", 'wb') as output_f:
            writer = csv.writer(output_f)
            components = cpu_mcpat.itervalues().next()["CPU0"]["dynamic"].keys()
            total_header = [" "] + [x + "_dynamic" for x in components] + ["static"] + ["sum"]
            writer.writerow(total_header)
            times = cpu_mcpat.keys()
            times.sort()
            for time in times:
                writer.writerow([time] + 
				cpu_mcpat[time]["CPU" + str(core)]["dynamic"].values() + 
				[cpu_mcpat[time]["CPU" + str(core)]["static"]] + 
				[sum(cpu_mcpat[time]["CPU" + str(core)]["dynamic"].values()) + cpu_mcpat[time]["CPU" + str(core)]["static"]])
            output_f.close()

    with open(output_dir + "/mcpat.csv", 'wb') as output_f:
        writer = csv.writer(output_f)
	components = cpu_mcpat.itervalues().next()["TOTAL"]["dynamic"].keys()
        total_header = [" "] + [x + "_dynamic" for x in components]  + ["dynamic"] + ["static"] + ["sum"]
        writer.writerow(total_header)
        times = cpu_mcpat.keys()
        times.sort()
        for time in times:
            writer.writerow([time] + 
			    cpu_mcpat[time]["TOTAL"]["dynamic"].values() + 
			    [sum(cpu_mcpat[time]["TOTAL"]["dynamic"].values())] +  
			    [cpu_mcpat[time]["TOTAL"]["static"]] + 
			    [sum(cpu_mcpat[time]["TOTAL"]["dynamic"].values()) + cpu_mcpat[time]["TOTAL"]["static"]])
        output_f.close()
        


# Run in standalone script mode
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Calculates DRAM Energy/Power")
    parser.add_argument("raw_cntr_file", help="raw perf output")
    parser.add_argument("output_dir", help="output results directory")
    parser.add_argument("microarch", help="microarchitecture name for McPAT config and counter mapping")
    parser.add_argument("bin_size", help="Binning time for results",type=float)
    parser.add_argument("TSC_FREQUENCY", help="Freqeuncy of the internal TSC",type=int)
    parser.add_argument("NUM_CORES", help="Number of physical cores",type=int)
    parser.add_argument("THREADS_PER_CORE", help="Threads per physical core",type=int)
    args = parser.parse_args()
    process(args.raw_cntr_file, args.output_dir,  args.microarch, args.bin_size, args.TSC_FREQUENCY, args.NUM_CORES, args.THREADS_PER_CORE)
