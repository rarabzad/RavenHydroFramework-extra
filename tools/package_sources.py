#!/usr/bin/env python3
"""Writes the source/ folder of the Raven + MODFLOW 6 package and checks that its history can be restored as the package
README says.

    python3 package_sources.py <package folder> <code repo> <code revision> <extra repo> <extra revision>
                               [--branch soil-zone] [--readme <package folder>/README.md] [--update-readme]

<code revision> and <extra revision> are branches or commits of the two repositories (worktrees work too).

Writes into <package folder>/source/:
  raven_code_src.tar.gz         git archive of the code revision, unpacks as raven-soil-zone/
  raven_code_history.bundle     the complete history of the code revision (back to Raven's first commit) as branch
                                --branch (default soil-zone)
  raven_extra_docs_tests.tar.gz git archive of the extra revision without docs/design (the developer records stay in the
                                repository and its history), unpacks as raven-mf6-extra/
  raven_extra_history.bundle    the complete history of the extra revision, as branch --branch
  RESTORE_HISTORY.md            the "Restore the git history" section of the package README: the clone commands and what
                                they give (commits and tip of each bundle)
  COMMITS.txt                   the commit, branch and commit count of each archive and bundle

A git bundle can only be cloned when it holds every ancestor of its branch. When a repository is a shallow clone
(git rev-parse --is-shallow-repository), the missing history is fetched first from the upstream Raven repository
(RAVEN_UPSTREAM, default https://github.com/rchlumsk/RavenHydroFramework, branch main). The script stops when the
upstream history does not reach the shallow boundary.

Check: the package README (--readme, default <package folder>/README.md) must have a section "## Restore the git
history". Its "git clone" commands are run as written, from an empty folder holding a copy of source/; together they must
clone both bundles, and each clone must be complete (not shallow, git fsck --full clean), be on branch --branch, have the
recorded tip and the same number of commits as the full history. Every "<n> commits ... (to <tip>)" statement of the
section must match the bundles. With --update-readme the section is first replaced by RESTORE_HISTORY.md's text.
Exit code 0 when the check passes.
"""
import os, sys, re, subprocess, shutil, tempfile, argparse

UPSTREAM = os.environ.get('RAVEN_UPSTREAM', 'https://github.com/rchlumsk/RavenHydroFramework')
UPSTREAM_BRANCH = os.environ.get('RAVEN_UPSTREAM_BRANCH', 'main')
SECTION = '## Restore the git history'
BUNDLES = {'code': 'raven_code_history.bundle', 'extra': 'raven_extra_history.bundle'}
EXCLUDE_EXTRA = ['docs/design']      # developer records: in the repository and its history, not in the source archive


def git(args, cwd, check=True):
    r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit('git %s (in %s) failed:\n%s%s' % (' '.join(args), cwd, r.stdout, r.stderr))
    return r.stdout.strip()


def is_shallow(repo):
    return git(['rev-parse', '--is-shallow-repository'], repo) == 'true'


def publish_repo(repo, rev, branch, tmp, name):
    """a temporary bare repository whose refs/heads/<branch> is <rev> of <repo> with its whole history (completed from
    upstream when <repo> is shallow); returns (path, tip, commit count)"""
    sha = git(['rev-parse', '--verify', rev + '^{commit}'], repo)
    pub = os.path.join(tmp, name + '_pub')
    git(['init', '-q', '--bare', pub], tmp)
    if is_shallow(repo):
        print('  %s is shallow: fetching the upstream history (%s %s)' % (repo, UPSTREAM, UPSTREAM_BRANCH))
        git(['fetch', '-q', UPSTREAM, '+refs/heads/%s:refs/upstream/%s' % (UPSTREAM_BRANCH, UPSTREAM_BRANCH)], pub)
        shallow_file = git(['rev-parse', '--git-path', 'shallow'], repo)
        if not os.path.isabs(shallow_file):
            shallow_file = os.path.join(repo, shallow_file)
        for s in open(shallow_file).read().split():
            if git(['cat-file', '-t', s], pub, check=False) != 'commit':
                sys.exit('the upstream history does not contain the shallow boundary %s of %s' % (s, repo))
    # every branch of the repository (the revision may be any commit on one of them), then the published branch
    git(['fetch', '-q', os.path.abspath(repo), '+refs/heads/*:refs/src/*'], pub)
    if git(['cat-file', '-t', sha], pub, check=False) != 'commit':
        sys.exit('%s (%s) is on no branch of %s' % (rev, sha, repo))
    git(['update-ref', 'refs/heads/' + branch, sha], pub)
    if is_shallow(pub):
        sys.exit('the history of %s is still incomplete (shallow)' % repo)
    return pub, sha, int(git(['rev-list', '--count', sha], pub))


