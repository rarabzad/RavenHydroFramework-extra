"""Input handling of :SoilZone PHYSICAL (short runs of the T1 column).

I1 HYDRAUL_COND missing for the class of the bottom soil-zone layer: the run stops (Raven's automatic value is a
   placeholder, so the soil zone must not run on it). Classes outside the soil zone do not need it (the Liard test T7
   has such classes).
I2 :SoilZoneIteration with only the update count (tolerances keep their defaults) is accepted.
I3 :SoilZone PHYSICAL followed by :SoilZone CONCEPTUAL: the last one counts (a conceptual run, no soil-zone output,
   HYDRAUL_COND not required).
I4 soil-zone options under CONCEPTUAL are reported as ignored.
I5 a :GWSoilZoneColumns block that does not match the columns (one column missing) is reported, and the run starts the
   columns from the water table.
I6 the same block with its rows in another order is used (columns are matched by their cell).
I7 groundwater lines and blocks in the .rvc of a run without :GroundwaterModel are skipped (each to its own end line)
   and Raven's initial conditions after them still apply.
I8 a :SurfaceWaterExchange on a soil-zone layer of a soil-zone HRU is refused (that layer already exchanges with the
   aquifer through the soil zone)
I9 a damaged :GWHeads header in the .rvc: a negative count (":GWHeads -1 2 2") and a huge one (":GWHeads
   100000 100000 100000") stop the run with a clear message (ExitGracefully: "counts must be positive"), not an uncaught
   exception (std::length_error / std::bad_alloc, "terminate called").
I10 :StartTime of the .rvc (Raven core, ParseInitialConditionFile.cpp): the offset of the run's start from the
   start of the run that wrote the file is computed from the run's real start date (it read an end date that was never
   set). A run without :GroundwaterModel (the I7 model, 2 days) from an .rvc with :StartTime under valgrind: no
   "uninitialised value" in ParseInitialConditionsFile / TimeDifference (SKIP when valgrind is not installed).
"""
import os, sys, shutil, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'inputs')

def case(name, **kw):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    kw.setdefault('days', 5)
    sz_models.make_case(d, **kw)
    return d

def edit(path, old, new):
    t = open(path).read(); assert old in t, (path, old); open(path, 'w').write(t.replace(old, new))

def errors(d):
    p = os.path.join(d, 'out', 'Raven_errors.txt')
    return open(p).read() if os.path.exists(p) else ''

def drop_hydraul_cond(d):
    p = os.path.join(d, 'm.rvp'); t = open(p).read()
    t = t.replace(', HYDRAUL_COND, MAX_PERC_RATE', ', MAX_PERC_RATE').replace('none, mm_per_d, mm_per_d', 'none, mm_per_d')
    t = re.sub(r'(\[DEFAULT\], [^,\n]+, [^,\n]+, [^,\n]+), [^,\n]+, ([^,\n]+\n)', r'\1, \2', t, count=1)
    open(p, 'w').write(t)

