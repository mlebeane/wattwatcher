WattWatcher: Power Estimation Framework for Emerging Workloads
==============================================================
Current version: 0.01

WattWatcher is a collection of scripts that wrap around the Linux perf
tool and the McPAT[1] framework to allow the estimation of power and energy
from performance counters in real hardware.

Getting started
===========
You will need to install perf and Berkeley DB executables and headers before
getting started with WattWatcher.

1. Enter the fast_mcpat subdirectory and build in accordance with the README.

2. Create a mapping file in the counters_list/ directory from template.txt.
This file must correlate a perf event to each of the events listed in the
template.  We include two examples for Haswell and Sandy Bridge machines.
Statistics related to L3 caches and floating point units are optional.

3. Create a template McPAT XML file detailing all the microarchitectural
characteristics of the machine and place it in the mcpat_procs folder.  
Only hardware constants need to be specified in this file, runtime statistics
will be populated by WattWatcher and can be left at their default values.  
This file must have the same name as the counter mapping file, with a 
different extension (xml vs txt).  For full details on  creating this file,
see the McPAT subdirectory README.  We include two samples for our Haswell and
Sandy Bridge laptop form factors.

4. Look at the included sample run script in the run_scripts directory to see
how to run WattWatcher.  Set WATTWATCHER_HOME and the application to profile as
done in these scripts.  Then invoke the following functions in the run script:

run_perf <hostname of SUT> <counter file name> <sampling interval (in seconds)>

<launch workload to profile>

marshal_perf <hostname of SUT> <results_dir> <results_name> 
	     <microarch name> <sampling interval (in seconds)>
	     <TSC frequency> <HW Cores> <Threads per HW core>

The <hostname of the SUT> can be replaced with "local" to run locally on the 
same node.

The above commands will place the results in the <results_dir> indicated.  By
default, the results directory will contain a number of files reporting the 
performance counters collected from perf and a power breakdown of the system
at each sampling interval.  The results directory will contain the following
files and folders

- mcpat/ : Folder containing the mcpat output files for each sampling period
- cntrs_processed_CPU*.csf:  Organized counters for each logical core
- mcpat_*.csv: WattWatcher results for each physical core
- <results_name>-counters.csv: Raw counter information

Troubleshooting
===========

Sometimes the Berkeley DB database can become corrupt.  To resolve this 
problem, please delete the database files (by default created in /tmp).

WattWatcher uses the '-I' option in perf to collect counters at a user defined
sampling interval.  This option is unavailable in some older kernels.

Order of magnitude errors or nonsensical results reported by McPAT tend to
come from one of two primary places:

Major Statistics Errors:
Total Cycles/Instructions: Please verify that the total number of elapsed cycles
is roughly correct for the sampling interval.

Major Configuration Errors:
Voltage:  Please verify that the voltage is correct.  
Device Type: Verify that the device type is correct. A server would be type 0.  
See McPAT documentation for more information.
Core Tech Node: Please verify the core tech node (ex: 45nm)


Disclaimer
===========
For feedback or questions, please email:

mlebeane@utexas.edu
songshuang1990@gmail.com 

This version of WattWatcher is missing a few features that 
are planned for inclusion in the full release.

- No DVFS Support: WattWatcher does not monitor changes to
operating voltage and frequency.  It will provide results
based on the voltage and frequency provided in the McPAT configuration
file. A simplistic accounting of leakage power is provided based on
active vs idle cycles, but this will not reflect C-State policies
on real machines.  

- No online monitoring mode: WattWatcher is currently configured to
provide offline analysis/post processing support.

- No multisocket support: WattWatcher assumes that all cores in
the system belong to the same socket.

Acknowledgments
==========
This tool uses code from McPAT[1] and some McPAT integration code from the
Sniper simulator team[2].  

References
===========
[1] Sheng Li, Jung Ho Ahn, Richard D. Strong, Jay B. Brockman, Dean M. Tullsen, 
and Norman P. Jouppi. 2009. McPAT: an integrated power, area, 
and timing modeling framework for multicore and manycore architectures.
In Proceedings of the 42nd Annual IEEE/ACM International Symposium on 
Microarchitecture (MICRO 42).
 
[2] Wim Heirman, Souradip Sarkar, Trevor E. Carlson, Ibrahim Hur, and 
Lieven Eeckhout. 2012. Power-aware multi-core simulation for early design 
stage hardware/software co-optimization. In Proceedings of the 21st 
international conference on Parallel architectures and compilation 
techniques (PACT '12).
