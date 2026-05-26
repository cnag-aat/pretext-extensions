# pretext-extensions

Add long-read coverage, assembly gaps, and telomere tracks to an existing
[PretextMap](https://github.com/wtsi-hpag/PretextMap) file.

Extracted from the [CLAWS](https://github.com/cnag-aat/CLAWS) genome assembly
pipeline as a self-contained tool for collaborators who already have a `.pretext`
file and want to annotate it — without running the full pipeline.

## What it does

| Track | Tool | Input |
|-------|------|-------|
| Long-read coverage | minimap2 → samtools → bedtools genomecov | reads + assembly |
| Assembly gaps | gfastats → awk | assembly |
| Telomeres | [telo_scan.py](scripts/telo_scan.py) | assembly |

All tracks are injected into a copy of your `.pretext` (and optionally `.HR.pretext`)
file using `PretextGraph`.

## Setup

```bash
conda env create -f environment.yml
conda activate pretext-extensions
```

## Usage

```bash
python run_pretext_extensions.py \
    --assembly  genome.fa \
    --pretext   assembly.pretext \
    --hr-pretext assembly.HR.pretext \   # optional
    --reads     reads.ont.fastq.gz \
    --read-type ont \                    # ont | hifi
    --telomere-motif TTAGGG \
    --threads   16 \
    --outdir    pretext_out/
```

Output files land in `--outdir`:

```
pretext_out/
├── assembly.extensions.pretext        # annotated copy
├── assembly.HR.extensions.pretext     # (if --hr-pretext given)
├── lr_sorted.bam                      # long-read mapping
├── lr_coverage.bg
├── gaps.bed
├── gaps.bg
└── telo.TTAGGG.5p+3p_telomere.bg
```

### Skip individual tracks

```bash
# gaps + telomeres only (no reads available)
python run_pretext_extensions.py \
    --assembly genome.fa \
    --pretext  assembly.pretext \
    --skip-coverage

# coverage + gaps only
python run_pretext_extensions.py \
    --assembly genome.fa --reads reads.hifi.fastq.gz --read-type hifi \
    --pretext  assembly.pretext \
    --skip-telomeres
```

### All options

```
--assembly          Assembly FASTA (required)
--pretext           Input .pretext file (required)
--hr-pretext        Input .HR.pretext file (optional)
--reads             Long reads FASTQ (required unless --skip-coverage)
--read-type         ont | hifi (required with --reads)
--telomere-motif    Telomeric repeat motif, 5′→3′ forward strand, e.g. TTAGGG (required)
--telo-window       Window size in bp for telo_scan.py (default: 10000)
--telo-min-tandem   Min consecutive copies for telo_scan.py (default: 2)
--threads           CPU threads (default: 8)
--outdir            Output directory (default: pretext_extensions_out/)
--skip-coverage     Skip the long-read coverage track
--skip-gaps         Skip the assembly gaps track
--skip-telomeres    Skip the telomere track
-v / --verbose      Show debug output
```

## Dependencies

All tools are installed via the conda environment:

| Tool | Version | Purpose |
|------|---------|---------|
| minimap2 | ≥ 2.24 | Long-read alignment |
| samtools | ≥ 1.15 | BAM sorting and indexing |
| bedtools | ≥ 2.30 | Coverage bedgraph |
| gfastats | ≥ 1.3.10 | Gap extraction |
| pretextgraph | 0.0.9 | Inject tracks into .pretext |
| tidk | ≥ 0.2.65 | Telomere motif discovery (`tidk explore`) |
| python | ≥ 3.8 | Wrapper + telo_scan.py |

`telo_scan.py` is bundled in `scripts/` and requires only the Python standard
library.
