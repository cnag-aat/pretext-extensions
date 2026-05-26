# pretext-extensions — Session Memory

## What this repo is

A self-contained tool extracted from the [CLAWS](https://github.com/cnag-aat/CLAWS)
genome assembly pipeline. It adds long-read coverage, assembly gap, and telomere
tracks to an existing PretextMap file, for use by collaborators who don't need the
full CLAWS pipeline.

**GitHub:** https://github.com/cnag-aat/pretext-extensions  
**Local:** `/Users/talioto/repositories/pretext-extensions`

---

## Repo structure

```
pretext-extensions/
├── run_pretext_extensions.py   # Python CLI wrapper (main entry point)
├── environment.yml             # Single conda environment
├── scripts/
│   ├── telo_scan.py            # Telomere scanner (bundled from cnag-aat/scripts)
│   └── gap_bed2bedgraph.sh     # awk one-liner: gfastats gap BED → bedgraph
└── README.md
```

---

## What it does (pipeline steps)

1. **Long-read mapping** — minimap2 (`map-ont` or `map-hifi`) → samtools sort → BAM  
   *(skipped if `--bam` is provided)*
2. **Coverage bedgraph** — `bedtools genomecov -bga`
3. **Gaps bedgraph** — `gfastats -b gaps` → `gap_bed2bedgraph.sh` (score = 100)
4. **Telomere bedgraphs** — `telo_scan.py` produces three tracks:
   - `5p_telomere` (forward strand)
   - `3p_telomere` (reverse strand)
   - `telomere` (combined — these are the exact PretextGraph `-n` names)
5. **Inject into pretext** — `PretextGraph` called once per non-empty bedgraph;
   works on both `.pretext` and `.HR.pretext`

---

## Key design decisions

- **telo_scan.py replaces tidk search** for telomere bedgraph generation.
  It is bundled directly in `scripts/` (downloaded from cnag-aat/scripts).
- **tidk is still included in the conda env** (`tidk>=0.2.65`) so users can run
  `tidk explore` to discover unknown motifs before running the main wrapper.
- **`--telomere-motif` is required** (no default). If omitted without
  `--skip-telomeres`, the script exits with a `tidk explore` command the user
  can copy-paste.
- **`--skip-telomeres`** is allowed for organisms with no canonical telomeres
  (e.g. most Diptera) but triggers a loud multi-line warning.
- **`--bam`** accepts a pre-mapped sorted BAM, mutually exclusive with
  `--reads`/`--read-type`.
- **Single conda env** — all tools in one `environment.yml` for simplicity.
- **pretextgraph=0.0.9** pinned (latest on bioconda; `pretext-suite` metapackage
  is stale at 0.0.2 and not used).

---

## Conda environment tools

| Tool | Version | Purpose |
|------|---------|---------|
| minimap2 | ≥ 2.24 | Long-read alignment |
| samtools | ≥ 1.15 | BAM sorting/indexing |
| bedtools | ≥ 2.30 | Coverage bedgraph |
| gfastats | ≥ 1.3.10 | Gap extraction |
| pretextgraph | 0.0.9 | Inject tracks into .pretext |
| tidk | ≥ 0.2.65 | Telomere motif discovery |
| python | ≥ 3.8 | Wrapper + telo_scan.py |

---

## Source of extracted rules (CLAWS)

| Rule | File |
|------|------|
| `align_lr` | `modules/evaluate_assemblies.rules.smk` |
| `get_extension_cov` | `modules/evaluate_assemblies.rules.smk` |
| `get_extension_gaps` | `modules/evaluate_assemblies.rules.smk` |
| `tidk_search` (replaced by telo_scan.py) | `modules/evaluate_assemblies.rules.smk` |
| `add_extensions_pretext` | `modules/hic.rules.smk` |

---

## Commit history

| Hash | Message |
|------|---------|
| `6ef7e55` | Fix PretextGraph track names for telomere strands |
| `a60dd31` | Add 5p/3p/combined telomere tracks and optional BAM input |
| `ae47380` | Initial commit: pretext-extensions standalone tool |

---

## Things to pick up next session

- [ ] Test with a real assembly + reads (colleagues are testing)
- [ ] Consider adding `PretextSnapshot` call to auto-generate PNG after injection
- [ ] Consider a `--no-hr` flag to make `--hr-pretext` truly optional without
      needing to omit it (currently it's already optional)
- [ ] telo_scan.py is vendored — consider a git submodule or pip install if
      cnag-aat/scripts evolves independently
