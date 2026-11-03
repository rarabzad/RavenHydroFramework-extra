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
I11 a :BoundaryHead or :WellFlowRate time series that names no boundary or well: ":BoundaryHead NOPE"
   beside a specified-head boundary EDGE, and ":WellFlowRate 7" when the only well is 1, stop the run naming the series
   and the boundaries / wells there are (they were dropped silently: EDGE kept its constant HEAD); the correct names run.
I12 options given where they do nothing: on a model Raven builds, :SeepageToRaven, :KeepPackages, :MF6StartDate and
   :MF6Model each stop the run ("apply only to an existing model"); :SoilZoneVadoseClasses and :SoilZoneVadoseInitialFlux
   with :SoilZoneVadose NONE, and :SoilZoneAquiferClass on a generated model, are reported as ignored (Raven_errors.txt);
   an unknown :AquiferProfileParameters attribute (INITIAL_HEAD_DEPHT) and LAYERS BOTTOM on a boundary stop the run.
I13 messages: a missing .rvg file is named in Raven_errors.txt ("Cannot find or read .rvg file"), and a :Wells row
   with a missing value names the :Wells table (not ":EndWells").
I14 age tracer across a hotstart (Raven core, no :GroundwaterModel): a 2-layer soil model with
   :Transport AGE, 20 days continuous against 7 + 7 + 6 days chained through solution.rvc: the ages of every store
   (Ages.csv) and of the outflow (AGEPollutographs.csv) equal the continuous run's within 1e-3 d (the .rvc carries 6
   digits), and each solution.rvc carries :StartTime 2000-01-01, the datum of its entry times. Before, the offset never
   reached the ages (each restart reported them 7 or 14 days too young).
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

    # I11: time series that name no boundary or well
    def run_err(d):
        ok, txt = sz_check.run(d); return ok, txt + errors(d)
    good = True
    d = case('I11_bnd', days=3, chd=99.0)
    open(os.path.join(d, 'm.rvt'), 'a').write('\n:BoundaryHead NOPE m\n  2000-01-01 00:00:00 1.0 3\n  99.5\n  99.5\n  99.5\n:EndBoundaryHead\n')
    ok, txt = run_err(d)
    m1 = ':BoundaryHead NOPE in the .rvt file names no' in txt and 'boundaries: EDGE' in txt
    good &= (not ok) and m1
    edit(os.path.join(d, 'm.rvt'), ':BoundaryHead NOPE', ':BoundaryHead EDGE')
    ok2, txt2 = run_err(d)
    good &= ok2
    lon, lat = sz_models.ll(0.0, 0.0)
    d = case('I11_well', days=3, extra_rvg=':Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT\n'
             '  1, PW_1, %.6f, %.6f, 95.0, 85.0\n:EndWells\n' % (lat, lon))
    open(os.path.join(d, 'm.rvt'), 'a').write('\n:WellFlowRate 7 m3/d\n  2000-01-01 00:00:00 1.0 3\n  -10\n  -10\n  -10\n:EndWellFlowRate\n')
    ok, txt = run_err(d)
    m2 = ':WellFlowRate 7 in the .rvt file names no well' in txt and 'well IDs: 1' in txt
    good &= (not ok) and m2
    edit(os.path.join(d, 'm.rvt'), ':WellFlowRate 7', ':WellFlowRate 1')
    ok3, txt3 = run_err(d)
    good &= ok3
    print('  I11: :BoundaryHead NOPE stops with the message %s, EDGE runs %s; :WellFlowRate 7 stops with the message %s, well 1 runs %s'
          % (m1, ok2, m2, ok3))
    res.append(('I11 series naming no boundary or well stop the run', good))

    # I12: options given where they do nothing
    good = True
    for opt in (':SeepageToRaven OFF', ':KeepPackages RCH', ':MF6StartDate 2000-01-01', ':MF6Model GWF'):
        d = case('I12_%s' % opt.split()[0][1:], days=2, extra_rvg=opt + '\n')
        ok, txt = run_err(d)
        g = (not ok) and ('%s apply only to an existing model' % opt.split()[0]) in txt
        print('  I12 %-26s %s' % (opt, 'stops with the message' if g else ('RAN' if ok else 'stops, message missing')))
        good &= g
    d = case('I12_vzcls', days=2, extra_rvg=':SoilZoneVadoseClasses 3\n:SoilZoneVadoseInitialFlux 1.0\n:SoilZoneAquiferClass SAND\n')
    ok, txt = run_err(d)
    w1 = ':SoilZoneVadoseClasses :SoilZoneVadoseInitialFlux ignored: these apply only to unsaturated columns' in txt
    w2 = ':SoilZoneAquiferClass ignored: it applies only to an existing model' in txt
    print('  I12 classes / initial flux with NONE: %s; aquifer class on a generated model: %s' % ('reported' if w1 else 'NOT reported', 'reported' if w2 else 'NOT reported'))
    good &= ok and w1 and w2
    d = case('I12_prof', days=2)
    edit(os.path.join(d, 'm.rvp'), 'INITIAL_HEAD_DEPTH,', 'INITIAL_HEAD_DEPHT,')
    ok, txt = run_err(d)
    g = (not ok) and 'unknown aquifer profile parameter INITIAL_HEAD_DEPHT' in txt
    print('  I12 profile attribute INITIAL_HEAD_DEPHT: %s' % ('stops' if g else 'NOT stopped'))
    good &= g
    d = case('I12_layers', days=2, chd=99.0)
    edit(os.path.join(d, 'm.rvg'), 'HEAD 99\n', 'HEAD 99 LAYERS BOTTOM\n')
    ok, txt = run_err(d)
    g = (not ok) and 'LAYERS must be ALL or TOP, not BOTTOM' in txt
    print('  I12 LAYERS BOTTOM: %s' % ('stops' if g else 'NOT stopped'))
    good &= g
    res.append(('I12 options that do nothing: stop or warning', good))

    # I13: messages
    d = case('I13_rvg', days=2); os.remove(os.path.join(d, 'm.rvg'))
    ok, txt = run_err(d)
    g1 = (not ok) and 'Cannot find or read .rvg file' in errors(d)
    d = case('I13_wells', days=2, extra_rvg=':Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT\n'
             '  1, PW_1, %.6f, %.6f, 95.0\n:EndWells\n' % (lat, lon))
    ok, txt = run_err(d)
    g2 = (not ok) and 'a row of the :Wells table' in txt and ':EndWells table' not in txt
    print('  I13 missing .rvg named in Raven_errors.txt: %s; short :Wells row names :Wells: %s' % (g1, g2))
    res.append(('I13 messages name the file and the table', g1 and g2))

    # I14: age tracer across hotstarts (no groundwater)
    import pandas as pd
    def age_case(name, days, start=None, rvc=None):
        d = case(name, physical=False, days=20, rain=[5.0, 0.0, 12.0, 0.0, 3.0] * 4, perc=2.0)
        pr = os.path.join(d, 'm.rvi'); tx = open(pr).read().replace(':GroundwaterModel MODFLOW6\n', '')
        tx = tx.replace(':EndHydrologicProcesses\n', ':EndHydrologicProcesses\n:Transport AGE\n')
        tx = re.sub(r':Duration \d+', ':Duration %d' % days, tx)
        if start: tx = tx.replace(':StartDate 2000-01-01', ':StartDate ' + start)
        open(pr, 'w').write(tx)
        if rvc: shutil.copy(rvc, os.path.join(d, 'm.rvc'))
        ok, txt = sz_check.run(d)
        return d, ok
    dc, okc = age_case('I14_cont', 20)
    chain = []; prev = None; good = okc
    for i, (start, n) in enumerate((('2000-01-01', 7), ('2000-01-08', 7), ('2000-01-15', 6))):
        d, ok = age_case('I14_part%d' % (i + 1), n, start if i else None, prev)
        good &= ok; chain.append((d, 7 * i)); prev = os.path.join(d, 'out', 'solution.rvc')
    worst = {}; st = []
    if good:
        c = pd.read_csv(os.path.join(dc, 'out', 'Ages.csv')); cp = pd.read_csv(os.path.join(dc, 'out', 'AGEPollutographs.csv'))
        for d, t0 in chain:
            b = pd.read_csv(os.path.join(d, 'out', 'Ages.csv')); bp = pd.read_csv(os.path.join(d, 'out', 'AGEPollutographs.csv'))
            cc = c[c['time[d]'] >= t0].reset_index(drop=True).iloc[:len(b)]; ccp = cp.iloc[t0:t0 + len(bp)].reset_index(drop=True)
            for col in [x for x in b.columns if x.endswith('[d]') and x != 'time[d]']:
                v = (pd.to_numeric(cc[col], errors='coerce') - pd.to_numeric(b[col], errors='coerce')).abs().max()
                worst[col] = max(worst.get(col, 0.0), float(0.0 if pd.isna(v) else v))
            for col in [x for x in bp.columns if x.endswith('[d]') and not x.startswith('time')]:
                v = (pd.to_numeric(ccp[col], errors='coerce') - pd.to_numeric(bp[col], errors='coerce')).abs().max()
                worst['outflow ' + col] = max(worst.get('outflow ' + col, 0.0), float(0.0 if pd.isna(v) else v))
            st.append(open(os.path.join(d, 'out', 'solution.rvc')).readline().strip())
        good = bool(worst) and max(worst.values()) < 1e-3 and all(s.startswith(':StartTime 2000-01-01') for s in st)
    print('  I14: largest age difference to the continuous run by store: %s; :StartTime of the solution.rvc files: %s'
          % (', '.join('%s %.3g d' % (k, v) for k, v in worst.items()), st))
    res.append(('I14 age tracer: restarts equal the continuous run', good))
    for n, g in res:
        print('  %-50s %s' % (n, 'ok' if g else 'FAILED'))
    good = all(g for _, g in res)
    print('input tests: %s' % ('ALL PASSED' if good else 'FAILED'))
    return good

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
