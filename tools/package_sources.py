#!/usr/bin/env python3
"""Writes the source/ folder of the Raven + MODFLOW 6 package and checks that its history can be restored.

    python3 package_sources.py <package folder> <code repo> <code branch> <extra repo> <extra branch>

Writes into <package folder>/source/:
  raven_code_src.tar.gz       (git archive of the code branch, unpacks as raven-soil-zone/)
  raven_code_history.bundle   (the complete history of the code branch, back to Raven's first commit)
  raven_extra_docs_tests.tar.gz (unpacks as raven-mf6-extra/)
  raven_extra_history.bundle  (the complete history of the extra branch)
  RESTORE_HISTORY.md          (the commands of the package README's "Restore the git history" section)

A git bundle can only be cloned when it holds every ancestor of its branch. When a repository is a shallow clone
(git rev-parse --is-shallow-repository), the missing history is fetched first from the upstream Raven repository
(RAVEN_UPSTREAM, default https://github.com/rchlumsk/RavenHydroFramework, branch main) into a temporary full repository,
and the branch is bundled from there. The script stops when the upstream history does not reach the shallow boundary.

Check: the commands of RESTORE_HISTORY.md are run as written in an empty folder next to a copy of source/; each clone
must be complete (not shallow, git fsck --full clean), have the branch tip of the repository and the same number of
commits as the full history. Exit code 0 when both restores pass.
"""
import os, sys, subprocess, shutil, tempfile

UPSTREAM = os.environ.get('RAVEN_UPSTREAM', 'https://github.com/rchlumsk/RavenHydroFramework')
UPSTREAM_BRANCH = os.environ.get('RAVEN_UPSTREAM_BRANCH', 'main')


def git(args, cwd, check=True):
    r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit('git %s (in %s) failed:\n%s%s' % (' '.join(args), cwd, r.stdout, r.stderr))
    return r.stdout.strip()


def is_shallow(repo):
    return git(['rev-parse', '--is-shallow-repository'], repo) == 'true'


def full_repo(repo, branch, tmp):
    """a repository holding the whole history of <branch>: <repo> itself, or a temporary one completed from upstream"""
    if not is_shallow(repo):
        return repo
    full = os.path.join(tmp, os.path.basename(os.path.abspath(repo)) + '_full')
    git(['init', '-q', '--bare', full], tmp)
    print('  %s is shallow: fetching the upstream history (%s %s)' % (repo, UPSTREAM, UPSTREAM_BRANCH))
    git(['fetch', '-q', UPSTREAM, '+refs/heads/%s:refs/upstream/%s' % (UPSTREAM_BRANCH, UPSTREAM_BRANCH)], full)
    shallow_file = git(['rev-parse', '--git-path', 'shallow'], repo)
    if not os.path.isabs(shallow_file):
        shallow_file = os.path.join(repo, shallow_file)
    for sha in open(shallow_file).read().split():
        if git(['cat-file', '-t', sha], full, check=False) != 'commit':
            sys.exit('the upstream history does not contain the shallow boundary %s of %s' % (sha, repo))
    git(['fetch', '-q', os.path.abspath(repo), '+refs/heads/%s:refs/heads/%s' % (branch, branch)], full)
    if is_shallow(full):
        sys.exit('the completed repository is still shallow')
    return full


def bundle(repo, branch, out, tmp):
    full = full_repo(repo, branch, tmp)
    tip = git(['rev-parse', 'refs/heads/' + branch], full)
    n = int(git(['rev-list', '--count', tip], full))
    git(['bundle', 'create', out, 'refs/heads/' + branch], full)
    git(['bundle', 'verify', out], full)
    return tip, n


def check_clone(cmd, folder, tip, n):
    """runs one README command as written; returns a list of problems"""
    r = subprocess.run(cmd, shell=True, cwd=folder, capture_output=True, text=True)
    if r.returncode != 0:
        return ['"%s" failed: %s' % (cmd, (r.stdout + r.stderr).strip())]
    dest = os.path.join(folder, cmd.split()[3])
    bad = []
    if is_shallow(dest):
        bad.append('the clone is shallow')
    if git(['rev-parse', 'HEAD'], dest) != tip:
        bad.append('HEAD is not the branch tip %s' % tip)
    m = int(git(['rev-list', '--count', 'HEAD'], dest))
    if m != n:
        bad.append('%d commits instead of %d' % (m, n))
    f = subprocess.run(['git', 'fsck', '--full'], cwd=dest, capture_output=True, text=True)
    if f.returncode != 0:
        bad.append('git fsck: ' + (f.stdout + f.stderr).strip())
    return bad


def main():
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    pkg, code, code_br, extra, extra_br = sys.argv[1:]
    src = os.path.join(pkg, 'source')
    os.makedirs(src, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='pkgsrc_')
    try:
        git(['archive', '--format=tar.gz', '--prefix=raven-soil-zone/', '-o',
             os.path.abspath(os.path.join(src, 'raven_code_src.tar.gz')), code_br], code)
        git(['archive', '--format=tar.gz', '--prefix=raven-mf6-extra/', '-o',
             os.path.abspath(os.path.join(src, 'raven_extra_docs_tests.tar.gz')), extra_br], extra)
        tips = {}
        tips['code'] = bundle(code, code_br, os.path.abspath(os.path.join(src, 'raven_code_history.bundle')), tmp)
        tips['extra'] = bundle(extra, extra_br, os.path.abspath(os.path.join(src, 'raven_extra_history.bundle')), tmp)
        cmds = {'code': 'git clone source/raven_code_history.bundle raven-code -b %s' % code_br,
                'extra': 'git clone source/raven_extra_history.bundle raven-extra -b %s' % extra_br}
        with open(os.path.join(src, 'RESTORE_HISTORY.md'), 'w') as f:
            f.write('## Restore the git history\nFrom the package folder:\n\n    %s\n    %s\n\n' % (cmds['code'], cmds['extra']))
            f.write('raven-code holds the whole Raven history (%d commits to %s), raven-extra %d commits (to %s).\n'
                    % (tips['code'][1], tips['code'][0][:7], tips['extra'][1], tips['extra'][0][:7]))
        # the README commands, as written, in an empty folder holding only source/
        chk = os.path.join(tmp, 'restore')
        os.makedirs(chk)
        shutil.copytree(src, os.path.join(chk, 'source'))
        fails = 0
        for k in ('code', 'extra'):
            bad = check_clone(cmds[k], chk, *tips[k])
            print('%-5s %s: %s' % (k, cmds[k], 'ok (%d commits, %s, not shallow, fsck clean)' % (tips[k][1], tips[k][0][:7])
                                   if not bad else 'FAIL: ' + '; '.join(bad)))
            fails += bool(bad)
        print(open(os.path.join(src, 'RESTORE_HISTORY.md')).read())
        print('restore check: %s' % ('PASS' if fails == 0 else 'FAIL'))
        return fails
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
