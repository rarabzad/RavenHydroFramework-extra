"""The words that describe how the work was organised rather than what it does: the one list of them.

Commit messages of the coupling's commits must not contain them (the commit-message tool imports RULE from this file),
and make_package.py builds its README check (PROCESS) from RULE_SOURCE plus a few words of its own, so the README
check finds everything the commit-message rule finds. Change the words here only.

RULE finds: audit (not tools_audit), phase or round numbers, replay, findings, version and task numbers (v2, _v3,
v3build, t123), finding IDs (SZ-12, A3, D1-D2, R12-3), WIP, coordinator, usage-limit, work in progress, rb-* branch
names, integ, merge3, still to come, completed, rebuilt, recovered, reconstructed, history, placeholder, first full
version, final form, final audited, honest, no longer, previously, not rebuilt, draft, pending, git's "# Conflicts:"
list, "conflicts ... resolved", regenerated, "brought ... up to", up to date, revised, revision, taken out, to be
filled, left to fill, first release, review, reviewed, reviewer, "merged build" and "built (2026...".
"""
import re

RULE_SOURCE = (
    r'(?<!tools_)audit|\bphase\s*\d|\bphase\s+[A-Z]\b|\bphase\s+\d|\bround\s*\d|\bround-\d|\brounds?\s+\d|replay|\bfindings\b|'
    r'(?<![A-Za-z0-9])v[1-9][0-9]?[a-z]?\b|_v[1-9]|v[1-9]build|\bt[0-9]{3}\b|'                      # versions, task numbers
    r'\b(?:CB|SZ|VZ|IB|MT|BR|RS|WS|SV)-?\d+(?:-\d+)?\b|\bA[1-9]\b|\bD[1-9](?:-D[1-9])?\b|\bR1[0-9]?-\d\b|'  # finding IDs
    r'\bWIP\b|coordinator|usage-limit|work in progress|\brb-[a-z0-9]+|\binteg\b|\bmerge\d|'          # process wording
    r'\bstill to come\b|\bcompleted\b|'
    r'\brebuil|\brecover|\breconstruct|\bhistory\b|placeholder|first full version|final form|final audited|honest|'
    r'\bno longer\b|\bpreviously\b|\bnot rebuilt\b|\bdraft\b|\bpending\b|'
    r'(?m:^[ \t]*#\s*Conflicts:)|\bconflicts?\b[^.\n]*\bresolved\b|'                                # git's merge notes
    r'\bregenerat|\bbr(?:ought|ing|inging)\b[^.\n]{0,60}\bup to\b|\bup to date\b|\brevis(?:ed|ions?)\b|'  # "made again" wording
    r'\btaken out\b|\bto be filled\b|\bleft to fill\b|\bfirst[- ]release\b|\breview(?:ed|er|s)?\b|'
    r'\bmerged build\b|\bbuilt\s*\(\d')
RULE = re.compile(RULE_SOURCE, re.I)
