#!/usr/bin/env python3
"""
run_pretext_extensions.py
=========================
Add long-read coverage, assembly gaps, and telomere tracks to an existing
PretextMap file.

Steps
-----
1. Map long reads to the assembly with minimap2, sort and index the BAM.
2. Compute a genome-coverage bedgraph with bedtools genomecov.
3. Extract assembly gaps with gfastats and convert to bedgraph.
4. Scan for telomeric repeats with telo_scan.py (bundled in scripts/).
5. Inject all non-empty bedgraphs into the .pretext (and optionally .HR.pretext)
   file using PretextGraph.

Usage example
-------------
    python run_pretext_extensions.py \\
        --assembly genome.fa \\
        --pretext  assembly.pretext \\
        --hr-pretext assembly.HR.pretext \\
        --reads    reads.ont.fastq.gz \\
        --read-type ont \\
        --telomere-motif TTAGGG \\
        --threads  16 \\
        --outdir   pretext_out/
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent / "scripts"
TELO_SCAN   = SCRIPTS_DIR / "telo_scan.py"
GAP_BG_SH   = SCRIPTS_DIR / "gap_bed2bedgraph.sh"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: str, *, desc: str = "", check: bool = True) -> subprocess.CompletedProcess:
    if desc:
        log.info(desc)
    log.debug("CMD: %s", cmd)
    return subprocess.run(cmd, shell=True, check=check)


def nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        log.error("Required tool not found on PATH: %s", name)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def map_long_reads(assembly: Path, reads: Path, read_type: str,
                   outdir: Path, threads: int) -> Path:
    preset   = "map-ont" if read_type == "ont" else "map-hifi"
    bam_raw  = outdir / "lr_mapped.bam"
    bam_sort = outdir / "lr_sorted.bam"

    run(
        f"minimap2 -ax {preset} -t {threads} {assembly} {reads} "
        f"| samtools view -Sb - "
        f"| samtools sort -@ {threads} -o {bam_sort} -",
        desc=f"Mapping long reads ({preset}) and sorting BAM …",
    )
    run(f"samtools index -c {bam_sort}", desc="Indexing BAM …")
    return bam_sort


def make_coverage_bg(bam: Path, outdir: Path) -> Path:
    bg = outdir / "lr_coverage.bg"
    run(
        f"bedtools genomecov -bga -ibam {bam} > {bg}",
        desc="Computing long-read coverage bedgraph …",
    )
    return bg


def make_gaps_bg(assembly: Path, outdir: Path) -> Path:
    gaps_bed = outdir / "gaps.bed"
    gaps_bg  = outdir / "gaps.bg"
    run(
        f"gfastats -b gaps {assembly} > {gaps_bed}",
        desc="Extracting assembly gaps …",
    )
    run(
        f"cat {gaps_bed} | bash {GAP_BG_SH} > {gaps_bg}",
        desc="Converting gaps BED to bedgraph …",
    )
    return gaps_bg


def make_telomere_bg(assembly: Path, motif: str, outdir: Path,
                     threads: int, window: int, min_tandem: int) -> Path:
    prefix   = outdir / "telo"
    combined = outdir / f"telo.{motif.upper()}.5p+3p_telomere.bg"
    run(
        f"python {TELO_SCAN} -i {assembly} -m {motif} "
        f"-o {prefix} --threads {threads} "
        f"--window {window} --min-tandem {min_tandem} --no-hits",
        desc=f"Scanning for telomeric repeats ({motif}) …",
    )
    return combined


def inject_tracks(pretext_in: Path, pretext_out: Path,
                  tracks: dict[str, Path]) -> None:
    """Copy pretext_in to pretext_out then pipe each non-empty bedgraph in."""
    shutil.copy2(pretext_in, pretext_out)
    for name, bg in tracks.items():
        if nonempty(bg):
            log.info("Adding track '%s' from %s …", name, bg.name)
            run(f"cat {bg} | PretextGraph -i {pretext_out} -n \"{name}\"")
        else:
            log.warning("Skipping track '%s' — bedgraph is empty or missing.", name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Add coverage, gap, and telomere tracks to a PretextMap file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required
    p.add_argument("--assembly",  required=True, type=Path, help="Assembly FASTA (.fa / .fa.gz)")
    p.add_argument("--pretext",   required=True, type=Path, help="Input .pretext file")

    # Reads (optional together)
    p.add_argument("--reads",     type=Path, default=None,
                   help="Long reads FASTQ (.fastq.gz). Omit to skip the coverage track.")
    p.add_argument("--read-type", choices=["ont", "hifi"], default=None,
                   help="Read technology — required when --reads is given.")

    # Optional pretext
    p.add_argument("--hr-pretext", type=Path, default=None,
                   help="High-resolution .HR.pretext file (optional).")

    # Telomere options
    p.add_argument("--telomere-motif", default=None,
                   help="Telomeric repeat motif (5′→3′, forward strand), e.g. TTAGGG. "
                        "Required unless --skip-telomeres is set. "
                        "If the motif is unknown, run tidk explore first (see README).")
    p.add_argument("--telo-window",    type=int, default=10000,
                   help="Window size (bp) for telo_scan.py.")
    p.add_argument("--telo-min-tandem", type=int, default=2,
                   help="Minimum consecutive copies for telo_scan.py.")

    # General
    p.add_argument("--threads", type=int, default=8, help="CPU threads.")
    p.add_argument("--outdir",  type=Path, default=Path("pretext_extensions_out"),
                   help="Output directory (created if absent).")
    p.add_argument("--skip-coverage",  action="store_true", help="Skip LR coverage track.")
    p.add_argument("--skip-gaps",      action="store_true", help="Skip gaps track.")
    p.add_argument("--skip-telomeres", action="store_true",
                   help="Skip telomere scanning entirely. Only use this when the organism "
                        "is known to lack canonical telomeres (e.g. most Diptera). "
                        "The resulting pretext will have no telomere track.")
    p.add_argument("-v", "--verbose",  action="store_true", help="Show debug output.")

    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate reads/read-type pairing
    if args.reads and not args.read_type:
        log.error("--read-type (ont|hifi) is required when --reads is given.")
        sys.exit(1)
    if args.read_type and not args.reads:
        log.error("--reads is required when --read-type is given.")
        sys.exit(1)

    want_coverage = bool(args.reads) and not args.skip_coverage

    # Validate telomere options
    if args.telomere_motif and args.skip_telomeres:
        log.warning("Both --telomere-motif and --skip-telomeres were given. "
                    "--skip-telomeres takes precedence; the motif will be ignored.")

    if not args.telomere_motif and not args.skip_telomeres:
        log.error(
            "No telomere motif provided and --skip-telomeres was not set.\n\n"
            "  If the telomeric repeat is unknown, discover it first with tidk explore:\n"
            "\n"
            "      tidk explore -x 12 -m 5 \\\n"
            "          --output explore --dir tidk_out/ \\\n"
            "          --extension bedgraph --fasta %s\n"
            "\n"
            "  Inspect tidk_out/explore_telomeric_repeat_windows.bedgraph and the\n"
            "  log to identify the dominant motif, then rerun with:\n"
            "\n"
            "      --telomere-motif <MOTIF>\n"
            "\n"
            "  If the organism genuinely lacks canonical telomeres (e.g. most Diptera),\n"
            "  suppress this check with --skip-telomeres.\n",
            args.assembly,
        )
        sys.exit(1)

    if args.skip_telomeres:
        log.warning("=" * 60)
        log.warning("WARNING: telomere scanning is disabled (--skip-telomeres).")
        log.warning("The output pretext file will have NO telomere track.")
        log.warning("Only use this flag if the organism is known to lack")
        log.warning("canonical telomeres (e.g. most Diptera).")
        log.warning("=" * 60)

    # Check required tools
    for tool in ["minimap2", "samtools", "bedtools", "gfastats", "PretextGraph"]:
        if tool == "minimap2" and not want_coverage:
            continue
        if tool in ("minimap2", "samtools", "bedtools") and not want_coverage:
            continue
        if tool == "gfastats" and args.skip_gaps:
            continue
        require_tool(tool)

    args.outdir.mkdir(parents=True, exist_ok=True)

    # ---- Step 1 & 2: long-read coverage ----
    coverage_bg = None
    if want_coverage:
        bam = map_long_reads(args.assembly, args.reads, args.read_type,
                             args.outdir, args.threads)
        coverage_bg = make_coverage_bg(bam, args.outdir)

    # ---- Step 3: gaps ----
    gaps_bg = None
    if not args.skip_gaps:
        gaps_bg = make_gaps_bg(args.assembly, args.outdir)

    # ---- Step 4: telomeres ----
    telo_bg = None
    if not args.skip_telomeres:
        telo_bg = make_telomere_bg(
            args.assembly, args.telomere_motif, args.outdir,
            args.threads, args.telo_window, args.telo_min_tandem,
        )

    # ---- Step 5: inject into pretext ----
    tracks: dict[str, Path] = {}
    if gaps_bg:
        tracks["gap"] = gaps_bg
    if telo_bg:
        tracks["telomere"] = telo_bg
    if coverage_bg:
        tracks["coverage"] = coverage_bg

    stem      = args.pretext.stem
    out_pret  = args.outdir / f"{stem}.extensions.pretext"
    inject_tracks(args.pretext, out_pret, tracks)

    if args.hr_pretext:
        hr_stem     = args.hr_pretext.stem
        out_hr_pret = args.outdir / f"{hr_stem}.extensions.pretext"
        inject_tracks(args.hr_pretext, out_hr_pret, tracks)

    log.info("Done. Output written to: %s", args.outdir)


if __name__ == "__main__":
    main()
