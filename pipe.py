#!/usr/bin/env python
"""pyPipeline

Usage:
  pipe.py trim <config>
  pipe.py align <config> [options]
  pipe.py snps (individual|joint) <config> [options]
  pipe.py transposons <config>
  pipe.py samplefile <config>
  pipe.py genome [<name>]
  pipe.py test <config> [options]

Options:
  -h --help     Show this screen.
  --version     Show version.

"""
from docopt import docopt
from utils import *
from utils.constants import *
from utils.configuration import *
from utils.genomes import *
import csv
from pprint import pprint as pp

if __name__ == '__main__':
    opts = docopt(__doc__, version='pyPipeline')
    print opts

    # Setup configuration
    if opts["<config>"] is not None:
        config_file = opts["<config>"]
        cf = config(opts["<config>"])
        # Create new sample file
        if opts["samplefile"] is True:
            if file_exists(cf.sample_file):
                msg("Sample file already exists","error")
            sf = cf.get_sample_file()
            sf.new_sample_file()

    # sample file
    sf = cf.get_sample_file()

    #==================#
    # Genome Retrieval #
    #==================#

    if opts["genome"] is True:
        if opts["<name>"] is not None:
            fetch_genome(opts["<name>"])
        else:
            list_genomes()
        exit(0)

    #=======#
    # Setup #
    #=======#

    analysis_types = ["trim", "align", "merge", "snps", "indels", "test", "transposons"]
    analysis_type = [x for x in opts if opts[x] == True and x in analysis_types][0]

    #======================#
    # Debug (testing) mode #
    #======================#
    """
    if OPTIONS.debug == True:
        debug_fq_dir = "{OPTIONS.fastq_dir}/DEBUG_FQ".format(**locals())
        makedir(debug_fq_dir)
        bam_dir = "{OPTIONS.analysis_dir}/debug".format(**locals())
        eav_file = "{OPTIONS.analysis_dir}/{OPTIONS.stat_dir}/DEBUG_eav.txt".format(**locals())
    """
    cf.log("#=== Beginning Analysis ===#")
    cf.log("Running " + opts["<config>"])

    #======#
    # Trim #
    #======#

    if analysis_type == "trim":
        # Trim Nextera Adapters
        pass

    #===========#
    # Alignment #
    #===========#

    elif analysis_type == "align":
        cf.log("Performing Alignment")
        for bam in sf.check_bams():
            # Check merged bam
            dependency_list = []
            if bam["bam_merged_exists_and_RG_correct"] is False:
                # Remove merged bam if it exists (RG is wrong)
                if file_exists(bam["bam_merged_filename"]):
                    cf.log("merged bam %s exists or incorrect read group." %
                    bam["bam_merged_filename"])
                    cf.command("rm %s" % bam["bam_merged_filename"])
                # Check individual bams
                for ind_bam, ind_bam_exists, fq, RG, ID in zip(bam["bam_ind_filename"],
                                                                   bam["bam_ind_exists_and_RG_correct"],
                                                                   bam["fq"],
                                                                   bam[r"raw_RG"],
                                                                   bam["ID"]):
                    if ind_bam_exists is False:
                        fq_pair = {"fq1": fq[0], "fq2": fq[1], "ID": ID, "RG": RG, "SM": bam["SM"]}
                        align = "{run} {script_dir}/align.py {config_file} \"{fq_pair}\"".format(**locals())
                        jobid = cf.submit_job(align,
                                              analysis_type=analysis_type,
                                              log_name=ID)
                        dependency_list.append(jobid)
                    else:
                        print("IND")
                # Merge Bams
                merge_bams = "{run} {script_dir}/merge_bams.py {config_file} \"{bam}\"".format(**locals())
                jobid = cf.submit_job(merge_bams,
                                      log_name=bam.SM,
                                      analysis_type=analysis_type,
                                      dependencies=dependency_list,
                                      dependency_type="afterok")

    #=============#
    # SNP Calling #
    #=============#
    elif analysis_type == "snps" and opts["individual"] == True:
        #
        # Individual - Needs to be run twice to generate union output
        #
        # Get list of bams
        cf.log("Performing Variant Calling")
        # Construct Sample Set
        dependency_list = []
        for caller in cf.snp_callers:
            union_vcf_file = "{cf.vcf_dir}/{cf.config_name}.ALL.{caller}.union.vcf.gz".format(**locals())
            if check_seq_file(union_vcf_file) is False:
                for bam in sf.check_bams():
                    if bam["bam_merged_exists_and_RG_correct"] is False:
                        msg("Bam File or index does not exist: %s" % bam["bam_merged_filename"], "error")
                    else:
                        dependency_list = []
                        complete_individual = "{cf.vcf_dir}/{bam.SM}.ALL.{caller}.union.vcf.gz".format(**locals())
                        print complete_individual
                        if check_seq_file(complete_individual) is False:
                            print "YES"
                            call_snps = """{run} {output_dirs} {script_dir}/call_snps_individual.py {config_file} \"{bam}\"""".format(**locals())
                            jobid = cf.submit_job(call_snps,
                                                  log_name=bam.SM,
                                                  analysis_type=analysis_type,
                                                  dependency_type="afterok")
                            dependency_list.append(jobid)
        # Merge individual vcfs
        if cf.snps.snp_options.merge_individual_vcfs == True:
            merge_snps = """{run} {script_dir}/merge_vcfs_individual.py {config_file}""".format(**locals())
            cf.submit_job(merge_snps,
                      log_name="merge_snps",
                      analysis_type=analysis_type,
                      dependencies=dependency_list,
                      dependency_type="afterok")

    elif analysis_type == "snps" and opts["joint"] == True:
        #
        # Joint
        #
        dependency_list = []
        for caller in cf.snp_callers:
            joint_vcf_file = "{cf.vcf_dir}/{cf.config_name}.{caller}.joint.vcf.gz".format(**locals())
            joint_vcf_file_exists = check_seq_file(joint_vcf_file)
            for chunk in cf.chunk_genome():
                # Check that chunk does not exist.
                chunk_sanitized = chunk.replace(":","_")
                vcf_file = "{cf.vcf_dir}/TMP.{cf.config_name}.joint.{chunk_sanitized}.{caller}.vcf.gz".format(**locals())
                if not check_seq_file(vcf_file):
                    call_snps = """{run} {script_dir}/call_snps_joint.py {config_file} \"{chunk}\"""".format(**locals())
                    jobid = cf.submit_job(call_snps,
                                          log_name=chunk,
                                          analysis_type=analysis_type,
                                          dependency_type="afterok")
                    dependency_list.append(jobid)
        if not all(joint_vcf_file_exists):
            merge_snps = """{run} {script_dir}/concat_vcfs_joint.py {config_file}""".format(**locals())
            cf.submit_job(merge_snps,
                          log_name="Merge Joint",
                          analysis_type=analysis_type,
                          dependencies=dependency_list,
                          dependency_type="afterok")
        else:
            print("Merged File Already Exists")
    elif analysis_type == "test":
        r = "{run} {script_dir}/call_snps_individual.py {config_file} '[1,2,3]'".format(**locals())
        os.system(r)

    
    elif analysis_type == "transposons":
        bam_set = []
        for fq in csv.DictReader(sample_file, delimiter='\t', quoting=csv.QUOTE_NONE):
            if fq["RUN"] != "NO":
                SM = fq["SM"]
                bam_set.append(SM)
                bam_file = "{bam_dir}/{SM}.bam".format(**locals())
        bam_set = set(bam_set)
        # Has vcf been called for given snp caller?
        dependency_list = []
        for SM in bam_set:
            call_transposons = """{run} {script_dir}/call_transposons.py {config_file} \"{SM}.bam\"""".format(**locals())
            print call_transposons
            jobid = submit_job(call_transposons)
            #dependency_list.append(jobid)

