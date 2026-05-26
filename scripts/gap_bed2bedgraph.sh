#!/usr/bin/env bash
# Convert gfastats gap BED (chrom, start, end) to bedgraph with score 100.
# Usage: gfastats -b gaps assembly.fa | gap_bed2bedgraph.sh > gaps.bg
gawk '{print $1"\t"$2"\t"$3"\t100"}'
