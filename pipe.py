#!/usr/bin/env python
"""pyPipeline

Usage:
  pipe.py trim <config>
  pipe.py align <config> [--debug]
  pipe.py samplefile <filename/dir>
  pipe.py genome [<name>]
  pipe.py test <config>

Options:
  -h --help     Show this screen.
  --version     Show version.

"""
from docopt import docopt
import glob
from utils import *
from utils.genomes import *
import csv

def check_fqs(fq):
    if not file_exists(fq["FQ1"]) or not file_exists(fq["FQ2"]):
        raise Exception("File Missing; Check: {fq1}, {fq2}".format(fq1=fq["FQ1"], fq2=fq["FQ2"]))

if __name__ == '__main__':
    opts = docopt(__doc__, version='pyPipeline')
    print opts

    #=======#
    # Setup #
    #=======#

    config_file = opts["<config>"]
    analysis_dir = os.getcwd()

    #
    # Add Checks here for required options
    #

    #==================#
    # Genome Retrieval #
    #==================#

    if opts["genome"] == True:
        if opts["<name>"] is not None:
            fetch_genome(opts["<name>"])
        else:
            list_genomes()
        exit()

    #=================#
    # New Sample File #
    #=================#

    """
        Create a sample file where Library, Sample, and Platform info can be added.
        Optionally update an analysis file
    """

    if opts["samplefile"] == True: 
        header = "FQ1\tFQ2\tID\tLB\tSM\tPL\n"
        sample_file = open(opts["<filename/dir>"] + ".txt",'w')
        sample_file.write(header)
        if is_dir(analysis_dir + "/" + opts["<filename/dir>"]):
            # Construct a sample file using the directory info.
            fq_set = glob.glob(opts["<filename/dir>"] + "/*.fq.gz")
            fastq_pairs = zip(sorted([os.path.split(x)[1] for x in fq_set if x.find("1.fq.gz") != -1]), \
                sorted([os.path.split(x)[1] for x in fq_set if x.find("2.fq.gz") != -1]))
            for pair in fastq_pairs:
                ID = get_fq_ID(pair)
                sample_file.write("\t".join(pair) + "\t" + ID + "\n")
        exit()

    #===========#
    # Alignment #
    #===========#

    analysis_types = ["align", "merge", "snps","indels", "test"]
    analysis_type = [x for x in opts if opts[x] == True][0]
    # Load Configuration
    config, log, c_log = load_config_and_log(config_file, analysis_type)
    OPTIONS = config.OPTIONS
    log.info("#=== Beginning Analysis ===#")
    log.info("Running " + opts["<config>"])
    # Running locally or on a cluster
    if opts["--debug"] == True:
        run = "python"
        log.info("Using DEBUG mode")
    else:
        run = "sbatch"

    if analysis_type == "align":
        fq_set = open(config["OPTIONS"]["sample_file"], 'rU')
        log.info("Performing Alignment")
        sample_set = {} # Generate a list of samples.
        bam_white_list = [] # List of bams to keep following alignment; removes extras
        # Construct Sample Set
        for fq in csv.DictReader(fq_set, delimiter='\t', quoting=csv.QUOTE_NONE):
            fq1, fq2 = fq["FQ1"], fq["FQ2"]
            fq["FQ1"] = "{analysis_dir}/{OPTIONS.fastq_dir}/{fq1}".format(**locals())
            fq["FQ2"] = "{analysis_dir}/{OPTIONS.fastq_dir}/{fq2}".format(**locals())
            # Construct Individual BAM Dict
            ID = fq["ID"]
            SM = fq["SM"]
            if SM not in sample_set:
                sample_set[SM] = []
            RG = construct_RG_header(ID, fq).replace("\\t","\t")
            sample_info = {"ID" : ID, "RG": RG, "fq": fq}
            sample_set[SM].append(sample_info)

            # Check that fq's exist before proceeding.
            check_fqs(fq)

        for SM in sample_set.keys():
            # Check the header of the merged bam to see if 
            # current file already exists within
            completed_merged_bam = "{OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{SM}.bam".format(**locals())

            # Check to see if merged bam contains constitutive bams
            if file_exists(completed_merged_bam):
                RG = get_bam_RG(completed_merged_bam)
                RG_ind = [x["RG"] for x in sample_set[SM]]
                if set(RG_ind) != set(RG):
                    # Delete merged Bam, and re-align all individual.
                    log.info("RG do not match; deleting.")
                    remove_file(completed_merged_bam)
                else:
                    log.info("{SM}.bam contains all specified individual bams.".format(**locals()))

            # Align fastq sets
            if not file_exists(completed_merged_bam):
                for seq_run in sample_set[SM]:
                    ID = seq_run["ID"]
                    fq = seq_run["fq"]
                    single_bam = "{OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{ID}.bam".format(**locals())
                    bam_white_list.append(single_bam)
                    # Check single bam RG
                    re_align = False
                    if file_exists(single_bam):
                        current_RG = get_bam_RG(single_bam)[0]
                        single_RG_incorrect = (seq_run["RG"] != current_RG)
                        if (seq_run["RG"] != current_RG):
                            log.info("Readgroup for {single_bam} does not match file; deleting")
                            remove_file(single_bam)
                            remove_file(single_bam + ".bai")
                            re_align = True


                    if not file_exists(single_bam) or re_align :
                        align = "{run} {script_dir}/align.py {config_file} \"{fq}\"".format(**locals())
                        log.info(align)
                        os.system(align)
                    else:
                        log.info("%-50s already aligned individually, skipping" % single_bam)
        #
        # Merging
        #
        for SM in sample_set.keys():  
            completed_merged_bam = "{OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/{SM}.bam".format(**locals())
            bam_white_list.append(completed_merged_bam)
            # Merge Bams for same samples.
            if not file_exists(completed_merged_bam):
                bam_set = [x["ID"] + ".bam" for x in sample_set[SM]]
                bams_to_merge = (SM, bam_set)
                merge_bams = "{run} {script_dir}/merge_bams.py {config_file} \"{bams_to_merge}\"".format(**locals())
                log.info(merge_bams)
                os.system(merge_bams)
            else:
                log.info("%-50s already exists with all individual bams, skipping" % completed_merged_bam)
        
        #
        # Cleanup Old Files
        # 
        bam_dir_files = glob.glob("{OPTIONS.analysis_dir}/{OPTIONS.bam_dir}/*bam".format(**locals()))
        for bam_file in bam_dir_files:
            if bam_file not in bam_white_list:
                remove_file(bam_file)
                remove_file(bam_file + ".bai")


    if analysis_type == "test":
        reference = glob.glob("{script_dir}/genomes/{OPTIONS.reference}/*gz".format(**locals()))[0]
        for i in chunk_genome(3000000, reference):
            print i
        





    
