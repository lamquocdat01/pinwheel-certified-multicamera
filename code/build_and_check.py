#!/usr/bin/env python3
"""
build_and_check.py -- regenerate numbers.tex and refs.bib, build the manuscript, then run the
pre-submission render checks (checklist items C2, C5, C6) ON THE RENDERED PDF, not on the source.

Checks performed on the extracted text of main.pdf:
  R1  no placeholder markers ("[TODO:") survive        -> must be 0
  R2  every bibliography entry prints a resolvable identifier (doi.org URL) -> 0 missing
  R3  the corpus size is printed correctly: "3,713" >= 2 occurrences, "3,723" == 0
      (this is the exact assertion the companion package uses; the two numbers were once
       confused and the check exists so they never are again)
  R4  page count and figure/table count are reported
  R5  promotional-tone words are counted (checklist C3): first/novel/guarantee/superior

Usage:  python Submission_JNCA/build_and_check.py [--no-build]
Exit code 0 only if R1, R2 and R3 all pass.
"""
import json, os, re, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC = os.path.abspath(os.path.join(HERE, ".."))

def _find_latex_dir(start):
    """Locate the directory holding main.tex. Works both in the author's working tree
    (<topic>/Submission_JNCA/latex) and in the published repository (<repo>/latex)."""
    d = os.path.abspath(start)
    for _ in range(4):
        for cand in (os.path.join(d, "latex"),
                     os.path.join(d, "Submission_JNCA", "latex")):
            if os.path.exists(os.path.join(cand, "main.tex")):
                return cand
        d = os.path.dirname(d)
    return os.path.join(start, "latex")


def _find_file(name, *roots):
    for r in roots:
        p = os.path.join(r, name)
        if os.path.exists(p):
            return p
    return os.path.join(roots[0], name)

LATEX = _find_latex_dir(HERE)
MIKTEX = r"C:\Users\Admin\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
PDF = os.path.join(LATEX, "main.pdf")
TXT = os.path.join(LATEX, "main.txt")


def run(cmd, cwd, log):
    with open(os.path.join(cwd, log), "w", encoding="utf-8", errors="replace") as f:
        p = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, shell=False)
    return p.returncode


def tex(prog):
    return os.path.join(MIKTEX, prog + ".exe")


def build():
    print("== regenerating numbers.tex and refs.bib")
    r = subprocess.run([sys.executable, _find_file("make_numbers.py",
                                               os.path.join(TOPIC, "code"), HERE)])
    if r.returncode:
        print("   (make_numbers reported missing inputs -- numbers.tex was still written;"
              " any placeholder that reaches the PDF is caught by R1 below)")
    subprocess.run([sys.executable, _find_file("make_bib.py", HERE,
                                           os.path.join(TOPIC, "code"))], check=True)
    for stale in ("main.aux", "main.bbl", "main.blg", "main.out", "main.toc"):
        f = os.path.join(LATEX, stale)
        if os.path.exists(f):
            os.remove(f)           # a stale .bbl makes pass 1 report errors already fixed
    print("== pdflatex / bibtex / pdflatex x2")
    for i, (cmd, log) in enumerate((
            ([tex("pdflatex"), "-interaction=nonstopmode", "main.tex"], "pass1.log"),
            ([tex("bibtex"), "main"], "bibtex.log"),
            ([tex("pdflatex"), "-interaction=nonstopmode", "main.tex"], "pass2.log"),
            ([tex("pdflatex"), "-interaction=nonstopmode", "main.tex"], "pass3.log"))):
        run(cmd, LATEX, log)
    # surface every real TeX error: nonstopmode hides them from the exit code
    errs = []
    for log in ("pass2.log", "pass3.log", "bibtex.log"):   # pass1 runs without a .bbl
        p = os.path.join(LATEX, log)
        if not os.path.exists(p):
            continue
        txt = open(p, encoding="utf-8", errors="replace").read()
        errs += [(log, l.strip()) for l in txt.splitlines()
                 if l.startswith("!") or "Warning--" in l
                 or "LaTeX Warning: Citation" in l or "LaTeX Warning: Reference" in l]
    return errs