def main():
    res = []
    d = case('I1'); drop_hydraul_cond(d)
    ok, txt = sz_check.run(d)
    msg = 'needs HYDRAUL_COND' in (txt + errors(d))
    res.append(('I1 missing HYDRAUL_COND stops the run', (not ok) and msg))

    d = case('I2', extra_rvg=':SoilZoneIteration 0\n')
    ok, txt = sz_check.run(d)
    b = sz_check.outputs(d)[0] if ok else None
    res.append(('I2 :SoilZoneIteration 0 (tolerances default)', ok and b is not None and int(b['interface updates'].max()) == 0))

    d = case('I3', extra_rvg=':SoilZone CONCEPTUAL\n'); drop_hydraul_cond(d)
    ok, txt = sz_check.run(d)
    res.append(('I3 the last :SoilZone counts', ok and not os.path.exists(os.path.join(d, 'out', 'GWSoilExchange.csv'))))

    d = case('I4', physical=False, extra_rvg=':SoilZoneSubgrid 3\n:SoilZoneIteration 5\n')
    ok, txt = sz_check.run(d)
    res.append(('I4 soil-zone options under CONCEPTUAL reported', ok and re.search(r'ParseGWFile: (:SoilZone\w+ ?)+ignored', errors(d)) is not None
                and ':SoilZoneSubgrid' in errors(d) and ':SoilZoneIteration' in errors(d)))

    d0 = case('I5a')
    ok0, _ = sz_check.run(d0)
    ok = False
    if ok0:
        t = open(os.path.join(d0, 'out', 'solution.rvc')).read()
        blk = re.search(r':GWSoilZoneColumns[^\n]*\n(.*?):EndGWSoilZoneColumns', t, re.S)
        rows = blk.group(1).strip().split('\n') if blk else []
        if len(rows) >= 2:
            t = t.replace(rows[-1] + '\n', '', 1)                       # drop the last column of the HRU
            d = case('I5', days=2)
            open(os.path.join(d, 'm.rvc'), 'w').write(t)
            for f in ('m.rvi', 'm.rvt'):
                edit(os.path.join(d, f), '2000-01-01 00:00:00', '2000-01-06 00:00:00')
            ok, txt = sz_check.run(d)
            ok = ok and 'do not match its soil-zone columns' in errors(d)
    res.append(('I5 mismatched hotstart columns reported', ok))

    ok = False
    if ok0:   # rows in another order: columns are matched by cell, so the run uses them (no mismatch)
        t = open(os.path.join(d0, 'out', 'solution.rvc')).read()
        blk = re.search(r'(:GWSoilZoneColumns[^\n]*\n)(.*?)(:EndGWSoilZoneColumns)', t, re.S)
        rows = blk.group(2).strip('\n').split('\n')
        t = t.replace(blk.group(0), blk.group(1) + '\n'.join(rows[::-1]) + '\n' + blk.group(3))
        d = case('I6', days=2)
        open(os.path.join(d, 'm.rvc'), 'w').write(t)
        for f in ('m.rvi', 'm.rvt'):
            edit(os.path.join(d, f), '2000-01-01 00:00:00', '2000-01-06 00:00:00')
        ok, txt = sz_check.run(d)
        ok = ok and 'do not match its soil-zone columns' not in errors(d) and len(rows) >= 3
    res.append(('I6 hotstart columns matched by cell, not by order', ok))

    # I7: groundwater lines in the .rvc of a run without :GroundwaterModel are skipped, each block to its own end line,
    # and Raven's own initial conditions after them still apply
    d = case('I7', physical=False)
    edit(os.path.join(d, 'm.rvi'), ':GroundwaterModel MODFLOW6\n', '')
    p = os.path.join(d, 'm.rvc'); t = open(p).read()
    open(p, 'w').write(':InitialGWHeads DEPTH_BELOW_SURFACE 2\n' + t + ':GWRechargeStore\n  1, 5.0\n:EndGWRechargeStore\n')
    ok, txt = sz_check.run(d)
    good = False
    if ok:
        import pandas as pd
        w = pd.read_csv(os.path.join(d, 'out', 'WatershedStorage.csv'))
        cs = [c for c in w.columns if 'SOIL[0]' in c or 'Soil Water[0]' in c]
        good = bool(cs) and abs(float(w[cs[0]].iloc[0]) - 100.0) < 1.0 and 'ignored (the model has no' in errors(d)
        if not good:
            print('  I7: columns %s, first row %s' % (cs, w.iloc[0].to_dict() if len(w) else None))
    res.append(('I7 .rvc groundwater blocks skipped without :GroundwaterModel', good))

    d = case('I8', extra_rvg=':SurfaceWaterExchange SOIL[0] ALLH LEAKANCE 1.0\n')
    p = os.path.join(d, 'm.rvh'); h = open(p).read()
    ids = [l.split(',')[0].strip() for l in h.split(':HRUs')[1].split(':EndHRUs')[0].split('\n') if l.strip() and not l.strip().startswith(':')]
    open(p, 'a').write('\n:HRUGroup ALLH\n  %s\n:EndHRUGroup\n' % ', '.join(ids))
    ok, txt = sz_check.run(d)
    res.append(('I8 surface exchange on a soil-zone layer refused', (not ok) and 'exchanges with the aquifer through the soil zone already' in (txt + errors(d))))
    # I9: a damaged :GWHeads header
    good = ok0
    if ok0:
        t0 = open(os.path.join(d0, 'out', 'solution.rvc')).read()
        for k, hdr in (('neg', ':GWHeads -1 2 2'), ('huge', ':GWHeads 100000 100000 100000')):
            t = re.sub(r':GWHeads +\d+ +\d+ +\d+', hdr, t0, count=1)
            d = case('I9_%s' % k, days=2)
            open(os.path.join(d, 'm.rvc'), 'w').write(t)
            for f in ('m.rvi', 'm.rvt'):
                edit(os.path.join(d, f), '2000-01-01 00:00:00', '2000-01-06 00:00:00')
            ok, txt = sz_check.run(d)
            msg = 'counts must be positive' in (txt + errors(d))
            crash = ('terminate called' in txt) or ('bad_alloc' in txt) or ('length_error' in txt)
            print('  I9 %s: %s, message %s%s' % (hdr, 'stopped' if not ok else 'RAN', 'present' if msg else 'MISSING', ', CRASH' if crash else ''))
            good &= (not ok) and msg and not crash
    res.append(('I9 damaged :GWHeads header: clear error', good))

    # I10: :StartTime of the .rvc under valgrind
    import shutil as _sh, subprocess
    if _sh.which('valgrind') is None:
        sz_check.tc.skip('I10 :StartTime under valgrind', 'valgrind is not installed') if hasattr(sz_check.tc, 'skip') else print('SKIP I10: valgrind is not installed')
    else:
        d = case('I10', physical=False, days=2)
        edit(os.path.join(d, 'm.rvi'), ':GroundwaterModel MODFLOW6\n', '')
        p = os.path.join(d, 'm.rvc'); t = open(p).read()
        open(p, 'w').write(':StartTime 1999-12-01 00:00:00\n:TimeStamp 2000-01-01 00:00:00\n' + t)
        os.makedirs(os.path.join(d, 'out'), exist_ok=True)
        r = subprocess.run(['valgrind', '--error-exitcode=0', sz_check.tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True,
                           env=sz_check.tc.ENV, timeout=1800)
        log = r.stdout + r.stderr
        uninit = [l for l in log.split('\n') if 'uninitialised' in l]
        blk = re.findall(r'(?:Conditional jump|Use of uninitialised)[^\n]*\n(?:==\d+==[^\n]*\n){1,6}', log)
        here = [x for x in blk if ('TimeDifference' in x) or ('ParseInitialConditions' in x)]
        good = ('Successful Simulation' in log) and not here
        print('  I10: valgrind: %d "uninitialised" reports, %d in TimeDifference / ParseInitialConditionsFile -> %s'
              % (len(uninit), len(here), 'ok' if good else 'FAIL'))
        res.append(('I10 :StartTime of the .rvc: no uninitialised read', good))
    for n, g in res:
        print('  %-50s %s' % (n, 'ok' if g else 'FAILED'))
    good = all(g for _, g in res)
    print('input tests: %s' % ('ALL PASSED' if good else 'FAILED'))
    return good

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
