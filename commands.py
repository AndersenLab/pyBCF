#usr/bin/python

# Align with BWA
bwa = """bwa {bwa_command} -R '{RG_header}' {bwa_options} {reference} {FQ1} {FQ2} | samtools view -bhu - > {OPTIONS.analysis_dir}/bam/{ID}.unsorted.bam
         samtools sort -O bam -T {tmpname} {OPTIONS.analysis_dir}/bam/{ID}.unsorted.bam > {OPTIONS.analysis_dir}/bam/{ID}.sorted.bam"""

samtools_command = """ """

freebayes_command = """ """
