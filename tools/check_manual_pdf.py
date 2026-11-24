#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Checks that the two PDFs of the manual are built from the sources beside them: builds both volumes from
docs/manual in a scratch folder and compares the text of each PDF with its build (pdftotext) and their page counts.

    python3 tools/check_manual_pdf.py [--repo DIR] [--rev REV] [--write]

The volumes (docs/manual):
  user_manual.tex  ->  Raven_MF6_User_Manual.pdf   Volume 1, User Manual
  reference.tex    ->  Raven_MF6_Reference.pdf     Volume 2, Reference and Verification

--repo DIR   the RavenHydroFramework-extra checkout (default: the one this script is in)
--rev REV    check the manual of that commit (git archive: its sources against its PDFs) instead of the files of the
             working tree
--write      when a text differs, replace that PDF in docs/manual of the working tree by the new build (not with --rev)

The two volumes refer to each other (package xr-hyper), so they are built together, with SOURCE_DATE_EPOCH set, in a
copy of docs/manual: pdflatex on each, bibtex on each, then pdflatex on each again until neither asks for a rerun and
their .aux files no longer change (at most 8 rounds). The last pass of each volume must end without errors, LaTeX
warnings, overfull boxes or undefined references. Exit code 0 when both PDFs' text and page counts are those of the
build (PASS), 1 when one differs (the first differing lines are shown), 2 when the manual does not build. Needs
pdflatex, bibtex and pdftotext. package_sources.py runs it on the extra revision it packages.
"""
import os, re, sys, shutil, hashlib, difflib, argparse, tempfile, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VOLUMES = [('user_manual', 'Raven_MF6_User_Manual.pdf'), ('reference', 'Raven_MF6_Reference.pdf')]
BAD = re.compile(r'^(?:LaTeX Warning: .*|Overfull \\hbox.*|! .*)$', re.M)
RERUN = re.compile(r'Rerun to get|Label\(s\) may have changed|Rerun LaTeX')
MAX_ROUNDS = 8


def run(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env, errors='replace')


def _aux_hash(mdir):
    h = hashlib.sha256()
    for job, _ in VOLUMES:
        p = os.path.join(mdir, job + '.aux')
        h.update(open(p, 'rb').read() if os.path.exists(p) else b'')
    return h.hexdigest()


def build(mdir):
    """builds both volumes in mdir (a copy of docs/manual); returns ({job: pdf path}, problems)"""
    env = dict(os.environ, SOURCE_DATE_EPOCH='1767225600', FORCE_SOURCE_DATE='1')
    for job, _ in VOLUMES:
        for ext in ('.pdf', '.aux'):
            if os.path.exists(os.path.join(mdir, job + ext)):
                os.remove(os.path.join(mdir, job + ext))

    def latex(job):
        r = run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', job + '.tex'], mdir, env)
        return None if r.returncode == 0 else 'pdflatex %s.tex failed:\n%s' % (job, r.stdout[-2000:])

    for job, _ in VOLUMES:
        e = latex(job)
        if e:
            return {}, [e]
    for job, _ in VOLUMES:
        run(['bibtex', job], mdir, env)
    prev = None
    for _ in range(MAX_ROUNDS):
        for job, _ in VOLUMES:
            e = latex(job)
            if e:
                return {}, [e]
        logs = [open(os.path.join(mdir, job + '.log'), errors='replace').read() for job, _ in VOLUMES]
        cur = _aux_hash(mdir)
        if cur == prev and not any(RERUN.search(l) for l in logs):
            break
        prev = cur
    probs = []
    for job, _ in VOLUMES:
        log = open(os.path.join(mdir, job + '.log'), errors='replace').read()
        probs += ['%s: %s' % (job, p) for p in BAD.findall(log)]
        if re.search(r'There were undefined (references|citations)', log):
            probs.append('%s: undefined references or citations' % job)
    pdfs = {job: os.path.join(mdir, job + '.pdf') for job, _ in VOLUMES if os.path.exists(os.path.join(mdir, job + '.pdf'))}
    if len(pdfs) < len(VOLUMES):
        probs.append('a volume produced no PDF')
    return pdfs, probs


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
    for prog in ('pdflatex', 'bibtex', 'pdftotext'):
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
        missing = [name for _, name in VOLUMES if not os.path.exists(os.path.join(mdir, name))]
        committed = {}
        for job, name in VOLUMES:
            if name not in missing:
                committed[job] = os.path.join(tmp, 'committed_' + name)
                shutil.copy(os.path.join(mdir, name), committed[job])
        pdfs, probs = build(mdir)
        if probs or len(pdfs) < len(VOLUMES):
            for p in probs:
                print('  ' + p.strip()[:300])
            print('check_manual_pdf: the manual of %s does not build cleanly: FAIL' % what)
            return 2
        status = 0
        for job, name in VOLUMES:
            new, pn = pdf_text(pdfs[job])
            if job not in committed:
                print('check_manual_pdf: %s has no %s (the build of %s.tex has %d pages): FAIL' % (what, name, job, pn))
                status = 1
            else:
                old, po = pdf_text(committed[job])
                if old == new and po == pn:
                    print('check_manual_pdf: %s (%d pages) is the build of %s.tex (%s): PASS' % (name, pn, job, what))
                    continue
                d = list(difflib.unified_diff(old, new, name, 'built from %s.tex' % job, n=0, lineterm=''))
                print('\n'.join(d[:40]) + ('\n  ... %d more lines' % (len(d) - 40) if len(d) > 40 else ''))
                print('check_manual_pdf: %s has %d pages, the build of %s.tex %d; %d text lines differ: FAIL' % (
                    name, po, job, pn, sum(1 for l in d if l[:1] in '+-' and not l.startswith(('+++', '---')))))
                status = 1
            if a.write:
                shutil.copy(pdfs[job], os.path.join(a.repo, 'docs', 'manual', name))
                print('check_manual_pdf: docs/manual/%s replaced by the new build' % name)
        print('check_manual_pdf: both volumes: %s' % ('PASS' if status == 0 else 'FAIL'))
        return status
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
