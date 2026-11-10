#!/usr/bin/env python3
"""Writes the hand-over kit for publishing the coupling: the two repositories as git bundles and source archives, with
HANDOVER.md, the copy-paste steps to publish them from your own computer.

    python3 make_handover.py <code repo> <extra repo> [--code-rev soil-zone] [--extra-rev soil-zone]
                             [--out handover] [--code-branch mf6-coupling] [--extra-branch main] [--no-public-check]

<code repo> holds Raven with the coupling, <extra repo> this repository; the revisions are branches or commits of them.
Writes into --out (a new or empty folder):

  RavenHydroFramework_mf6-coupling.bundle      the complete history of the code revision (back to Raven's first commit)
                                               as branch mf6-coupling, the branch of https://github.com/rarabzad/RavenHydroFramework
  RavenHydroFramework-extra_main.bundle        the complete history of the extra revision as branch main, the default
                                               branch of https://github.com/rarabzad/RavenHydroFramework-extra
  RavenHydroFramework_mf6-coupling.tar.gz      the files of each tip (git archive; unpacks as RavenHydroFramework/ and
  RavenHydroFramework-extra_main.tar.gz        RavenHydroFramework-extra/), for publishing by replacing the files
  HANDOVER.md                                  the steps: publish the code branch (history-preserving, or by replacing the
                                               files), create and fill the -extra repository, verify, and what to do when
                                               the public branch holds commits the bundle does not
  KIT.txt, SHA256SUMS.txt                      commit, tree and commit count of each bundle; checksums of every file

The -extra repository is published with its whole history, docs/design (the developer records) included: every earlier
commit holds them, so leaving them out of the tip would not take them out of the public repository, and rewriting the
history would give commits that no longer match this repository's. The release package's source archive (written by
package_sources.py) leaves docs/design out.

A shallow code repository is completed from the upstream Raven repository first (package_sources.publish_repo:
RAVEN_UPSTREAM, default https://github.com/rchlumsk/RavenHydroFramework).

Checks (the exit code is 0 only when all pass):
  - each bundle: git bundle verify; it holds only its branch; a clone of it is on that branch, at the recorded commit,
    not shallow, with the recorded commit count, and git fsck --full is clean;
  - each archive unpacks into one folder named as the repository;
  - HANDOVER.md's command blocks pass bash -n, and the blocks are run as written, each in a new bash, against local
    stand-ins for the two GitHub repositories (git's url.insteadOf; the code stand-in at an ancestor of the kit's tip,
    the -extra one empty): 0-checksums; 2-extra (the -extra branch at the kit's commit); 1B-bundle and 1B-archive (the
    published tree is the kit's; the stand-in is reset after each); 1A-check and 1A-push (a fast-forward to the kit's
    commit); 4-show; 3-verify (PASS); 2-extra-files on an empty stand-in (the kit's tree). Nothing is pushed to GitHub;
  - unless --no-public-check: the public branch mf6-coupling is read (git ls-remote; nothing is pushed) and, when it can
    be fetched, whether it is an ancestor of the bundle's tip (a plain fast-forward) is written into HANDOVER.md.
"""
import os, re, sys, argparse, subprocess, tempfile, shutil, hashlib, tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import package_sources as ps   # noqa: E402  (publish_repo, bundle, git)

PUBLIC = {'code': 'https://github.com/rarabzad/RavenHydroFramework', 'extra': 'https://github.com/rarabzad/RavenHydroFramework-extra'}
NAME = {'code': 'RavenHydroFramework', 'extra': 'RavenHydroFramework-extra'}
ENV = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='true')   # (never ask for a password)


def run(args, cwd, timeout=600):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=ENV, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def check_bundle(path, k, rec, tmp):
    """clones the bundle and checks branch, tip, history, fsck; returns a list of problems"""
    tip, n, br, tree = rec[k]['tip'], rec[k]['n'], rec[k]['branch'], rec[k]['tree']
    dest = os.path.join(tmp, 'verify', NAME[k])
    rc, out = run(['git', 'clone', '-q', '-b', br, path, dest], tmp)
    if rc != 0:
        return ['clone of %s failed: %s' % (os.path.basename(path), out[:300])]
    bad = []
    g = lambda *a: run(['git'] + list(a), dest)[1]
    if g('rev-parse', '--is-shallow-repository') != 'false': bad.append('the clone is shallow')
    if g('rev-parse', '--abbrev-ref', 'HEAD') != br: bad.append('the clone is not on branch %s' % br)
    if g('rev-parse', 'HEAD') != tip: bad.append('the clone is at %s, not %s' % (g('rev-parse', 'HEAD'), tip))
    if g('rev-parse', 'HEAD^{tree}') != tree: bad.append('tree %s, not %s' % (g('rev-parse', 'HEAD^{tree}'), tree))
    if g('rev-list', '--count', 'HEAD') != str(n): bad.append('%s commits, not %d' % (g('rev-list', '--count', 'HEAD'), n))
    rc, out = run(['git', 'fsck', '--full'], dest)
    if rc != 0: bad.append('git fsck: ' + out[:300])
    heads = [l.split()[1] for l in run(['git', 'bundle', 'list-heads', path], tmp)[1].split('\n') if l.strip()]
    if heads != ['refs/heads/' + br]: bad.append('the bundle holds %s, not only refs/heads/%s' % (heads, br))
    return bad


