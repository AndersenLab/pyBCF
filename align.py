#/usr/bin/python
import sys, os
from ast import literal_eval
from utils import *
from commands import *
import tempfile
import glob

# ======= #
# Command #
# ======= #

bwa = """bwa {bwa_command} -R '{RG_header}' {bwa_options} {reference} {FQ1} {FQ2} | samtools view -bhu - > {OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.unsorted.bam
         samtools sort -O bam -T {tmpname} {OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.unsorted.bam > {OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.sorted.bam"""


#====================#
# Load Configuration #
#====================#

opts = literal_eval(sys.argv[2])
config, log, c_log = load_config_and_log(sys.argv[1], "align")
OPTIONS = config.OPTIONS
COMMANDS = config.COMMANDS
align = COMMANDS.align # Pulls out alignment types.

#=========================#
# Setup Read Group Header #
#=========================#

# Set up Read Group String for alignment (with bwa)
fqs = [os.path.split(opts["FQ1"])[1], os.path.split(opts["FQ2"])[1]]
ID = get_fq_ID(fqs)
RG_header = construct_RG_header(ID, opts)

#=====#
# BWA #
#=====#

if "bwa" in align:
	bwa_command, bwa_options = format_command(align["bwa"])
	reference = glob.glob("{script_dir}/genomes/{OPTIONS.reference}/*gz".format(**locals()))[0]
	tmpname = os.path.split(tempfile.mktemp(prefix=ID))[1]
	FQ1 = opts["FQ1"]
	FQ2 = opts["FQ2"]

	# Create Directories
	makedir(OPTIONS["analysis_dir"])
	makedir(OPTIONS["analysis_dir"] + "/bam")
	completed_bam = "{OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.bam".format(**locals())
	unsorted_bam = "{OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.unsorted.bam".format(**locals())
	if not file_exists(completed_bam) and not file_exists(unsorted_bam):
		comm = bwa.format(**locals())
		command(comm, c_log)
		if align.alignment_options.remove_temp == True:
			file_to_delete = "rm {unsorted_bam}".format(**locals())
			command(file_to_delete, c_log)
	else:
		log.info("SKIPPING: " + completed_bam + " exists; no alignment.")


#=================#
# Mark Duplicates #
#=================#

if "picard" in align:
	if "markduplicates" in align.picard:
		if align.picard.markduplicates == True:
			dup_report = "{OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.duplicate_report.txt".format(**locals())
			if not file_exists(dup_report) or not file_exists(completed_bam):
				comm = mark_dups.format(**locals())
				log.info("Removing Duplicates: %s.bam" % ID)
				c_log.add(comm)
				command(comm, c_log)
				# Remove Sort tempfile
				if align.alignment_options.remove_temp == True:
					file_to_delete = "rm {OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.sorted.bam".format(**locals())
					command(file_to_delete, c_log)
			else:
				log.info("SKIPPING: " + dup_report + " exists; Skipping.")
else:
	# If duplicates are not being marked, move files
	move_file = """mv {OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.sorted.bam {OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.bam""".format(**locals())
	command(move_file, c_log)
