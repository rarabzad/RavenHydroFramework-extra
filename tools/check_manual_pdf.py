#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Checks that the manual PDF (docs/manual/main.pdf) is built from the chapters beside it: builds the manual from
docs/manual in a scratch folder and compares the text of the two PDFs (pdftotext) and their page counts.

    python3 tools/check_manual_pdf.py [--repo DIR] [--rev REV] [--write]

--repo DIR   the RavenHydroFramework-extra checkout (default: the one this script is in)
--rev REV    check the manual of that commit (git archive: its chapters against its main.pdf) instead of the files of
             the working tree
--write      when the texts differ, replace docs/manual/main.pdf of the working tree by the new build (not with --rev)

The build is `latexmk -pdf` (or, without latexmk, pdflatex, bibtex and pdflatex twice) with SOURCE_DATE_EPOCH set, in a
copy of docs/manual; it must end without errors, LaTeX warnings, overfull boxes or undefined references. Exit code 0
when the PDF's text and page count are those of the build (PASS), 1 when they differ (the first differing lines are
shown), 2 when the manual does not build. Needs pdflatex, bibtex (or latexmk) and pdftotext. package_sources.py runs it
on the extra revision it packages.
"""
import os, re, sys, shutil, difflib, argparse, tempfile, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BAD = re.compile(r'^(?:LaTeX Warning: .*|Overfull \\hbox.*|! .*)$', re.M)


def run(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env, errors='replace')


def build(mdir):
    """builds main.pdf in mdir (a copy of docs/manual); returns (pdf path, problems)"""
    env = dict(os.environ, SOURCE_DATE_EPOCH='1767225600', FORCE_SOURCE_DATE='1')
    pdf = os.path.join(mdir, 'main.pdf')
    if os.path.exists(pdf):
        os.remove(pdf)
    if shutil.which('latexmk'):
        steps = [['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'main.tex']]
    else:
        tex = ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'main.tex']
        steps = [tex, ['bibtex', 'main'], tex, tex]
    for s in steps:
        r = run(s, mdir, env)
        if r.returncode != 0 and s[0] != 'bibtex':
            return None, ['%s failed:\n%s' % (' '.join(s), r.stdout[-2000:])]
    log = open(os.path.join(mdir, 'main.log'), errors='replace').read()
    probs = BAD.findall(log)
    probs += ['undefined references or citations'] if re.search(r'There were undefined (references|citations)', log) else []
    return (pdf if os.path.exists(pdf) else None), probs


def pdf_text(pdf):
    r = run(['pdftotext', '-layout', pdf, '-'], os.path.dirname(pdf))
    if r.returncode != 0:                   # (not a PDF: an empty or damaged file)
        return ['(%s is not a readable PDF)' % os.path.basename(pdf)], 0
    pages = r.stdout.count('\f')
    lines = [re.sub(r'\s+', ' ', l).strip() for l in r.stdout.split('\n')]
    return [l for l in lines if l], pages


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', default=os.path.dirname(HERE)); ap.add_argument('--rev'); ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    if a.write and a.rev:
        sys.exit('--write works on the working tree only')
    for prog in ('pdflatex', 'pdftotext'):
        if not shutil.which(prog):
            sys.exit('check_manual_pdf: %s is needed' % prog)
    tmp = tempfile.mkdtemp(prefix='manualchk_')
    try:
        mdir = os.path.join(tmp, 'manual')
        if a.rev:
            arch = subprocess.run(['git', '-C', a.repo, 'archive', '--format=tar', a.rev, 'docs/manual'], capture_output=True)
            if arch.returncode != 0:
                sys.exit('git archive %s docs/manual failed: %s' % (a.rev, arch.stderr.decode(errors='replace')))
            subprocess.run(['tar', '-x', '-C', tmp, '-f', '-'], input=arch.stdout, check=True)
            shutil.move(os.path.join(tmp, 'docs', 'manual'), mdir)
            what = 'docs/manual of %s' % a.rev
        else:
            shutil.copytree(os.path.join(a.repo, 'docs', 'manual'), mdir)
            what = 'docs/manual of the working tree %s' % a.repo
        committed = os.path.join(tmp, 'committed.pdf')
        if not os.path.exists(os.path.join(mdir, 'main.pdf')):
            print('check_manual_pdf: %s has no main.pdf' % what); return 1
        shutil.copy(os.path.join(mdir, 'main.pdf'), committed)
        pdf, probs = build(mdir)
        if pdf is None or probs:
            for p in probs:
                print('  ' + p.strip()[:300])
            print('check_manual_pdf: the manual of %s does not build cleanly: FAIL' % what)
            return 2
        old, po = pdf_text(committed); new, pn = pdf_text(pdf)
        if old == new and po == pn:
            print('check_manual_pdf: main.pdf (%d pages) is the build of the chapters (%s): PASS' % (pn, what))
            return 0
        d = list(difflib.unified_diff(old, new, 'main.pdf', 'built from the chapters', n=0, lineterm=''))
        print('\n'.join(d[:40]) + ('\n  ... %d more lines' % (len(d) - 40) if len(d) > 40 else ''))
        print('check_manual_pdf: main.pdf has %d pages, the build of the chapters %d; %d text lines differ: FAIL' % (
            po, pn, sum(1 for l in d if l[:1] in '+-' and not l.startswith(('+++', '---')))))
        if a.write:
            shutil.copy(pdf, os.path.join(a.repo, 'docs', 'manual', 'main.pdf'))
            print('check_manual_pdf: docs/manual/main.pdf replaced by the new build')
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