def font_check(pdfs):
    """No PDF in the list may embed a Type 3 (bitmap) font, and every font must be embedded.
    Shared with verify_package.py, which runs it over the whole submission package."""
    bad, unembedded, per_file = [], [], {}
    for p in pdfs:
        if not os.path.exists(p):
            continue
        r = subprocess.run([tex("pdffonts"), p], capture_output=True)
        rows = r.stdout.decode("utf-8", "replace").splitlines()[2:]
        names = set()
        for row in rows:
            if not row.strip():
                continue
            cols = row.split()
            # name is column 0; the type is everything up to the encoding column
            if "Type 3" in row:
                bad.append((os.path.basename(p), cols[0]))
            # columns are: name type... encoding emb sub uni objectnum gen
            if len(cols) >= 6 and cols[-5] == "no":       # "emb" column
                unembedded.append((os.path.basename(p), cols[0]))
            names.add(cols[0])
        per_file[os.path.basename(p)] = len(names)
    return {"pdfs_checked": per_file, "type3": sorted(set(bad)),
            "not_embedded": sorted(set(unembedded)),
            "pass": not bad and not unembedded}


def extract():
    r = subprocess.run([tex("pdftotext"), "-raw", "main.pdf", "main.txt"], cwd=LATEX,
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(TXT):
        sys.exit("pdftotext failed: " + r.stderr.decode("utf-8", "replace")[:400])
    return open(TXT, encoding="utf-8", errors="replace").read()


def main():
    errs = [] if "--no-build" in sys.argv else build()
    t = extract()
    flat = re.sub(r"\s+", " ", t)
    # page count from pdfinfo, not from counting form feeds in the extracted text: pdftotext
    # emits a trailing form feed, which made the form-feed count one too high.
    _pi = subprocess.run([tex("pdfinfo"), PDF], capture_output=True)
    _m = re.search(rb"Pages:\s+(\d+)", _pi.stdout)
    n_pages = int(_m.group(1)) if _m else t.count("\f")
    results = {}

    # R1 placeholders
    todos = re.findall(r"\[TODO:[^\]]*\]", flat)
    results["R1_placeholders"] = {"count": len(todos), "pass": len(todos) == 0,
                                  "examples": todos[:5]}

    # R2 identifiers in the bibliography
    bib = json.load(open(_find_file("refs_verified.json", HERE,
                                os.path.join(TOPIC, "Submission_JNCA"))))
    cited = sorted(bib)
    tail = flat[flat.rfind("References"):] if "References" in flat else flat
    dois = {d.rstrip(".,;") for d in re.findall(r"doi\.org/(\S+)", tail)}
    missing = []
    for k, r in bib.items():
        d = (r["doi"] or "").lower()
        ax = r["sources"].get("arxiv")
        if not d and isinstance(ax, dict) and ax.get("doi"):
            d = ax["doi"].lower()
        if not d:
            d = ("10.48550/arxiv." + str(r["arxiv"])).lower()
        if not any(d in x.lower() for x in dois):
            missing.append((k, d))
    results["R2_identifiers"] = {"entries": len(bib), "printed_on_page": len(dois),
                                 "missing": missing, "pass": len(missing) == 0}

    # R3 corpus-size assertion
    n3713 = len(re.findall(r"3,713", flat))
    n3723 = len(re.findall(r"3,723", flat))
    results["R3_corpus_number"] = {"n_3713": n3713, "n_3723": n3723,
                                   "pass": n3713 >= 2 and n3723 == 0}

    # R4 inventory
    results["R4_inventory"] = {
        "pages": n_pages,
        "figures": len(set(re.findall(r"Figure (\d+)", flat))),
        "tables": len(set(re.findall(r"Table (\d+)", flat))),
        "theorem_env": len(set(re.findall(r"(?:Theorem|Lemma|Proposition|Corollary) (\d+)", flat))),
    }

    # R5 tone
    tone = {w: len(re.findall(r"\b" + w + r"\w*", flat, re.I))
            for w in ("novel", "superior", "outperform", "first", "guarantee")}
    results["R5_tone"] = tone

    # R6 abstract length: JNCA Guide for Authors caps it at 250 words.
    # Counted on the SOURCE with \num* macros expanded, because pdftotext splits ligature words
    # ("certi cate", "su ciently") and hyphenated line breaks, which inflates a PDF-side count.
    src = open(os.path.join(LATEX, "main.tex"), encoding="utf-8").read()
    numbers = dict(re.findall(r"\\newcommand\{\\(num[A-Za-z]+)\}\{([^}]*)\}",
                              open(os.path.join(LATEX, "numbers.tex"), encoding="utf-8").read()))
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", src, re.S)
    words = None
    if m:
        a = re.sub(r"(?<!\\)%.*", "", m.group(1))              # drop LaTeX comments
        a = re.sub(r"\\(num[A-Za-z]+)\\?", lambda g: numbers.get(g.group(1), "X") + " ", a)
        a = re.sub(r"\$[^$]*\$", " X ", a)                     # inline maths counts as one word
        a = re.sub(r"\\[a-zA-Z]+\*?", " ", a)                  # remaining control sequences
        a = re.sub(r"[{}~\\]", " ", a)
        words = len([w for w in a.split() if re.search(r"[0-9A-Za-z]", w)])
    m2 = re.search(r"Abstract\s+(.*?)\s+Keywords", flat, re.S)
    pdf_words = len(m2.group(1).split()) if m2 else None
    results["R6_abstract_words"] = {"words": words, "limit": 250,
                                    "pdf_extracted_words_upper_bound": pdf_words,
                                    "pass": words is not None and words <= 250}

    # R7 highlights: 3-5 bullets, each <= 85 characters including spaces
    hp = _find_file("highlights.txt", HERE, TOPIC)
    bullets = [l.strip() for l in open(hp, encoding="utf-8").read().splitlines()
               if l.strip()] if os.path.exists(hp) else []
    over = [(len(b), b) for b in bullets if len(b) > 85]
    results["R7_highlights"] = {"file": os.path.basename(hp), "n": len(bullets),
                                "lengths": [len(b) for b in bullets], "over_85": over,
                                "pass": bool(bullets) and 3 <= len(bullets) <= 5 and not over}

    # R8 mandatory Elsevier sections present on the rendered page, AI declaration before References
    need = {"credit": "CRediT authorship contribution statement",
            "competing": "Declaration of competing interest",
            "ai": "Declaration of generative AI and AI-assisted technologies",
            "data": "Data availability",
            "funding": "Funding"}
    pos = {k: flat.find(v) for k, v in need.items()}
    ref_pos = flat.rfind("References")
    ai_before_refs = 0 <= pos["ai"] < ref_pos
    results["R8_sections"] = {"found": {k: (v >= 0) for k, v in pos.items()},
                              "ai_declaration_before_references": ai_before_refs,
                              "pass": all(v >= 0 for v in pos.values()) and ai_before_refs}

    # R9 badly overfull boxes: text running off the page silently truncates it in the PDF.
    # (A long unbreakable URL did exactly that once; the check exists so it cannot recur.)
    log = os.path.join(LATEX, "main.log")
    over = []
    if os.path.exists(log):
        for l in open(log, encoding="utf-8", errors="replace"):
            m = re.match(r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)", l)
            if m and float(m.group(1)) > 20.0:
                over.append(l.strip()[:110])
    results["R9_overfull"] = {"threshold_pt": 20.0, "count": len(over), "examples": over[:5],
                              "pass": not over}

    # R10 no Type 3 fonts. A Type 3 font is a bitmap: it renders blurry at any zoom, cannot be
    # searched or copied, and makes pdftotext drop ligatures (which once inflated the abstract
    # word count from 240 to 292). MiKTeX falls back to Type 3 whenever the T1 outlines are
    # missing (fixed by \usepackage{lmodern}) and matplotlib emits Type 3 unless
    # rcParams["pdf.fonttype"] is 42.
    results["R10_no_type3_fonts"] = font_check([PDF])

    results["tex_errors"] = errs

    out = os.path.join(HERE, "RENDER_CHECK.json")
    json.dump(results, open(out, "w"), indent=1)

    GATES = ("R1_placeholders", "R2_identifiers", "R3_corpus_number",
             "R6_abstract_words", "R7_highlights", "R8_sections", "R9_overfull",
             "R10_no_type3_fonts")
    ok = all(results[k]["pass"] for k in GATES)
    print("\n== RENDER CHECK on %s" % PDF)
    for k in GATES:
        print("  %-20s %s  %s" % (k, "PASS" if results[k]["pass"] else "FAIL",
                                  {kk: vv for kk, vv in results[k].items() if kk != "pass"}))
    print("  %-20s %s" % ("R4_inventory", results["R4_inventory"]))
    print("  %-20s %s" % ("R5_tone", tone))
    if errs:
        print("  TeX diagnostics (%d):" % len(errs))
        for log, l in errs[:12]:
            print("     [%s] %s" % (log, l[:150]))
    print("  ->", out)
    sys.exit(0 if ok and not errs else 1)


if __name__ == "__main__":
    main()
