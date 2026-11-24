#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Coverage check of the split of the manual into two volumes (docs/design/manual_two_volumes.md).

    python3 docs/design/manual_two_volumes_coverage.py [--old REV]

Reads the one-volume manual of git revision REV (default 132b551: docs/manual/main.tex and every file it inputs) and
the two volumes of the working tree (docs/manual/user_manual.tex and reference.tex, with every file they input), and
checks that every label, every table and every command name of the old manual is in a volume:
  labels    every \\label{...} of the old manual is defined in one of the volumes;
  tables    every table (table, longtable, or a tabular outside them) is in a volume: by its caption, or, without a
            caption, by its first row;
  commands  every command name (':Name') and every upper-case keyword written in \\cmd{...} (options, parameters, state
            variables) appears in a volume;
  numbers   every number written in the two chapters that were rewritten for Volume 1 (intro.tex, applying.tex)
            appears in Volume 1.
Prints the missing items and a summary line per check; exit code 1 when anything is missing.
"""
import os, re, sys, argparse, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAN = 'docs/manual'


def old_file(rev, path):
    r = subprocess.run(['git', '-C', REPO, 'show', '%s:%s/%s' % (rev, MAN, path)], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def new_file(path):
    p = os.path.join(REPO, MAN, path)
    return open(p).read() if os.path.exists(p) else None


def expand(read, name, seen=None):
    """the text of name.tex with every \\input expanded, comments removed"""
    seen = set() if seen is None else seen
    t = read(name if name.endswith('.tex') else name + '.tex')
    if t is None or name in seen:
        return ''
    seen.add(name)
    t = re.sub(r'(?<!\\)%.*', '', t)
    return re.sub(r'\\input\{([^}]*)\}', lambda m: expand(read, m.group(1), seen), t)


def norm(s):
    s = s.replace('\\_', '_').replace('\\allowbreak', '').replace('\\allowbreak ', '')
    return re.sub(r'\s+', ' ', s).strip()


def labels(t):
    return set(re.findall(r'\\label\{([^}]*)\}', t))


def tables(t):
    """(key, kind) of every table: caption text, or the first row of an uncaptioned tabular"""
    out = []
    for m in re.finditer(r'\\begin\{(table|longtable)\}(.*?)\\end\{\1\}', t, re.S):
        c = re.search(r'\\caption\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}', m.group(2))
        out.append(('caption', norm(c.group(1))) if c else ('row', norm(m.group(2)[:120])))
    rest = re.sub(r'\\begin\{(table|longtable)\}.*?\\end\{\1\}', '', t, flags=re.S)
    for m in re.finditer(r'\\begin\{(tabular|tabularx)\}(?:\{[^}]*\})+(.*?)\\end\{\1\}', rest, re.S):
        body = m.group(2).replace('\\toprule', '').replace('\\hdr', '')
        row = body.split('\\\\')[0]
        out.append(('row', norm(row)))
    return out


def command_names(t):
    names = set()
    for m in re.finditer(r'\\cmd\{((?:[^{}]|\{[^{}]*\})*)\}', t):
        s = norm(m.group(1))
        names.update(re.findall(r':[A-Za-z][A-Za-z0-9_]*', s))
        names.update(w for w in re.findall(r'\b[A-Z][A-Z0-9_]{2,}\b', s))
    return names


def numbers(t):
    t = re.sub(r'\\(label|ref|cite|pageref|includegraphics|input|url)(\[[^]]*\])?\{[^}]*\}', '', t)
    t = t.replace('\\,', '')
    return set(n for n in re.findall(r'(?<![\w.])\d+(?:\.\d+)?', t) if len(n.replace('.', '')) >= 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--old', default='132b551')
    a = ap.parse_args()
    old = expand(lambda p: old_file(a.old, p), 'main')
    if not old:
        sys.exit('cannot read %s:%s/main.tex' % (a.old, MAN))
    vol1 = expand(new_file, 'user_manual'); vol2 = expand(new_file, 'reference')
    new = vol1 + '\n' + vol2
    newn = norm(new)
    missing = 0

    ol = labels(old); nl = labels(new)
    lm = sorted(ol - nl)
    for l in lm:
        print('label missing: %s' % l)
    print('labels: %d of %d of the old manual are defined in a volume (%d in Volume 1, %d in Volume 2)%s' % (
        len(ol) - len(lm), len(ol), len(ol & labels(vol1)), len(ol & labels(vol2)), '' if not lm else ': FAIL'))
    missing += len(lm)

    ot = tables(old); nt = set(k for _, k in tables(new))
    tm = [(kind, k) for kind, k in ot if k not in nt and k not in newn]
    for kind, k in tm:
        print('table missing (%s): %s' % (kind, k[:100]))
    print('tables: %d of %d of the old manual are in a volume (%d by caption, %d uncaptioned by their first row)%s' % (
        len(ot) - len(tm), len(ot), sum(1 for kd, _ in ot if kd == 'caption'), sum(1 for kd, _ in ot if kd == 'row'),
        '' if not tm else ': FAIL'))
    missing += len(tm)

    oc = command_names(old)
    cm = sorted(c for c in oc if c not in newn)
    for c in cm:
        print('command name missing: %s' % c)
    print('commands: %d of %d command names and keywords of the old manual appear in a volume (%d names with a colon)%s' % (
        len(oc) - len(cm), len(oc), sum(1 for c in oc if c.startswith(':')), '' if not cm else ': FAIL'))
    missing += len(cm)

    rew = ''.join(old_file(a.old, 'chapters/%s.tex' % c) or '' for c in ('intro', 'applying'))
    on = numbers(rew); v1n = numbers(vol1)
    nm = sorted(on - v1n)
    for n in nm:
        print('number of intro.tex/applying.tex missing in Volume 1: %s' % n)
    print('numbers: %d of %d numbers of intro.tex and applying.tex appear in Volume 1%s' % (
        len(on) - len(nm), len(on), '' if not nm else ': FAIL'))
    missing += len(nm)
    print('coverage: %s' % ('PASS' if missing == 0 else 'FAIL (%d items missing)' % missing))
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