def check_archive(path, k):
    """the archive unpacks into one folder named as the repository; returns a list of problems (its content is checked by
    running HANDOVER.md's blocks, run_blocks)"""
    with tarfile.open(path) as t:
        top = {m.name.split('/')[0] for m in t.getmembers() if m.name not in ('pax_global_header',)}
    return [] if top == {NAME[k]} else ['%s unpacks into %s, not one folder %s/' % (os.path.basename(path), sorted(top), NAME[k])]


def blocks(text):
    """the command blocks of HANDOVER.md: {tag: script}, from every fenced block whose first line is '# [tag] ...'"""
    out = {}
    for m in re.finditer(r'^([ \t]*)```\n(.*?)^[ \t]*```$', text, re.M | re.S):
        lines = [l[len(m.group(1)):] if l.startswith(m.group(1)) else l for l in m.group(2).split('\n')]
        t = re.match(r'# \[([0-9A-Za-z-]+)\]', lines[0])
        if t:
            out[t.group(1)] = '\n'.join(lines)
    return out


def run_blocks(text, out, rec, pubs, tmp):
    """runs HANDOVER.md's blocks as written, each in a new bash, against local stand-ins for the GitHub repositories
    (git's url.insteadOf maps the GitHub addresses to them): the code stand-in's branch is an ancestor of the kit's tip
    with another tree, the -extra stand-in is empty. Returns a list of problems."""
    B = blocks(text)
    need = ['0-checksums', '1A-check', '1A-push', '1A-replace', '1B-bundle', '1B-archive', '2-extra', '2-extra-files',
            '3-verify', '3-build', '4-show', '4-keep', '4-keep-push', '4-merge']
    bad = ['HANDOVER.md has no block %s' % b for b in need if b not in B]
    for tag, s in B.items():
        rc, o = run(['bash', '-n', '-c', s], tmp)
        if rc != 0: bad.append('block %s: bash -n: %s' % (tag, o[:200]))
    if bad: return bad
    gh, work, home = (os.path.join(tmp, x) for x in ('gh', 'work', 'home'))
    for d in (gh, work, home): os.makedirs(d)
    os.symlink(out, os.path.join(work, 'handover'))
    cfg = os.path.join(tmp, 'gitconfig')
    with open(cfg, 'w') as f:
        f.write('[user]\n\tname = handover check\n\temail = check@example.invalid\n[url "file://%s/"]\n\tinsteadOf = %s/\n'
                '[advice]\n\tdetachedHead = false\n' % (gh, PUBLIC['code'].rsplit('/', 1)[0]))
    env = dict(ENV, HOME=home, GIT_CONFIG_GLOBAL=cfg, GIT_CONFIG_NOSYSTEM='1')
    cb, xb = rec['code']['branch'], rec['extra']['branch']
    code_gh, extra_gh = os.path.join(gh, NAME['code'] + '.git'), os.path.join(gh, NAME['extra'] + '.git')
    g = lambda args, cwd: run(['git'] + args, cwd)
    # (GitHub's default branch: main on the fork, the first branch pushed on the new repository)
    def bare(path, headref):
        g(['init', '-q', '--bare', path], tmp); g(['symbolic-ref', 'HEAD', headref], path)
    # the code stand-in's branch: the first ancestor of the kit's tip on its first-parent line whose tree differs (so
    # that 1B makes a commit), and main the same
    base = next(c for c in g(['rev-list', '--first-parent', rec['code']['tip']], pubs['code'])[1].split()
                if g(['rev-parse', c + '^{tree}'], pubs['code'])[1] != rec['code']['tree'])
    bare(code_gh, 'refs/heads/main')
    g(['push', '-q', code_gh, base + ':refs/heads/' + cb, base + ':refs/heads/main'], pubs['code'])
    bare(extra_gh, 'refs/heads/' + xb)

    def blk(tag):
        r = subprocess.run(['bash', '-c', B[tag]], cwd=work, capture_output=True, text=True, env=env, timeout=1800)
        return r.returncode, (r.stdout + r.stderr).strip()

    def head(repo, ref, what='commit'):
        return g(['rev-parse', ref + ('^{tree}' if what == 'tree' else '')], repo)[1]

    steps = []
    def step(tag, ok, msg):
        steps.append('  block %-13s %s' % (tag, ('ok: ' + msg) if ok else 'FAIL: ' + msg))
        if not ok: bad.append('block %s: %s' % (tag, msg))
    rc, o = blk('0-checksums'); step('0-checksums', rc == 0 and 'FAILED' not in o, o.split('\n')[-1][:120])
    rc, o = blk('2-extra'); x = head(extra_gh, 'refs/heads/' + xb)
    step('2-extra', rc == 0 and x == rec['extra']['tip'], '-extra %s at %s' % (xb, x[:12]) if rc == 0 else o[-300:])
    for tag in ('1B-bundle', '1B-archive'):
        rc, o = blk(tag); tr = head(code_gh, 'refs/heads/' + cb, 'tree')
        step(tag, rc == 0 and tr == rec['code']['tree'], ('%s has tree %s' % (cb, tr[:12])) if rc == 0 else o[-300:])
        rc, o = g(['update-ref', 'refs/heads/' + cb, base], code_gh)
        if rc != 0: bad.append('could not reset the stand-in: ' + o); return bad
        shutil.rmtree(os.path.join(work, NAME['code'] + '-1B'), ignore_errors=True)
    rc, o = blk('1A-check'); step('1A-check', rc == 0 and 'fast-forward' in o, o.split('\n')[-1][:120])
    rc, o = blk('1A-push'); c = head(code_gh, 'refs/heads/' + cb)
    step('1A-push', rc == 0 and c == rec['code']['tip'], ('%s at %s' % (cb, c[:12])) if rc == 0 else o[-300:])
    rc, o = blk('4-show'); step('4-show', rc == 0, 'nothing beyond the kit' if rc == 0 else o[-300:])
    rc, o = blk('3-verify'); step('3-verify', rc == 0 and o.endswith('verify: PASS'), o.split('\n')[-1][:120])
    shutil.rmtree(extra_gh); bare(extra_gh, 'refs/heads/' + xb)
    rc, o = blk('2-extra-files'); tr = head(extra_gh, 'refs/heads/' + xb, 'tree')
    step('2-extra-files', rc == 0 and tr == rec['extra']['tree'], ('-extra %s has tree %s' % (xb, tr[:12])) if rc == 0 else o[-300:])
    print('\n'.join(steps), flush=True)
    return bad