def bundle(pub, branch, out):
    git(['bundle', 'create', out, 'refs/heads/' + branch], pub)
    git(['bundle', 'verify', out], pub)
    heads = git(['bundle', 'list-heads', out], pub).split('\n')
    if [h.split()[1] for h in heads if h.strip()] != ['refs/heads/' + branch]:
        sys.exit('%s holds %s, not only refs/heads/%s' % (out, heads, branch))


def restore_text(branch, rec):
    cmds = ['git clone source/%s raven-code -b %s' % (BUNDLES['code'], branch),
            'git clone source/%s raven-extra -b %s' % (BUNDLES['extra'], branch)]
    txt = (SECTION + '\nFrom the package folder:\n\n    %s\n    %s\n\n' % tuple(cmds) +
           'raven-code holds the whole Raven history (%d commits to %s), raven-extra %d commits (to %s), both on branch %s.\n'
           % (rec['code'][1], rec['code'][0][:7], rec['extra'][1], rec['extra'][0][:7], branch))
    return txt


def readme_section(text):
    """the README's restore section (from its heading to the next '## ' heading), or None"""
    i = text.find(SECTION + '\n')
    if i < 0:
        return None, -1, -1
    j = text.find('\n## ', i + len(SECTION))
    j = len(text) if j < 0 else j + 1
    return text[i:j], i, j


def check_clone(cmd, folder, branch, rec):
    """runs one README clone command as written; returns (which bundle, problems)"""
    w = cmd.split()
    which = [k for k, b in BUNDLES.items() if any(x.endswith(b) for x in w)]
    if len(w) < 4 or not which:
        return None, ['"%s" clones neither bundle' % cmd]
    tip, n = rec[which[0]]
    r = subprocess.run(cmd, shell=True, cwd=folder, capture_output=True, text=True)
    if r.returncode != 0:
        return which[0], ['"%s" failed: %s' % (cmd, (r.stdout + r.stderr).strip())]
    dest = os.path.join(folder, w[3] if not w[3].startswith('-') else os.path.basename(w[2]).replace('.bundle', ''))
    bad = []
    if is_shallow(dest):
        bad.append('the clone is shallow')
    if git(['rev-parse', '--abbrev-ref', 'HEAD'], dest) != branch:
        bad.append('checked out %s, not branch %s' % (git(['rev-parse', '--abbrev-ref', 'HEAD'], dest), branch))
    if git(['rev-parse', 'HEAD'], dest) != tip:
        bad.append('HEAD is not the recorded tip %s' % tip[:7])
    m = int(git(['rev-list', '--count', 'HEAD'], dest))
    if m != n:
        bad.append('%d commits instead of %d' % (m, n))
    f = subprocess.run(['git', 'fsck', '--full'], cwd=dest, capture_output=True, text=True)
    if f.returncode != 0:
        bad.append('git fsck: ' + (f.stdout + f.stderr).strip()[:300])
    return which[0], bad


