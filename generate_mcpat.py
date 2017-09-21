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

# Generates McPAT input files by populating a template
# @date: 11/21/2014

import csv
import os
import xml.etree.ElementTree as ET
import shutil
import sys
import collections
import argparse


def generate_mcpat(stats, output_dir, input_proc_model, l3_avail, bin_size, CORES, HW_THREADS, TSC_FREQUENCY):

	print "********** Generating McPAT input files **********"
	shutil.rmtree(output_dir,ignore_errors=True)
	os.makedirs(output_dir)

	# now, import the base McPat config file and augment the runtime statistics with our data
	tree = ET.parse(input_proc_model)
	root = tree.getroot()
	file_num = 0
	
	for time_stamp in stats.itervalues().next().keys():


		total_cycles = []
		idle_cycles = []
		busy_cycles = []

		for i in range(0,HW_THREADS):
			total_cycles.append(stats["CPU" + str(i)][time_stamp]["total_cycles"])
			idle_cycles.append(stats["CPU" + str(i)][time_stamp]["idle_cycles"])
			busy_cycles.append(stats["CPU" + str(i)][time_stamp]["busy_cycles"])
		total_cycles= max(total_cycles)
		idle_cycles = min(idle_cycles)
		busy_cycles = max(busy_cycles)
	
		# cycle information
		# These cycles define the simulation time only, so just express them as the TSC_Frequency into bin szie
		root.find(".//*[@id='system']/stat[@name='total_cycles']").set        ('value',str(bin_size * TSC_FREQUENCY))
		
		d = stats["TOTAL"][time_stamp]
		#l3 stats
		if l3_avail:
			# lets say 1/4 are writes and 3/4 are reads
			l3_reads = int(d["l3_accesses"]) * 0.75
			l3_writes = int(d["l3_accesses"]) * 0.25
			l3_write_misses =  int(d["l3_misses"]) * 0.25
			l3_read_misses = int(d["l3_misses"]) * 0.75
			root.find(".//*[@id='system.L30']/stat[@name='read_accesses']").set       ('value',str(l3_reads))
			root.find(".//*[@id='system.L30']/stat[@name='read_misses']").set         ('value',str(l3_read_misses))
			root.find(".//*[@id='system.L30']/stat[@name='write_accesses']").set       ('value',str(l3_writes))
			root.find(".//*[@id='system.L30']/stat[@name='write_misses']").set         ('value',str(l3_write_misses))

		#mc stats
		if l3_avail:
			# lets say 1/4 are writes and 3/4 are reads
			memory_reads = l3_write_misses
			memory_writes = l3_read_misses
			root.find(".//*[@id='system.mc']/stat[@name='memory_accesses']").set       ('value',str(int(d["l3_misses"])))
			root.find(".//*[@id='system.mc']/stat[@name='memory_reads']").set         ('value',str(memory_reads))
			root.find(".//*[@id='system.mc']/stat[@name='memory_writes']").set       ('value',str(memory_writes))
		else:
			root.find(".//*[@id='system.mc']/stat[@name='memory_accesses']").set       ('value',str(int(d["l2_write_misses"]) + int(d["l2_read_misses"])))
			root.find(".//*[@id='system.mc']/stat[@name='memory_reads']").set         ('value',str(int(d["l2_read_misses"])))
			root.find(".//*[@id='system.mc']/stat[@name='memory_writes']").set       ('value',str(int(d["l2_write_misses"])))

			
		#Populate core level stats
		# For core level stats, we need to merge all the HW_Threads into their shared physical resources
		# threads are merged as follows (for a 4 core machine with 8 threads)
		# 0/4,2/5,3/6,4/7
		threads_per_core = HW_THREADS / CORES
		core_id = 0
		for k in range(0,CORES,1):
			d = {}
			for stat in stats.itervalues().next().itervalues().next().keys():
				d[stat] = 0
				for j in range(k, HW_THREADS, CORES):
					d[stat] += stats["CPU" + str(j)][time_stamp][stat]

			# The frequency and voltage depends on the host power state!
			root.find(".//*[@id='system.core" + str(core_id) + "']/param[@name='clock_rate']").set        ('value',str(int(TSC_FREQUENCY / 1000000)))
			#root.find(".//*[@id='system.core" + str(core_id) + "']/param[@name='vdd']").set        ('value',str(package_voltage))
		
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='total_instructions']").set        ('value',str(int(d["uops_dispatched"])))

			# estimate int instructions as uops - FP - BR 
			int_estimate = (d["uops_dispatched"] - d["fp_uops_executed"] - d["branches_executed"])
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='int_instructions']").set           ('value',str(int(int_estimate)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='fp_instructions']").set           ('value',str(d["fp_uops_executed"]))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='branch_instructions']").set       ('value',str(d["branches_executed"]))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='branch_mispredictions']").set     ('value',str(d["branches_mispredicted"]))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='load_instructions']").set        ('value',str(d["dcache_reads"]))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='store_instructions']").set        ('value',str(d["dcache_writes"]))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='committed_instructions']").set    ('value',str(d["uops_retired"]))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='committed_int_instructions']").set    ('value',str(int_estimate))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='committed_fp_instructions']").set ('value',str(d["fp_uops_retired"]))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='context_switches']").set          ('value',str(d["context_switches"]))
			
			# this is a little complicated with hyperthreading
			# We don't want to count total cycles for each logical thread, only physical core, so devide out the threads per core
			# We assume that the busy cycles don't overlap, and can be added. This is an estimate and could result in a value greater than total_cycles, so fix that up!
			per_core_total_cycles = d["total_cycles"] / threads_per_core
			if (d["busy_cycles"]/2) > per_core_total_cycles:
				per_core_busy_cycles = per_core_total_cycles
			else:
				per_core_busy_cycles = d["busy_cycles"]/2
			per_core_idle_cycles = per_core_total_cycles - per_core_busy_cycles
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='total_cycles']").set    ('value',str(bin_size * TSC_FREQUENCY))

			# CORE STATS
			rob_reads =  d["uops_dispatched"]
			rob_writes = d["uops_retired"]
			rename_reads = 2 * int_estimate
			rename_writes = int_estimate
			fp_rename_reads = 2 * d["fp_uops_executed"]
			fp_rename_writes = d["fp_uops_executed"]
			inst_window_reads = int_estimate + d["branches_executed"]
			inst_window_writes = int_estimate + d["branches_executed"]
			inst_window_wakeup_accesses = int_estimate + d["branches_executed"]
			fp_inst_window_reads = d["fp_uops_executed"]
			fp_inst_window_writes = d["fp_uops_executed"]
			fp_inst_window_wakeup_accesses = d["fp_uops_executed"]
			int_regfile_reads = 2 * int_estimate
			float_regfile_reads = 2 * d["fp_uops_executed"]
			int_regfile_writes = int_estimate
			float_regfile_writes = d["fp_uops_executed"]
			ialu_accesses = int_estimate
			fpu_accesses = d["fp_uops_executed"]
			mul_accesses = 0.05 * int_estimate
			cdb_alu_accesses = int_estimate
			cdb_mul_accesses = 0.05 * int_estimate
			cdb_fpu_accesses = d["fp_uops_executed"]


			pipe_d = d["uops_dispatched"] / float(d["total_cycles"]	)		
			IFU_d = d["uops_dispatched"] / float(d["total_cycles"]	)				
			LSU_d = (d["dcache_reads"] + d["dcache_writes"]) / float(d["total_cycles"]	)	
			MemManU_I_d = d["uops_dispatched"] / float(d["total_cycles"]	)	
			MemManU_D_d = ( d["dcache_reads"] + d["dcache_writes"] ) / float(d["total_cycles"]	)	
			ALU_d = int_estimate / float(d["total_cycles"]	)	
			MUL_d = 0.3
			FPU_d = ( d["fp_uops_executed"] * 20 ) / float(d["total_cycles"]	)	
			ALU_cdb = int_estimate / float(d["total_cycles"]	)	
			MUL_cdb = 0.3
			FPU_cdb = ( d["fp_uops_executed"]  ) / float(d["total_cycles"]	)	
 
			pipeline_duty_cycle = 1.0 if pipe_d > 1.0 else pipe_d
			IFU_duty_cycle = 1.0 if IFU_d > 1.0 else IFU_d
			LSU_duty_cycle = 1.0 if LSU_d > 1.0 else LSU_d
			MemManU_I_duty_cycle = 1.0 if MemManU_I_d > 1.0 else MemManU_I_d
			MemManU_D_duty_cycle = 1.0 if MemManU_D_d > 1.0 else MemManU_D_d
			ALU_duty_cycle = 1.0 if ALU_d > 1.0 else ALU_d
			MUL_duty_cycle = 1.0 if MUL_d > 1.0 else MUL_d
			FPU_duty_cycle = 1.0 if FPU_d > 1.0 else FPU_d
			ALU_cdb_duty_cycle = 1.0 if ALU_cdb > 1.0 else ALU_cdb
			MUL_cdb_duty_cycle = 1.0 if MUL_cdb > 1.0 else MUL_cdb
			FPU_cdb_duty_cycle = 1.0 if FPU_cdb > 1.0 else FPU_cdb
			
			# mcpat requires the duty cycles for max dynamic power AND for regular dynamic power
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='pipeline_duty_cycle']").set      ('value',str(pipeline_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='IFU_duty_cycle']").set           ('value',str(IFU_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='LSU_duty_cycle']").set           ('value',str(LSU_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='MemManU_I_duty_cycle']").set     ('value',str(MemManU_I_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='MemManU_D_duty_cycle']").set     ('value',str(MemManU_D_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='ALU_duty_cycle']").set           ('value',str(ALU_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='MUL_duty_cycle']").set           ('value',str(MUL_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='FPU_duty_cycle']").set           ('value',str(FPU_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='ALU_cdb_duty_cycle']").set       ('value',str(ALU_cdb_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='MUL_cdb_duty_cycle']").set       ('value',str(MUL_cdb_duty_cycle))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='FPU_cdb_duty_cycle']").set       ('value',str(FPU_cdb_duty_cycle))


			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='ROB_reads']").set           ('value',str(int(rob_reads)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='ROB_writes']").set           ('value',str(int(rob_writes)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='rename_reads']").set       ('value',str(int(rename_reads)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='rename_writes']").set     ('value',str(int(rename_writes)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='fp_rename_reads']").set        ('value',str(int(fp_rename_reads)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='fp_rename_writes']").set        ('value',str(int(fp_rename_writes)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='inst_window_reads']").set              ('value',str(int(inst_window_reads)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='inst_window_writes']").set            ('value',str(int(inst_window_writes)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='inst_window_wakeup_accesses']").set   ('value',str(int(inst_window_wakeup_accesses)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='fp_inst_window_reads']").set          ('value',str(int(fp_inst_window_reads)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='fp_inst_window_writes']").set           ('value',str(int(fp_inst_window_writes)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='fp_inst_window_wakeup_accesses']").set           ('value',str(int(fp_inst_window_wakeup_accesses)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='int_regfile_reads']").set         ('value',str(int(int_regfile_reads)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='float_regfile_reads']").set       ('value',str(int(float_regfile_reads)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='int_regfile_writes']").set        ('value',str(int(int_regfile_writes)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='float_regfile_writes']").set     ('value',str(int(float_regfile_writes)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='ialu_accesses']").set             ('value',str(int(ialu_accesses)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='fpu_accesses']").set              ('value',str(int(fpu_accesses)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='mul_accesses']").set              ('value',str(int(mul_accesses)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='cdb_alu_accesses']").set          ('value',str(int(cdb_alu_accesses)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='cdb_mul_accesses']").set          ('value',str(int(cdb_mul_accesses)))
			root.find(".//*[@id='system.core" + str(core_id) + "']/stat[@name='cdb_fpu_accesses']").set          ('value',str(int(cdb_fpu_accesses)))

			# haswell doesnt keep track of icache reads, so assume that we have a read every 3 instructions
			icache_reads = int(d["instructions"]) / 3

			dcache_accesses = int(d["dcache_reads"]) + int(d["dcache_writes"])

			#itlb stats
			root.find(".//*[@id='system.core" + str(core_id) + ".itlb']/stat[@name='total_accesses']").set       ('value',str(icache_reads))
			root.find(".//*[@id='system.core" + str(core_id) + ".itlb']/stat[@name='total_misses']").set         ('value',str(int(d["itlb_misses"])))

			#dtlb stats
			root.find(".//*[@id='system.core" + str(core_id) + ".dtlb']/stat[@name='total_accesses']").set       ('value',str(dcache_accesses))
			root.find(".//*[@id='system.core" + str(core_id) + ".dtlb']/stat[@name='total_misses']").set         ('value',str(int(d["dtlb_misses"])))

			#icache stats
			root.find(".//*[@id='system.core" + str(core_id) + ".icache']/stat[@name='read_accesses']").set       ('value',str(icache_reads))
			root.find(".//*[@id='system.core" + str(core_id) + ".icache']/stat[@name='read_misses']").set         ('value',str(int(d["icache_misses"])))

			#dcache stats
			root.find(".//*[@id='system.core" + str(core_id) + ".dcache']/stat[@name='read_accesses']").set       ('value',str(int(d["dcache_reads"])))
			root.find(".//*[@id='system.core" + str(core_id) + ".dcache']/stat[@name='read_misses']").set         ('value',str(int(d["dcache_read_misses"])))
			root.find(".//*[@id='system.core" + str(core_id) + ".dcache']/stat[@name='write_accesses']").set       ('value',str(int(d["dcache_writes"])))
			root.find(".//*[@id='system.core" + str(core_id) + ".dcache']/stat[@name='write_misses']").set         ('value',str(int(d["dcache_write_misses"])))

			#l2 stats
			# lets say 1/4 are writes and 3/4 are reads
			l2_reads = int(d["l2_accesses"]) * 0.75
			l2_writes = int(d["l2_accesses"]) * 0.25
			l2_write_misses =  int(d["l2_misses"]) * 0.25
			l2_read_misses = int(d["l2_misses"]) * 0.75
			root.find(".//*[@id='system.L2" + str(core_id) + "']/stat[@name='read_accesses']").set       ('value',str(l2_reads))
			root.find(".//*[@id='system.L2" + str(core_id) + "']/stat[@name='read_misses']").set         ('value',str(l2_read_misses))
			root.find(".//*[@id='system.L2" + str(core_id) + "']/stat[@name='write_accesses']").set       ('value',str(l2_writes))
			root.find(".//*[@id='system.L2" + str(core_id) + "']/stat[@name='write_misses']").set         ('value',str(l2_write_misses))

			core_id +=1

		tree.write(output_dir + "/config_" + str(file_num) + ".xml")
		file_num = file_num +1
	print "********** McPAT input File Generation Complete **********"


# Run in standalone script mode
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Calculates DRAM Energy/Power")
    parser.add_argument("input_file", help="dram configuraiton file (in csv format)")
    parser.add_argument("output_dir", help="read MB")
    parser.add_argument("input_proc_model", help="write MB")
    parser.add_argument("microarch", help="elapsed time in seconds")
    parser.add_argument("bin_size", help="elapsed time in seconds",type=float)
    parser.add_argument("NUM_CORES", help="elapsed time in seconds",type=int)
    args = parser.parse_args()
    generate_mcpat(args.input_file, args.output_dir, args.input_proc_model, args.microarch, args.bin_size,  args.NUM_CORES, 0)