def public_state(pub_code, rec, tmp):
    """what the public repositories hold now (read only): text lines for KIT.txt and HANDOVER.md"""
    lines = []
    br = rec['code']['branch']
    rc, out = run(['git', 'ls-remote', PUBLIC['code'], 'refs/heads/' + br], tmp, timeout=120)
    sha = out.split()[0] if (rc == 0 and out.strip()) else ''
    if not sha:
        lines.append('%s branch %s: not readable now (%s)' % (PUBLIC['code'], br, 'no such branch' if rc == 0 else 'offline or private'))
    elif sha == rec['code']['tip']:
        lines.append('%s branch %s: already at %s (nothing to push)' % (PUBLIC['code'], br, sha))
    else:
        rc, out = run(['git', 'fetch', '-q', PUBLIC['code'], '+refs/heads/%s:refs/public/%s' % (br, br)], pub_code, timeout=900)
        if rc != 0:
            lines.append('%s branch %s: at %s, could not be fetched to compare' % (PUBLIC['code'], br, sha))
        else:
            anc = run(['git', 'merge-base', '--is-ancestor', sha, rec['code']['tip']], pub_code)[0] == 0
            extra = run(['git', 'rev-list', '--count', '%s..%s' % (rec['code']['tip'], sha)], pub_code)[1]
            lines.append('%s branch %s: at %s, %s' % (PUBLIC['code'], br, sha,
                         'an ancestor of the bundle\'s tip: publishing it is a fast-forward (block 1A-push)' if anc else
                         'not an ancestor of the bundle\'s tip: it holds %s commit(s) the bundle does not (block 1A-replace, or step 4)' % extra))
    rc, out = run(['git', 'ls-remote', PUBLIC['extra']], tmp, timeout=120)
    if rc != 0:
        lines.append('%s: not readable now (it does not exist yet, is private, or the computer is offline): create it in step 2' % PUBLIC['extra'])
    elif not out.strip():
        lines.append('%s: exists and is empty: fill it in step 2' % PUBLIC['extra'])
    else:
        lines.append('%s: exists and holds %s: see step 2 (it must be empty before the first push)' % (PUBLIC['extra'], ', '.join(l.split()[1] for l in out.split('\n'))))
    return lines


