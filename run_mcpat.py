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

import os, sys, math, re, collections, re,  csv, argparse, subprocess
import buildstack, sniper_lib
from multiprocessing.pool import ThreadPool

# Parts of this function was modified from the Sniper simulator's McPAT plugin.
def run_mcpat(input_dir, mcpatdir, stats, CORES, HW_THREADS):
	all_items = [
		[ 'core',     .01,    'core-ooo' ],
		[ 'ifetch',   .01,    'core-ifetch' ],
		[ 'alu',      .01,    'core-alu-complex' ],
		[ 'int',      .01,    'core-alu-int' ],
		[ 'fp',       .01,    'core-alu-fp' ],
		[ 'mem',      .01,    'core-mem' ],
		[ 'icache',   .01,    'core-icache' ],
		[ 'dcache',   .01,    'core-dcache' ],
		[ 'l2',       .01,    'l2' ],
		[ 'l3',       .01,    'l3' ],
		[ 'noc',      .01,    'noc' ],
		[ 'other',    .01,    'other' ],
	]

	def mcpat_run(inputfile,mcpatdir):
		return subprocess.check_output("LD_LIBRARY_PATH=$LD_LIBRARY_PATH:" + mcpatdir + " " + mcpatdir + "/mcpat -print_level 5 -opt_for_clk 1 -infile " + inputfile, shell=True)

	def power_stack(power_dat, scale=[1.0], powertype = 'total', core = 'all', nocollapse = False):
		def getpower(powers, index=-1, key = None):
			def getcomponent(suffix):
				if key: return powers.get(key+'/'+suffix, 0)
				else: return powers.get(suffix, 0)
			index = -1
			if index == -1:
				scale_factor = 1.0
			else:
				scale_factor = scale[index]
			if powertype == 'dynamic':
				return getcomponent('Runtime Dynamic')
			elif powertype == 'static':
				return getcomponent('Subthreshold Leakage') * scale_factor + getcomponent('Subthreshold Leakage with power gating') * (1 - scale_factor) + getcomponent('Gate Leakage')
			elif powertype == 'total':
				dyn=getcomponent('Runtime Dynamic') 
				sub_leak = getcomponent('Subthreshold Leakage') * scale_factor 
				sub_leak_gate =  getcomponent('Subthreshold Leakage with power gating') * (1 - scale_factor) 
				gate_leak = getcomponent('Gate Leakage')
				return dyn + sub_leak + sub_leak_gate + gate_leak
			elif powertype == 'area':
				return getcomponent('Area') + getcomponent('Area Overhead')
			else:
				raise ValueError('Unknown powertype %s' % powertype)
	  
		
		if core == "all":
			data = {
				'l2':              	5 * sum([ getpower(cache,index) for index,cache in enumerate(power_dat.get('L2', []) )])  # shared L2
								+ 5 * sum([ getpower(core, index, 'L2') for index,core in enumerate(power_dat['Core']) ]), # private L2
				'l3':               5 * sum([ getpower(cache) for index,cache in enumerate(power_dat.get('L3', [])) ]),
				'core-ooo':             sum([ getpower(core, index, 'Execution Unit/Instruction Scheduler')
									  + getpower(core, index, 'Execution Unit/Register Files')
									  + getpower(core, index, 'Execution Unit/Results Broadcast Bus')
									  + getpower(core, index, 'Renaming Unit')
									  for index,core in enumerate(power_dat['Core'])
									]),
				'core-ifetch':      sum([ getpower(core, index, 'Instruction Fetch Unit/Branch Predictor')
									  + getpower(core, index, 'Instruction Fetch Unit/Branch Target Buffer')
									  + getpower(core, index, 'Instruction Fetch Unit/Instruction Buffer')
									  + getpower(core, index, 'Instruction Fetch Unit/Instruction Decoder')
									  for index,core in enumerate(power_dat['Core'])
									]),
				'core-icache':           sum([ getpower(core, index, 'Instruction Fetch Unit/Instruction Cache') for index, core in enumerate(power_dat['Core']) ]),
				'core-dcache':           sum([ getpower(core, index, 'Load Store Unit/Data Cache') for index,core in enumerate(power_dat['Core'] )]),
				'core-alu-complex': sum([ getpower(core, index, 'Execution Unit/Complex ALUs') for index,core in enumerate(power_dat['Core']) ]),
				'core-alu-fp':      sum([ getpower(core, index, 'Execution Unit/Floating Point Units') for index,core in enumerate(power_dat['Core'] )]),
				'core-alu-int':     sum([ getpower(core, index, 'Execution Unit/Integer ALUs') for index,core in enumerate(power_dat['Core']) ]),
				'core-mem':         sum([ getpower(core, index, 'Load Store Unit/LoadQ')
									  + getpower(core, index, 'Load Store Unit/StoreQ')
									  + getpower(core, index, 'Memory Management Unit')
									  for index,core in enumerate(power_dat['Core'])
									]),
			}
			#data['other'] = getpower(power_dat["Processor"]) -  (sum(data.values()))# - data['dram'])
		else:
			data = {
				'l2':               5 * getpower(power_dat['Core'][core], -1, 'L2'), # private L2
				'core-ooo':         getpower(power_dat['Core'][core], -1, 'Execution Unit/Instruction Scheduler')
									  + getpower(power_dat['Core'][core], -1, 'Execution Unit/Register Files')
									  + getpower(power_dat['Core'][core], -1, 'Execution Unit/Results Broadcast Bus')
									  + getpower(power_dat['Core'][core], -1, 'Renaming Unit'),
				'core-ifetch':      getpower(power_dat['Core'][core], -1, 'Instruction Fetch Unit/Branch Predictor')
									  + getpower(power_dat['Core'][core], -1, 'Instruction Fetch Unit/Branch Target Buffer')
									  + getpower(power_dat['Core'][core], -1, 'Instruction Fetch Unit/Instruction Buffer')
									  + getpower(power_dat['Core'][core], -1, 'Instruction Fetch Unit/Instruction Decoder'),
				'core-icache':      getpower(power_dat['Core'][core], -1, 'Instruction Fetch Unit/Instruction Cache'),
				'core-dcache':      getpower(power_dat['Core'][core], -1, 'Load Store Unit/Data Cache'),
				'core-alu-complex': getpower(power_dat['Core'][core], -1, 'Execution Unit/Complex ALUs'),
				'core-alu-fp':      getpower(power_dat['Core'][core], -1, 'Execution Unit/Floating Point Units'),
				'core-alu-int':     getpower(power_dat['Core'][core], -1, 'Execution Unit/Integer ALUs'),
				'core-mem':         getpower(power_dat['Core'][core], -1, 'Load Store Unit/LoadQ')
									  + getpower(power_dat['Core'][core], -1, 'Load Store Unit/StoreQ')
									  + getpower(power_dat['Core'][core], -1, 'Memory Management Unit'),
			}
		return data

	onlyfiles = [ f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir,f)) ]

	WORKER_THREADS = 1
	power_threads = [None] * len(onlyfiles)
	pt_results = [None] * WORKER_THREADS
	power = {}

	#TODO: Mutlithreaded McPAT invocation occasionally causes DB corruption
	# disabled for now
	timestamps = stats.itervalues().next().keys()
	START_TIME = timestamps[0]
	pool = ThreadPool(processes=WORKER_THREADS)
	for i in range(0, len(onlyfiles), WORKER_THREADS):
		print "launching mcpat thread"
		for j in range(0,WORKER_THREADS):
			if (i + j) < len(onlyfiles):
				pt_results[j] = pool.apply_async(mcpat_run, (input_dir + onlyfiles[i + j],mcpatdir))
		for j in range(0,WORKER_THREADS):
			if (i + j) < len(onlyfiles):
				power_threads[i + j]     = pt_results[j].get()
		print WORKER_THREADS, " mcpat runs finished" , i

	for i,files in enumerate(onlyfiles):
	  result = re.findall('\_(.*?)\.', files)
	  timestamp = float(result[0]) + START_TIME
	  power[timestamp] = {}
	  components = power_threads[i].split('*'*89)[2:-1]

	  # Parse output
	  power_dat = {}
	  for component in components:
		lines = component.strip().split('\n')
		componentname = lines[0].strip().strip(':')
		values = {}
		prefix = []; spaces = []
		for line in lines[1:]:
		  if not line.strip():
			continue
		  elif '=' in line:
			res = re.match(' *([^=]+)= *([-+0-9.e]+)(nan)?', line)
			if res:
			  name = ('/'.join(prefix + [res.group(1)])).strip()
			  if res.groups()[-1] == 'nan':
				# Result is -nan. Happens for instance with 'Subthreshold Leakage with power gating'
				# on components with 0 area, such as the Instruction Scheduler for in-order cores
				value = 0.
			  else:
				try:
				  value = float(res.group(2))
				except:
				  print >> sys.stderr, 'Invalid float:', line, res.groups()
				  raise
			  values[name] = value
		  else:
			res = re.match('^( *)([^:(]*)', line)
			if res:
			  j = len(res.group(1))
			  while(spaces and j <= spaces[-1]):
				spaces = spaces[:-1]
				prefix = prefix[:-1]
			  spaces.append(j)
			  name = res.group(2).strip()
			  prefix.append(name)
		if componentname in ('Core', 'L2', 'L3'):
		  # Translate whatever level we used for NUCA back into NUCA
		  outputname = componentname
		  if outputname not in power_dat:
			power_dat[outputname] = []
		  power_dat[outputname].append(values)
		else:
		  assert componentname not in power_dat
		  power_dat[componentname] = values

		if not power_dat:
			raise ValueError('No valid McPAT output found')
		
	  # Now, we will massage the power consumption based on how idle/active the core was for this quanta of time
	  # For core level stats, we need to merge all the HW_Threads into their shared physical resources
	  # scale represents precent active
	  threads_per_core = HW_THREADS / CORES
	  core_id = 0
	  active = []
	  for k in range(0,CORES,1):
		active.append(0)
		active[k] =max([stats["CPU" + str(j)][timestamp]["busy_cycles"]  for j in range(k, HW_THREADS, CORES)]) / 2400000000.0
		
	  # Plot stack
	  print_stack = 1
	  power[timestamp]["TOTAL"] = {}		
	  power[timestamp]["TOTAL"]["static"] = 0

	  # TODO: this is very primitive, need a better way to model idle states
          for k in range(0,CORES,1):
		power[timestamp]["CPU" + str(k)] = {}		
	  	power[timestamp]["CPU" + str(k)]["dynamic"] = power_stack(power_dat, active, "dynamic", k) 
	  	power[timestamp]["CPU" + str(k)]["static"] = active[k] * 2.2 + (1-active[k]) * 1.00
	  	power[timestamp]["TOTAL"]["static"] += active[k] * 2.2 + (1-active[k]) * 1.00

	  power[timestamp]["TOTAL"]["dynamic"] = power_stack(power_dat, active, "dynamic", "all")  

	return power
  
  # Run in standalone script mode
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Runs McPAT and reports results")
    parser.add_argument("input_dir", help="directory containg McPAT inputs")
    parser.add_argument("mcpatdir", help="directory containing McPAT")
    parser.add_argument("stats", help="stats dictionary")
    parser.add_argument("cores", help="hw cores")
    parser.add_argument("threads", help="threads per core")
    args = parser.parse_args()
    run_mcpat(args.input_dir, args.mcpatdir, args.stats, args.cores, args.threads)
