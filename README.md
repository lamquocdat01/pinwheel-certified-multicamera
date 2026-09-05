# How Many Cameras Can One Edge Box Certify?

Code, results and manuscript sources for the paper

> **How Many Cameras Can One Edge Box Certify? Density-Based Admission Control, Budget Shaping and
> Fleet Dimensioning for Shared-Accelerator Video Analytics**
> Dat Lam Quoc, FPT School of Business and Technology, FPT University, Ho Chi Minh City.
> Submitted to the *Journal of Network and Computer Applications*.

An edge box that runs object detection for a fleet of cameras has one accelerator and many
streams. If each camera's service-level agreement is written as a *refresh window* $K_i$ ---
inspect this camera at least once every $K_i$ frame slots, which bounds its worst-case detection
latency by $K_i-1$ --- then admission is decided by a single addition: a schedule meeting every
agreement exists whenever $\sum_i 1/K_i \le 5/6$. This repository contains the simulator that
replays a 121-video surveillance corpus against that rule, the machine checks for every theorem in
the paper, and the scripts that turn the result files into the numbers, tables and figures printed
in the manuscript. **No number in the paper is typed by hand**: `code/make_numbers.py` regenerates
`latex/numbers.tex` from `results/*.json`.

## Reproducing

```bash
pip install -r requirements.txt

# the corpus location (see "Data" below)
export PINWHEEL_DATA_DIR=/path/to/certifiable-frame-skipping/data/processed

python code/pinwheel_sim.py    --exp all   # E1-E3   round-1 experiments      (~4 min)
python code/proof_checks.py                # C1-C6   machine checks per theorem (~2 min)
python code/pinwheel_round2.py --exp all   # E1b, E4-E8 + all figures        (~5 min)
python code/make_numbers.py                # results/*.json -> latex/numbers.tex

cd latex && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Everything is seeded (`SEED = 42`) and deterministic: the exhaustive schedulability search uses a
state-count budget rather than a wall-clock budget, so the same verdicts come back on any machine.

To regenerate the bibliography from live metadata (needs network access to the Crossref and arXiv
APIs), run `python code/verify_refs.py` followed by `python code/make_bib.py`. Nothing enters
`latex/refs.bib` unless an API returned it; the cached verification is in `code/refs_verified.json`.

`code/build_and_check.py` rebuilds the manuscript and runs the pre-submission checks on the
*rendered PDF*: no leftover placeholders, a resolvable DOI printed for every reference, the corpus
size stated correctly, the abstract within the 250-word limit, highlights within 85 characters, and
the mandatory declaration sections present with the AI declaration before the references.

## Data

The corpus is 121 public surveillance videos --- 53 from CDnet2014, 48 from LASIESTA, 20 from
BMC --- carrying 3,713 annotated events over 166,589 frames.

**The video data and the derived per-event CSVs are not redistributed here.** The simulator reads
two files, `events_gated.csv` and `activation_by_video.csv`, from `$PINWHEEL_DATA_DIR`; they are
produced by the event-extraction pipeline of the companion single-camera study, and the versions
used for the published results are pinned by SHA-256 in `results/corpus_meta.json`:

| file | sha256 (first 12) |
|---|---|
| `events_gated.csv` | `8fade8f15bbb…` |
| `activation_by_video.csv` | `8b87d704a51a…` |

The source datasets are third-party and must be obtained from their authors:
CDnet2014 (Wang et al., CVPRW 2014, `10.1109/CVPRW.2014.126`),
LASIESTA (Cuevas et al., CVIU 2016, `10.1016/j.cviu.2016.08.005`),
BMC (Vacavant et al., ACCV 2012 Workshops, `10.1007/978-3-642-37410-4_25`).

## Layout

```
code/      simulator, round-2 experiments, per-theorem machine checks,
           number/bibliography generators, build + render checker
results/   every JSON the manuscript quotes, plus the results write-up
figures/   the eight figures, vector PDF
latex/     manuscript sources (main.tex, generated numbers.tex, generated refs.bib)
           and the elsarticle class and bibliography style (LPPL, redistributed with the paper)
```

`latex/main.tex` also reads an optional `latex/repo.tex` holding this repository's URL, commit and
tag for the Data availability statement. It is generated locally and deliberately not tracked
here, so that publishing the code cannot change the commit hash the paper quotes; the manuscript
builds without it.

## Licence

MIT --- see `LICENSE`. The bundled `elsarticle.cls` and `elsarticle-num.bst` are copyright
Elsevier Ltd and distributed under the LaTeX Project Public License 1.3 or later; they are not
covered by the MIT licence above.