def check_statements(section, rec):
    """every '<n> commits ... <tip>' statement of the section names a bundle's count and tip"""
    bad, seen = [], set()
    names = (('raven-code', 'code'), ('raven-extra', 'extra'))
    for m in re.finditer(r'([0-9][0-9,]*) commits\s*\(?(?:to\s+)?([0-9a-f]{7,40})\b', section):
        before = section[:m.start()]
        pos = [(before.rfind(name), name, k) for name, k in names]
        p, name, k = max(pos)
        if p < 0:
            bad.append('"%s" names neither raven-code nor raven-extra before it' % m.group(0))
            continue
        seen.add(k)
        n, tip = int(m.group(1).replace(',', '')), m.group(2)
        if n != rec[k][1] or not rec[k][0].startswith(tip):
            bad.append('%s: README says %d commits to %s, the bundle has %d to %s' % (name, n, tip, rec[k][1], rec[k][0][:7]))
    for name, k in names:
        if k not in seen:
            bad.append('no "%s ... <n> commits (to <tip>)" statement' % name)
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pkg'); ap.add_argument('code'); ap.add_argument('code_rev'); ap.add_argument('extra'); ap.add_argument('extra_rev')
    ap.add_argument('--branch', default='soil-zone', help='branch name of both bundles (default soil-zone)')
    ap.add_argument('--readme', default=None, help='the package README to check (default <pkg>/README.md)')
    ap.add_argument('--update-readme', action='store_true', help='replace its restore section by RESTORE_HISTORY.md first')
    a = ap.parse_args()
    src = os.path.join(a.pkg, 'source')
    readme = a.readme or os.path.join(a.pkg, 'README.md')
    os.makedirs(src, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='pkgsrc_')
    try:
        rec, pubs = {}, {}
        for k, repo, rev in (('code', a.code, a.code_rev), ('extra', a.extra, a.extra_rev)):
            pub, tip, n = publish_repo(repo, rev, a.branch, tmp, k)
            pubs[k] = pub; rec[k] = (tip, n)
        git(['archive', '--format=tar.gz', '--prefix=raven-soil-zone/', '-o',
             os.path.abspath(os.path.join(src, 'raven_code_src.tar.gz')), rec['code'][0]], pubs['code'])
        git(['archive', '--format=tar.gz', '--prefix=raven-mf6-extra/', '-o',
             os.path.abspath(os.path.join(src, 'raven_extra_docs_tests.tar.gz')), rec['extra'][0], '--', '.']
            + [':(exclude)%s' % p for p in EXCLUDE_EXTRA], pubs['extra'])
        for k in ('code', 'extra'):
            bundle(pubs[k], a.branch, os.path.abspath(os.path.join(src, BUNDLES[k])))
        txt = restore_text(a.branch, rec)
        with open(os.path.join(src, 'RESTORE_HISTORY.md'), 'w') as f:
            f.write(txt)
        with open(os.path.join(src, 'COMMITS.txt'), 'w') as f:
            f.write('raven_code_src.tar.gz and %s: commit %s, branch %s in the bundle, %d commits\n'
                    % (BUNDLES['code'], rec['code'][0], a.branch, rec['code'][1]))
            f.write('raven_extra_docs_tests.tar.gz and %s: commit %s, branch %s in the bundle, %d commits '
                    '(the archive without %s)\n' % (BUNDLES['extra'], rec['extra'][0], a.branch, rec['extra'][1],
                                                    ', '.join(EXCLUDE_EXTRA)))
        # the package README
        fails = []
        text = open(readme).read() if os.path.exists(readme) else None
        if text is None:
            fails.append('no package README %s' % readme)
        else:
            sec, i, j = readme_section(text)
            if sec is None:
                fails.append('the README has no section "%s"' % SECTION)
            else:
                new = text[:i] + txt + ('\n' if j < len(text) else '') + text[j:]
                if a.update_readme and new != text:
                    text = new
                    open(readme, 'w').write(text)
                    sec, i, j = readme_section(text)
                    print('README: restore section rewritten')
                cmds = [l.strip() for l in sec.split('\n') if l.strip().startswith('git clone')]
                chk = os.path.join(tmp, 'restore')
                os.makedirs(chk)
                shutil.copytree(src, os.path.join(chk, 'source'))
                seen = set()
                for c in cmds:
                    k, bad = check_clone(c, chk, a.branch, rec)
                    seen.add(k)
                    print('%-5s %s: %s' % (k or '?', c, ('ok (%d commits, %s, branch %s, not shallow, fsck clean)'
                                                          % (rec[k][1], rec[k][0][:7], a.branch)) if not bad else 'FAIL: ' + '; '.join(bad)))
                    fails += bad
                for k in BUNDLES:
                    if k not in seen:
                        fails.append('no README command clones %s' % BUNDLES[k])
                fails += check_statements(sec, rec)
        print(txt)
        print(open(os.path.join(src, 'COMMITS.txt')).read())
        for f in fails:
            print('FAIL: ' + f)
        print('restore check (README %s): %s' % (readme, 'PASS' if not fails else 'FAIL'))
        return 1 if fails else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