HANDOVER = r"""# Publishing the Raven + MODFLOW 6 coupling

This kit holds the two repositories of the coupling, ready to publish from your own computer:

| Repository | Branch | Commit | Commits | Files |
|---|---|---|---|---|
| {cu} | `{cb}` | `{ct}` | {cn} | `{cbundle}`, `{ctar}` |
| {xu} | `{xb}` (default branch) | `{xt}` | {xn} | `{xbundle}`, `{xtar}` |

Tree IDs (the content of each tip): code `{ctree}`, extra `{xtree}`. The state of the public repositories when the kit
was made:

{public}

## How to run the steps

- Use a bash shell: Linux, macOS, or Git Bash on Windows. You need git, and push access to both repositories (a personal
  access token or an SSH key; with SSH, write `git@github.com:rarabzad/...` for `https://github.com/rarabzad/...`).
- Put this kit as `handover/` in an empty **working folder** and `cd` into that folder. Every block below starts there.
- Copy each block whole. Each runs in a subshell `( ... )` with `set -eu`: it stops at the first command that fails,
  it uses no variable from an earlier block (it works out what it needs again), and it leaves your shell in the
  working folder. A block that would push checks first and pushes nothing when a check fails.
- Nothing here changes any branch other than `{cb}` (and creates `{cb}-before-release` only where it does not exist),
  and nothing deletes a branch.

Check the kit's files first:

```
# [0-checksums] run in: the working folder (the one that holds handover/)
( set -eu
  cd handover
  if command -v sha256sum >/dev/null 2>&1; then sha256sum -c SHA256SUMS.txt; else shasum -a 256 -c SHA256SUMS.txt; fi
)
```

## 1. Publish the code: branch `{cb}` of RavenHydroFramework

Choose A (keeps the full history: the published commits are exactly those of the kit) or B (one new commit on top of
the branch as it is now; no force push).

### 1A. History-preserving (recommended)

First see what GitHub holds. The block clones the fork into `RavenHydroFramework/` (or reuses that clone) and reads
the kit's branch from the bundle; it changes nothing on GitHub:

```
# [1A-check] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  [ -d RavenHydroFramework/.git ] || git clone -q {cu}.git RavenHydroFramework
  cd RavenHydroFramework
  git fetch -q ../handover/{cbundle} "+refs/heads/{cb}:refs/remotes/handover/{cb}"
  test "$(git rev-parse handover/{cb})" = {ct} || {{ echo "STOP: the kit's branch is not at {ct}"; exit 1; }}
  git fetch -q --prune origin
  if ! CUR=$(git rev-parse -q --verify refs/remotes/origin/{cb}); then
    echo "GitHub has no branch {cb}: publish with block 1A-push"; exit 0
  fi
  echo "GitHub's {cb} is at $CUR"
  if git merge-base --is-ancestor "$CUR" handover/{cb}; then
    echo "it is an ancestor of the kit: publish with block 1A-push (a fast-forward)"
  else
    echo "it holds commits the kit does not:"
    git log --oneline "handover/{cb}..$CUR"
    echo "publish with block 1A-replace (they stay on GitHub as {cb}-before-release), or read step 4 to keep them"
  fi
)
```

When GitHub's branch is an ancestor of the kit (or does not exist), push without force; git refuses anything but a
fast-forward:

```
# [1A-push] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  [ -d RavenHydroFramework/.git ] || git clone -q {cu}.git RavenHydroFramework
  cd RavenHydroFramework
  git fetch -q ../handover/{cbundle} "+refs/heads/{cb}:refs/remotes/handover/{cb}"
  test "$(git rev-parse handover/{cb})" = {ct} || {{ echo "STOP: the kit's branch is not at {ct}"; exit 1; }}
  git push origin "refs/remotes/handover/{cb}:refs/heads/{cb}"
)
```

When GitHub's branch holds commits the kit does not and you do not need them on `{cb}` (when the kit was made: the
commit listed above, an earlier single-commit upload of the coupling that the kit's history replaces), keep a copy of
the branch as `{cb}-before-release` and replace it. The copy is made only when it does not exist yet, and the block
stops if an existing copy does not hold GitHub's branch. `--force-with-lease` makes the push fail, rather than discard
anything, if someone pushes to the branch after the block has read it:

```
# [1A-replace] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  [ -d RavenHydroFramework/.git ] || git clone -q {cu}.git RavenHydroFramework
  cd RavenHydroFramework
  git fetch -q ../handover/{cbundle} "+refs/heads/{cb}:refs/remotes/handover/{cb}"
  test "$(git rev-parse handover/{cb})" = {ct} || {{ echo "STOP: the kit's branch is not at {ct}"; exit 1; }}
  git fetch -q --prune origin
  CUR=$(git rev-parse -q --verify refs/remotes/origin/{cb}) || {{ echo "STOP: GitHub has no branch {cb}: use block 1A-push"; exit 1; }}
  if git merge-base --is-ancestor "$CUR" handover/{cb}; then
    echo "GitHub's {cb} is an ancestor of the kit: nothing to replace, a plain push"
    git push origin "refs/remotes/handover/{cb}:refs/heads/{cb}"; exit 0
  fi
  if BAK=$(git rev-parse -q --verify refs/remotes/origin/{cb}-before-release); then
    git merge-base --is-ancestor "$CUR" "$BAK" || {{ echo "STOP: {cb}-before-release exists on GitHub and does not hold $CUR"; exit 1; }}
    echo "{cb}-before-release exists and holds $CUR: kept as it is"
  else
    git push origin "$CUR:refs/heads/{cb}-before-release"
  fi
  git push --force-with-lease="refs/heads/{cb}:$CUR" origin "refs/remotes/handover/{cb}:refs/heads/{cb}"
)
```

### 1B. Replace the files (one new commit)

The branch keeps its history and gets one new commit whose files are exactly the kit's. Each block makes its own clone
in `RavenHydroFramework-1B/` (it stops if that folder exists), commits, and pushes only when the new commit's tree is
`{ctree}`. From the bundle (exact files and file modes, on any system):

```
# [1B-bundle] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  test ! -e RavenHydroFramework-1B || {{ echo "STOP: RavenHydroFramework-1B exists: remove or rename it first"; exit 1; }}
  git clone -q -b {cb} {cu}.git RavenHydroFramework-1B
  cd RavenHydroFramework-1B
  git fetch -q ../handover/{cbundle} "+refs/heads/{cb}:refs/remotes/handover/{cb}"
  git read-tree -u --reset handover/{cb}
  git commit -q -m "Raven + MODFLOW 6 coupling: release {date}"
  TREE=$(git rev-parse "HEAD^{{tree}}")
  test "$TREE" = {ctree} || {{ echo "STOP: the commit's tree is $TREE, not {ctree}; nothing pushed"; exit 1; }}
  git push origin {cb}
)
```

From the archive, without git bundles (on Windows the executable bits of scripts can differ, and with them the tree:
the block then stops; use the bundle form there):

```
# [1B-archive] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  test ! -e RavenHydroFramework-1B || {{ echo "STOP: RavenHydroFramework-1B exists: remove or rename it first"; exit 1; }}
  git clone -q -b {cb} {cu}.git RavenHydroFramework-1B
  cd RavenHydroFramework-1B
  git rm -r -q --ignore-unmatch .
  tar -xzf ../handover/{ctar} --strip-components=1
  git add -A -f
  git commit -q -m "Raven + MODFLOW 6 coupling: release {date}"
  TREE=$(git rev-parse "HEAD^{{tree}}")
  test "$TREE" = {ctree} || {{ echo "STOP: the commit's tree is $TREE, not {ctree}; nothing pushed"; exit 1; }}
  git push origin {cb}
)
```

(`git add -A -f`: some files of the repository match its `.gitignore`, for example `src/Makefile`; without `-f` they
would be left out.) With 1B the published commit is new: its ID differs from `{ct}`, its tree is the same.

## 2. Create and fill RavenHydroFramework-extra

Create the repository on GitHub, **empty** (no README, licence or .gitignore; they are in the kit): on
https://github.com/new, owner `rarabzad`, name `RavenHydroFramework-extra`, Public; or with the GitHub CLI:
`gh repo create rarabzad/RavenHydroFramework-extra --public`. Then push its history from the bundle:

```
# [2-extra] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  test ! -e RavenHydroFramework-extra || {{ echo "STOP: RavenHydroFramework-extra exists: remove or rename it first"; exit 1; }}
  git clone -q -b {xb} handover/{xbundle} RavenHydroFramework-extra
  cd RavenHydroFramework-extra
  test "$(git rev-parse HEAD)" = {xt} || {{ echo "STOP: the bundle's {xb} is not at {xt}"; exit 1; }}
  git remote set-url origin {xu}.git
  git push -u origin {xb}
)
```

The first branch pushed becomes the default branch (`{xb}`); check it under Settings > General > Default branch. If
the repository was created with a README it is not empty, and the push is refused: delete and re-create it empty.

To publish it by its files instead (one commit, without the history):

```
# [2-extra-files] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  test ! -e RavenHydroFramework-extra-files || {{ echo "STOP: RavenHydroFramework-extra-files exists: remove or rename it first"; exit 1; }}
  mkdir RavenHydroFramework-extra-files
  cd RavenHydroFramework-extra-files
  git init -q
  git symbolic-ref HEAD refs/heads/{xb}
  tar -xzf ../handover/{xtar} --strip-components=1
  git add -A -f
  git commit -q -m "Raven + MODFLOW 6 coupling: documentation, examples, tests and tools, release {date}"
  TREE=$(git rev-parse "HEAD^{{tree}}")
  test "$TREE" = {xtree} || {{ echo "STOP: the commit's tree is $TREE, not {xtree}; nothing pushed"; exit 1; }}
  git remote add origin {xu}.git
  git push -u origin {xb}
)
```

## 3. Verify

Clone both repositories back from GitHub into `check/` (the block stops if that folder exists) and compare them with
the kit. The last line is `verify: PASS` or `verify: FAIL`:

```
# [3-verify] run in: the working folder (the one that holds handover/)
( set -eu
  test ! -e check || {{ echo "STOP: check/ exists: remove or rename it first"; exit 1; }}
  mkdir check
  cd check
  git clone -q -b {cb} {cu}.git RavenHydroFramework
  git clone -q {xu}.git RavenHydroFramework-extra
  ok=1
  C=$(git -C RavenHydroFramework rev-parse HEAD)
  if [ "$C" = {ct} ]; then
    N=$(git -C RavenHydroFramework rev-list --count HEAD)
    if [ "$N" = {cn} ]; then echo "code: commit {ct}, {cn} commits (1A)"; else echo "code: $N commits, not {cn}"; ok=0; fi
  elif git -C RavenHydroFramework merge-base --is-ancestor {ct} HEAD 2>/dev/null; then
    echo "code: $C, with the kit's {ct} in its history (step 4)"
  else
    T=$(git -C RavenHydroFramework rev-parse "HEAD^{{tree}}")
    if [ "$T" = {ctree} ]; then echo "code: $C, tree {ctree} (1B)"; else echo "code: $C, tree $T: neither the kit's commit nor its tree"; ok=0; fi
  fi
  if X=$(git -C RavenHydroFramework-extra rev-parse -q --verify HEAD); then
    B=$(git -C RavenHydroFramework-extra rev-parse --abbrev-ref HEAD)
    [ "$B" = {xb} ] && echo "extra: default branch {xb}" || {{ echo "extra: default branch $B, not {xb}"; ok=0; }}
    XT=$(git -C RavenHydroFramework-extra rev-parse "HEAD^{{tree}}")
    if [ "$X" = {xt} ]; then echo "extra: commit {xt}, $(git -C RavenHydroFramework-extra rev-list --count HEAD) commits (kit: {xn})"
    elif [ "$XT" = {xtree} ]; then echo "extra: $X, tree {xtree} (published by its files)"
    else echo "extra: $X, tree $XT: neither the kit's commit nor its tree"; ok=0; fi
  else
    echo "extra: the repository is empty: run step 2"; ok=0
  fi
  git -C RavenHydroFramework fsck --full --no-progress && echo "code: fsck clean" || ok=0
  git -C RavenHydroFramework-extra fsck --full --no-progress && echo "extra: fsck clean" || ok=0
  if [ $ok = 1 ]; then echo "verify: PASS"; else echo "verify: FAIL"; exit 1; fi
)
```

Then build Raven with the MODFLOW 6 library inside the clone (where the tests look for it), install it, run the install
check (it runs the installed Raven on a tiny coupled model and checks that it uses the library and Fortran runtime
beside it; it prints `install check: PASS`), and run the tests that need no MODFLOW library (a few minutes). On Windows
write `python` for `python3`:

```
# [3-build] run in: the working folder (the one that holds handover/)
( set -eu
  test -d check/RavenHydroFramework || {{ echo "STOP: run block 3-verify first"; exit 1; }}
  cd check
  cmake -S RavenHydroFramework -B RavenHydroFramework/build
  cmake --build RavenHydroFramework/build --config Release
  cmake --install RavenHydroFramework/build --prefix install --config Release
  python3 RavenHydroFramework/cmake/RavenMF6InstallCheck.py install/bin 6.8.1
  cd RavenHydroFramework-extra/tests
  python3 run_all.py --nolib
)
```

## 4. If GitHub's `{cb}` holds commits the kit does not

Block 1A-check lists them. The blocks below find them again by themselves: on `{cb}-before-release` once block
1A-replace has run, otherwise on `{cb}`. To see what they change:

```
# [4-show] run in: the working folder (the one that holds handover/)
( set -eu
  test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
  [ -d RavenHydroFramework/.git ] || git clone -q {cu}.git RavenHydroFramework
  cd RavenHydroFramework
  git fetch -q ../handover/{cbundle} "+refs/heads/{cb}:refs/remotes/handover/{cb}"
  git fetch -q --prune origin
  OLD=$(git rev-parse -q --verify refs/remotes/origin/{cb}-before-release || git rev-parse -q --verify refs/remotes/origin/{cb}) \
    || {{ echo "STOP: GitHub has neither {cb}-before-release nor {cb}"; exit 1; }}
  echo "commits on $OLD that the kit does not hold:"
  git log --oneline "handover/{cb}..$OLD"
  git diff --stat handover/{cb} "$OLD"
)
```

Then choose:

- **They are not needed** (for example an earlier upload that the kit's history replaces): publish with block
  1A-replace; `{cb}-before-release` keeps them on GitHub.
- **They hold work to keep**: put them on top of the kit's branch in a local branch `release` (block 4-keep), check the
  result (build, `run_all.py --quick`), and publish it (block 4-keep-push). If a commit does not apply cleanly, git stops
  and names the files: resolve them inside `RavenHydroFramework/`, run `git cherry-pick --continue` there until it
  ends, then go on with 4-keep-push.

  ```
  # [4-keep] run in: the working folder (the one that holds handover/)
  ( set -eu
    test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
    [ -d RavenHydroFramework/.git ] || git clone -q {cu}.git RavenHydroFramework
    cd RavenHydroFramework
    git fetch -q ../handover/{cbundle} "+refs/heads/{cb}:refs/remotes/handover/{cb}"
    git fetch -q --prune origin
    OLD=$(git rev-parse -q --verify refs/remotes/origin/{cb}-before-release || git rev-parse -q --verify refs/remotes/origin/{cb}) \
      || {{ echo "STOP: GitHub has neither {cb}-before-release nor {cb}"; exit 1; }}
    PICK=$(git rev-list --reverse --no-merges "handover/{cb}..$OLD")
    test -n "$PICK" || {{ echo "nothing to keep: $OLD holds no commit the kit does not"; exit 0; }}
    if git rev-parse -q --verify refs/heads/release >/dev/null; then
      echo "STOP: branch release exists (an earlier 4-keep): publish it with block 4-keep-push, or delete it with"
      echo "      git -C RavenHydroFramework branch -D release   and run this block again"; exit 1
    fi
    git checkout -q -b release handover/{cb}
    git cherry-pick $PICK
    echo "branch release: the kit's {cb} with the kept commits on top; check it, then run block 4-keep-push"
  )
  ```

  ```
  # [4-keep-push] run in: the working folder (the one that holds handover/)
  ( set -eu
    test -d RavenHydroFramework/.git || {{ echo "STOP: run this in the folder that holds RavenHydroFramework/ (block 4-keep)"; exit 1; }}
    cd RavenHydroFramework
    git rev-parse -q --verify refs/heads/release >/dev/null || {{ echo "STOP: no branch release: run block 4-keep first"; exit 1; }}
    git merge-base --is-ancestor {ct} release || {{ echo "STOP: release does not hold the kit's {ct}"; exit 1; }}
    git fetch -q --prune origin
    if ! CUR=$(git rev-parse -q --verify refs/remotes/origin/{cb}); then
      git push origin "refs/heads/release:refs/heads/{cb}"; exit 0
    fi
    if git merge-base --is-ancestor "$CUR" release; then
      git push origin "refs/heads/release:refs/heads/{cb}"; exit 0
    fi
    if BAK=$(git rev-parse -q --verify refs/remotes/origin/{cb}-before-release); then
      git merge-base --is-ancestor "$CUR" "$BAK" || {{ echo "STOP: {cb}-before-release exists on GitHub and does not hold $CUR"; exit 1; }}
    else
      git push origin "$CUR:refs/heads/{cb}-before-release"
    fi
    git push --force-with-lease="refs/heads/{cb}:$CUR" origin "refs/heads/release:refs/heads/{cb}"
  )
  ```

  The published tip is then a new commit with `{ct}` in its history.
- **Keep both histories as they are**: merge them (no force push: the result holds GitHub's branch). If the merge
  stops on conflicts, resolve them inside `RavenHydroFramework/`, run `git commit` there, and run the block again.

  ```
  # [4-merge] run in: the working folder (the one that holds handover/)
  ( set -eu
    test -d handover || {{ echo "STOP: run this in the folder that holds handover/"; exit 1; }}
    [ -d RavenHydroFramework/.git ] || git clone -q {cu}.git RavenHydroFramework
    cd RavenHydroFramework
    git fetch -q ../handover/{cbundle} "+refs/heads/{cb}:refs/remotes/handover/{cb}"
    git fetch -q --prune origin
    OLD=$(git rev-parse -q --verify refs/remotes/origin/{cb}-before-release || git rev-parse -q --verify refs/remotes/origin/{cb}) \
      || {{ echo "STOP: GitHub has neither {cb}-before-release nor {cb}"; exit 1; }}
    if ! git rev-parse -q --verify refs/heads/release-merge >/dev/null; then
      git checkout -q -b release-merge handover/{cb}
      git merge --no-edit "$OLD"
    fi
    git checkout -q release-merge
    git merge-base --is-ancestor "$OLD" release-merge || {{ echo "STOP: release-merge does not hold $OLD"; exit 1; }}
    git push origin "refs/heads/release-merge:refs/heads/{cb}"
  )
  ```

  The published tip is a merge commit with `{ct}` as one parent. (If block 1A-replace has run, GitHub's `{cb}` is the
  kit's tip and this push is a fast-forward too.)

## 5. Afterwards

- The README, user guide and manual tell users to clone `{cb}` of RavenHydroFramework and `{xb}` of
  RavenHydroFramework-extra; nothing in them changes when you publish.
- The release package's `source/` folder holds the same histories as bundles (branches `{cb}` and `{xb}`) for users
  without network access.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('code'); ap.add_argument('extra')
    ap.add_argument('--code-rev', default='soil-zone'); ap.add_argument('--extra-rev', default='soil-zone')
    ap.add_argument('--code-branch', default='mf6-coupling'); ap.add_argument('--extra-branch', default='main')
    ap.add_argument('--out', default='handover')
    ap.add_argument('--no-public-check', action='store_true', help='do not read the public repositories')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit('%s exists and is not empty: give a new or empty folder' % out)
    os.makedirs(out, exist_ok=True)
    br = {'code': a.code_branch, 'extra': a.extra_branch}
    files = {k: {'bundle': '%s_%s.bundle' % (NAME[k], br[k]), 'tar': '%s_%s.tar.gz' % (NAME[k], br[k])} for k in br}
    tmp = tempfile.mkdtemp(prefix='handover_')
    fails, rec, pubs = [], {}, {}
    try:
        for k, repo, rev in (('code', a.code, a.code_rev), ('extra', a.extra, a.extra_rev)):
            print('%s: %s %s -> branch %s' % (k, repo, rev, br[k]), flush=True)
            pub, tip, n = ps.publish_repo(repo, rev, br[k], tmp, k)
            pubs[k] = pub
            g = lambda *x: ps.git(list(x), pub)
            rec[k] = dict(tip=tip, n=n, branch=br[k], tree=g('rev-parse', tip + '^{tree}'),
                          date=g('log', '-1', '--format=%cs', tip), subject=g('log', '-1', '--format=%s', tip))
            ps.bundle(pub, br[k], os.path.join(out, files[k]['bundle']))
            ps.git(['archive', '--format=tar.gz', '--prefix=%s/' % NAME[k], '-o', os.path.join(out, files[k]['tar']), tip], pub)
        os.makedirs(os.path.join(tmp, 'verify'))
        for k in ('code', 'extra'):
            for kind, bad in (('bundle', check_bundle(os.path.join(out, files[k]['bundle']), k, rec, tmp)),
                              ('archive', check_archive(os.path.join(out, files[k]['tar']), k))):
                print('  %-5s %-7s %s' % (k, kind, 'ok' if not bad else 'FAIL: ' + '; '.join(bad)), flush=True)
                fails += bad
        public = ['(not checked: --no-public-check)'] if a.no_public_check else public_state(pubs['code'], rec, tmp)
        c, x = rec['code'], rec['extra']
        text = HANDOVER.format(cu=PUBLIC['code'], xu=PUBLIC['extra'], cb=br['code'], xb=br['extra'], ct=c['tip'], xt=x['tip'],
                               cn=c['n'], xn=x['n'], ctree=c['tree'], xtree=x['tree'], cbundle=files['code']['bundle'],
                               xbundle=files['extra']['bundle'], ctar=files['code']['tar'], xtar=files['extra']['tar'],
                               date=max(c['date'], x['date']), public='\n'.join('- ' + l for l in public))
        open(os.path.join(out, 'HANDOVER.md'), 'w').write(text)
        with open(os.path.join(out, 'KIT.txt'), 'w') as f:
            for k in ('code', 'extra'):
                r = rec[k]
                f.write('%s: %s branch %s, commit %s (%s, "%s"), tree %s, %d commits; files %s, %s\n'
                        % (k, PUBLIC[k], r['branch'], r['tip'], r['date'], r['subject'], r['tree'], r['n'], files[k]['bundle'], files[k]['tar']))
            f.write(''.join('public: %s\n' % l for l in public))
        with open(os.path.join(out, 'SHA256SUMS.txt'), 'w') as f:
            for n in sorted(os.listdir(out)):
                if n != 'SHA256SUMS.txt':
                    f.write('%s  %s\n' % (sha256(os.path.join(out, n)), n))
        print('HANDOVER.md, its blocks run as written against local stand-ins for GitHub:', flush=True)
        fails += run_blocks(text, out, rec, pubs, tmp)
        print(open(os.path.join(out, 'KIT.txt')).read(), end='')
        for f in fails:
            print('FAIL: ' + f)
        print('hand-over kit %s: %s' % (out, 'PASS' if not fails else 'FAIL'))
        return 1 if fails else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
