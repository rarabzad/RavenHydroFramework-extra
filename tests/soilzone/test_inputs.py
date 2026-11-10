"""Input handling of :SoilZone PHYSICAL (short runs of the CT1 column).

I1 HYDRAUL_COND missing for the class of the bottom soil-zone layer: the run stops (Raven's automatic value is a
   placeholder, so the soil zone must not run on it). Classes outside the soil zone do not need it (the Liard test LP1
   has such classes).
I2 :SoilZoneIteration with only the update count is accepted (here 0: explicit coupling, no interface update in any step;
   the tolerances keep their defaults, which explicit coupling does not use).
I3 :SoilZone PHYSICAL followed by :SoilZone CONCEPTUAL: the last one counts (a conceptual run, no soil-zone output,
   HYDRAUL_COND not required).
I4 soil-zone options under CONCEPTUAL are reported as ignored.
I5 a :GWSoilZoneColumns block that does not match the columns (one column missing) is reported (warning "do not match its
   soil-zone columns") and the run completes; that the columns then start from the water table is not checked here.
I6 the same block with its rows in another order is used (columns are matched by their cell).
I7 groundwater lines and blocks in the .rvc of a run without :GroundwaterModel are skipped (each to its own end line)
   and Raven's initial conditions after them still apply.
I8 a :SurfaceWaterExchange on a soil-zone layer of a soil-zone HRU is refused (that layer already exchanges with the
   aquifer through the soil zone)
I9 a damaged :GWHeads header in the .rvc: a negative count (":GWHeads -1 2 2") and a huge one (":GWHeads
   100000 100000 100000") stop the run with a clear message (ExitGracefully: "counts must be positive"), not an uncaught
   exception (std::length_error / std::bad_alloc, "terminate called").
I10 :StartTime of the .rvc: the offset of the run's start from the
   start of the run that wrote the file is computed from the run's real start date. A run without :GroundwaterModel (the I7 model, 2 days) from an .rvc with :StartTime under valgrind: no
   "uninitialised value" in ParseInitialConditionsFile / TimeDifference (SKIP when valgrind is not installed).
I11 a :BoundaryHead or :WellFlowRate time series that names no boundary or well: ":BoundaryHead NOPE"
   beside a specified-head boundary EDGE, and ":WellFlowRate 7" when the only well is 1, stop the run naming the series
   and the boundaries / wells there are (a series left unused would leave EDGE at its constant HEAD); the correct names run.
I12 options given where they do nothing: on a model Raven builds, :SeepageToRaven, :KeepPackages, :MF6StartDate and
   :MF6Model each stop the run ("apply only to an existing model"); :SoilZoneVadoseClasses and :SoilZoneVadoseInitialFlux
   with :SoilZoneVadose NONE, and :SoilZoneAquiferClass on a generated model, are reported as ignored (Raven_errors.txt);
   an unknown :AquiferProfileParameters attribute (INITIAL_HEAD_DEPHT) and LAYERS BOTTOM on a boundary stop the run.
I13 messages: a missing .rvg file is named in Raven_errors.txt ("Cannot find or read .rvg file"), and a :Wells row
   with a missing value names the :Wells table (not ":EndWells").
I14 age tracer across a hotstart (Raven core; no :GroundwaterModel): a 2-layer soil model with :Transport AGE, 20 days
   continuous against 7 + 7 + 6 days chained through solution.rvc: the ages of every store (Ages.csv) and of the outflow
   (AGEPollutographs.csv) equal the continuous run's within 2e-4 d plus 1e-5 of the age (Ages.csv writes 6 significant digits;
   the largest difference is 1e-4 d). Each solution.rvc carries
   :StartTime, the start of the run that wrote it, and, when the datum of its entry times is earlier (the restarted
   parts), :AgeTracerDatum 2000-01-01.
I15 the same across year boundaries: a chain 1999-12-25 (7 d), 2000-01-01 (7 d), 2000-01-08 (6 d) against 20 days in one
   run, and a multi-year chain 1998-12-20 (400 d), 2000-01-24 (380 d) against 780 days (full mode; quick: 1998-12-20
   (12 d), 1999-01-01 (400 d), 2000-02-05 (8 d) against 420 days). Every part runs, the ages equal the continuous run's
   within 2e-4 d plus 1e-5 of the age, and :AgeTracerDatum is the chain's first start written as a valid date (1999-12-25, 1998-12-20).
I16 an age-tracer run started from the solution.rvc of a spin-up run without the tracer (30 days, then 5 days with
   :Transport AGE): the file holds no age-tracer masses, so the initial water has age 0 (soil and groundwater ages 0 at
   the start, below 1.01 d after the first day), as in Raven without the coupling; the run's solution.rvc has no
   :AgeTracerDatum.
I17 EnKF members with their own :ExtraRVTFilename (ENKF_OPEN_FORECAST, 3 members, one well): each member's well rate is
   its own file's (-100, -200, -300 m3/d in GWBudget.csv "wells specified"), with no "has no :WellFlowRate" warning for
   the later members; an extra .rvt naming no well stops the member that reads it.
I18 damaged soil-zone hotstart values: a :GWSoilZoneColumns row with nan, one with negative water (-50 mm), and a
   :GWHeads value nan each stop the run with a message naming the block ("is not a finite number", "is negative");
   the undamaged file runs.
I19 Raven transport in a coupled run: :Transport Nitrate (CONCEPTUAL and PHYSICAL) and :Transport AGE with
   :GroundwaterModel MODFLOW6 stop the run naming the constituent (the coupling exchanges no constituent mass); the same
   model without :GroundwaterModel runs with :Transport Nitrate.
I20 a head boundary is placed with the highest head it has in the run: the specified head EDGE with HEAD 0 (below every
   cell) and a :BoundaryHead EDGE series of 99.5 m gets its cells (GWModelSummary "CHD cells" > 0) and holds the series'
   head (CHD flow in GWBudget.csv); the same boundary without the series has no cells, and a warning names it, its head
   and the highest cell bottom.
I21 a head boundary on steps whose :BoundaryHead value lies at or below a cell's bottom: 4 HRUs, layer 1 100 to 97 m,
   layer 2 97 to 79 m, boundary EDGE on the outlet column with HEAD 90 and a series 99 m on day 1, then 90 m.
   (a) GHB, LAYERS TOP, CONDUCTANCE 1000, aquifer at 95 m: on days 2-6 the GHB drains the aquifer (flow <= 0 on each day),
       as with HEAD 90 alone; a series of 90 m on every day gives the outputs of HEAD 90 alone (GWBudget.csv equal), and
       GWModelSummary.txt counts the cell-steps switched off ("head boundaries off").
   (b) CHD, LAYERS TOP, water table 98 m: on days 2-6 the water table under the outlet HRU falls below the bottom of layer 1
       (97 m): no cell is held at the bottom of layer 1.
   (c) CHD, LAYERS ALL, series 99, 99, 99, 90, 90, 90: the 6-day run against 3 + 3 days restarted from its solution.rvc:
       the same number of CHD cells, and CHD flow and heads equal on days 4-6 (1e-6).
   (d) a column with no cell held: 8 HRUs of 100 m (HRU 8 lies wholly on the boundary's column), CHD LAYERS ALL, rain
       20 mm/d, a series of 99 m on days 1-2 and 70 m (below the aquifer's bottom) on days 3-6, CONCEPTUAL and :SoilZone
       PHYSICAL: on days 3-6 the CHD flow is 0, nothing is booked onto CHD cells ('recharge onto CHD cells', and the soil
       zone's exchange with specified heads), MODFLOW's recharge equals Raven's (CONCEPTUAL), the column's soil-zone link
       exchanges with the aquifer (PHYSICAL), and every identity of combinations.check_run holds; on days 1-2 the boundary
       holds the column.
   (e) cells placed by the series alone: CHD and GHB, LAYERS TOP, HEAD 90 and a series of 99 m on every day: the boundary
       has the cells of layer 1 only (GWModelSummary.txt "GHB cells / CHD cells" 2), as a HEAD of 99 m gives, and none off.
   (f) a steady-state first period (:GWInitialization STEADY_STATE) whose series value (90 m, then 99, 99, 90, 90, 99)
       lies below the layer-1 cells' bottom: "head boundaries off" counts its 2 cells too (8 cell-steps against 6 without
       the steady period).
I22 strict numbers in the .rvc: ":InitialGWHeads ELEVATION 98,5" (a decimal comma: the tokens 98 and 5) stops with the
   surplus value '5', ":InitialGWHeads ELEVATION H98.5" and "0x62" (hexadecimal) stop with "'H98.5' is not a number", all
   naming the command; ":InitialGWHeads FROM_PROFILE 0" stops ("FROM_PROFILE takes no value"); ":InitialGWHeads ELEVATION
   98.5", "98.5# note" and "98.5 # note" (a trailing comment) run and start at 98.5 m; a :GWHeads value "98.5x" stops ("is
   not a finite number").
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

AGE_TOL, AGE_REL = 2e-4, 1e-5   # I14, I15: 2e-4 d plus the 6 significant digits Ages.csv writes (1e-5 of the age)

def age_diff(a, b):
    """largest |a - b| of two age columns [d], and whether any difference exceeds AGE_TOL + AGE_REL |a|"""
    import pandas as pd
    a = pd.to_numeric(a, errors='coerce'); b = pd.to_numeric(b, errors='coerce'); d = (a - b).abs()
    v = d.max(); over = bool((d > AGE_TOL + AGE_REL * a.abs()).any())
    return float(0.0 if pd.isna(v) else v), over

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
    worst = {}; st = []; over = False
    if good:
        c = pd.read_csv(os.path.join(dc, 'out', 'Ages.csv')); cp = pd.read_csv(os.path.join(dc, 'out', 'AGEPollutographs.csv'))
        for d, t0 in chain:
            b = pd.read_csv(os.path.join(d, 'out', 'Ages.csv')); bp = pd.read_csv(os.path.join(d, 'out', 'AGEPollutographs.csv'))
            cc = c[c['time[d]'] >= t0].reset_index(drop=True).iloc[:len(b)]; ccp = cp.iloc[t0:t0 + len(bp)].reset_index(drop=True)
            for col in [x for x in b.columns if x.endswith('[d]') and x != 'time[d]']:
                v, o = age_diff(cc[col], b[col]); over |= o
                worst[col] = max(worst.get(col, 0.0), v)
            for col in [x for x in bp.columns if x.endswith('[d]') and not x.startswith('time')]:
                v, o = age_diff(ccp[col], bp[col]); over |= o
                worst['outflow ' + col] = max(worst.get('outflow ' + col, 0.0), v)
            sol = open(os.path.join(d, 'out', 'solution.rvc')).read(); m = re.search(r':AgeTracerDatum (\S+)', sol)
            st.append((sol.split('\n')[0].strip(), m.group(1) if m else None))
        want = [(':StartTime 2000-01-%02d' % (1 + t0), None if t0 == 0 else '2000-01-01') for _, t0 in chain]
        good = bool(worst) and not over and all(s[0].startswith(w[0]) and s[1] == w[1] for s, w in zip(st, want))
    print('  I14: largest age difference to the continuous run by store: %s; :StartTime and :AgeTracerDatum of the solution.rvc files: %s'
          % (', '.join('%s %.3g d' % (k, v) for k, v in worst.items()), st))
    res.append(('I14 age tracer: restarts equal the continuous run', good))

    # I15: age-tracer chains across year boundaries; I16: spin-up without the tracer
    QUICK = os.environ.get('RAVEN_TEST_QUICK', '') not in ('', '0')
    import datetime
    def age2(name, d0, ntot, start, days, rvc=None, age=True):
        d = case(name, physical=False, days=ntot, rain=([5.0, 0.0, 12.0, 0.0, 3.0] * (ntot // 5 + 1))[:ntot], perc=2.0)
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(d, f); tx = open(p).read().replace('2000-01-01 00:00:00', d0 + ' 00:00:00')
            if f == 'm.rvi':
                tx = tx.replace(':GroundwaterModel MODFLOW6\n', '')
                if age: tx = tx.replace(':EndHydrologicProcesses\n', ':EndHydrologicProcesses\n:Transport AGE\n')
                tx = re.sub(r':Duration \d+', ':Duration %d' % days, tx).replace(':StartDate ' + d0, ':StartDate ' + start)
            open(p, 'w').write(tx)
        if rvc: shutil.copy(rvc, os.path.join(d, 'm.rvc'))
        ok, txt = sz_check.run(d)
        if not ok: print('  %s: run FAILED %s' % (name, txt[-400:].replace('\n', ' | ')))
        return d, ok
    def chain(tag, d0, parts):
        ntot = sum(parts); dc, ok = age2('%s_cont' % tag, d0, ntot, d0, ntot); good = ok; prev = None; t0 = 0; worst = 0.0; datums = []; over = False
        c = pd.read_csv(os.path.join(dc, 'out', 'Ages.csv')) if ok else None
        for i, n in enumerate(parts):
            st = (datetime.date(*map(int, d0.split('-'))) + datetime.timedelta(days=t0)).isoformat()
            d, ok = age2('%s_part%d' % (tag, i + 1), d0, ntot, st, n, prev); good &= ok
            if not ok: break
            b = pd.read_csv(os.path.join(d, 'out', 'Ages.csv')); cc = c[c['time[d]'] >= t0].reset_index(drop=True).iloc[:len(b)]
            for col in [x for x in b.columns if x.endswith('[d]') and x != 'time[d]']:
                v, o = age_diff(cc[col], b[col]); over |= o
                worst = max(worst, v)
            prev = os.path.join(d, 'out', 'solution.rvc'); t0 += n
            m = re.search(r':AgeTracerDatum (\S+)', open(prev).read()); datums.append(m.group(1) if m else None)
        g = good and not over and datums[0] is None and all(x == d0 for x in datums[1:])
        print('  I15 chain %s %s: parts run %s, largest age difference %.3g d, :AgeTracerDatum of the parts %s -> %s' % (d0, parts, good, worst, datums, 'ok' if g else 'FAIL'))
        return g
    g1 = chain('I15_ye', '1999-12-25', (7, 7, 6))
    g2 = chain('I15_my', '1998-12-20', (12, 400, 8) if QUICK else (400, 380))
    res.append(('I15 age-tracer chains across year boundaries', g1 and g2))
    ds, ok1 = age2('I16_spin', '2000-01-01', 35, '2000-01-01', 30, age=False)
    dr, ok2 = age2('I16_run', '2000-01-01', 35, '2000-01-31', 5, os.path.join(ds, 'out', 'solution.rvc'))
    good = ok1 and ok2
    if good:
        a = pd.read_csv(os.path.join(dr, 'out', 'Ages.csv')); cols = [x for x in a.columns if x.endswith('[d]') and x != 'time[d]']
        val = lambda r: pd.to_numeric(a[cols].iloc[r], errors='coerce').replace(-1.2345, float('nan')).abs().max()   # (-1.2345: no water)
        age0 = val(0); age1 = val(1)
        nod = ':AgeTracerDatum' not in open(os.path.join(dr, 'out', 'solution.rvc')).read()
        good = age0 < 1e-9 and age1 < 1.01 and nod
        print('  I16: largest age at the start %.3g d, after one day %.3g d; no :AgeTracerDatum written %s -> %s' % (age0, age1, nod, 'ok' if good else 'FAIL'))
    res.append(('I16 age tracer from a spin-up without it: ages start at 0', good))

    # I17: EnKF members' extra .rvt series
    d = case('I17_enkf', days=3, extra_rvg=':Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT\n'
             '  1, PW_1, %.6f, %.6f, 95.0, 85.0\n:EndWells\n' % (lat, lon))
    edit(os.path.join(d, 'm.rvi'), ':StartDate', ':EnsembleMode ENSEMBLE_ENKF 3\n:StartDate')
    open(os.path.join(d, 'm.rve'), 'w').write(':EnKFMode ENKF_OPEN_FORECAST\n:AssimilatedState SOIL[0] All\n:ForcingPerturbation TEMP_AVE DIST_NORMAL 0 0.000001 ADDITIVE\n'
                                              ':ExtraRVTFilename extra_*.rvt\n:OutputDirectoryFormat ./out/ens_*/\n')
    open(os.path.join(d, 'm.rvh'), 'a').write('\n:HRUGroup All\n  1\n:EndHRUGroup\n')
    for e in (1, 2, 3):
        os.makedirs(os.path.join(d, 'out', 'ens_%d' % e), exist_ok=True); shutil.copy(os.path.join(d, 'm.rvc'), os.path.join(d, 'out', 'ens_%d' % e, 'solution.rvc'))
    for e, q in ((1, -100), (2, -200), (3, -300)):
        open(os.path.join(d, 'extra_%d.rvt' % e), 'w').write(':WellFlowRate 1 m3/d\n  2000-01-01 00:00:00 1.0 3\n  %d\n  %d\n  %d\n:EndWellFlowRate\n' % (q, q, q))
    ok, txt = run_err(d)
    rates = []
    for e in (1, 2, 3):
        p = os.path.join(d, 'out', 'ens_%d' % e, 'GWBudget.csv')
        rates.append(float(pd.read_csv(p)['wells specified [m3/d]'].iloc[0]) if os.path.exists(p) else None)
    nw = errors(d).count('has no :WellFlowRate time series')
    g1 = ok and rates == [-100.0, -200.0, -300.0] and nw <= 1
    open(os.path.join(d, 'extra_2.rvt'), 'w').write(':WellFlowRate 7 m3/d\n  2000-01-01 00:00:00 1.0 3\n  -5\n  -5\n  -5\n:EndWellFlowRate\n')
    ok2, txt2 = run_err(d)
    g2 = (not ok2) and ':WellFlowRate 7 in the .rvt file names no well' in txt2
    print('  I17: members\' "wells specified" %s (want -100, -200, -300), %d "no :WellFlowRate" warnings; orphan series in member 2 stops: %s -> %s'
          % (rates, nw, g2, 'ok' if (g1 and g2) else 'FAIL'))
    res.append(('I17 EnKF members use their own extra .rvt series', g1 and g2))

    # I18: damaged soil-zone hotstart values
    d0 = case('I18_base', days=2); ok0, _ = sz_check.run(d0)
    good = ok0
    if ok0:
        sol = open(os.path.join(d0, 'out', 'solution.rvc')).read()
        a = sol.index(':GWSoilZoneColumns'); a = sol.index('\n', a) + 1; row = sol[a:sol.index('\n', a)]
        f = [x.strip() for x in row.split(',')]
        a2 = sol.index(':GWHeads'); a2 = sol.index('\n', a2) + 1; b2 = sol.index(':EndGWHeads'); hv = sol[a2:b2].split()
        for lab, t, msg in (('nan', sol.replace(row, '  ' + ', '.join(f[:2] + ['nan'] + f[3:]), 1), ':GWSoilZoneColumns: the value nan is not a finite number'),
                            ('neg', sol.replace(row, '  ' + ', '.join(f[:2] + ['-50'] + f[3:]), 1), ':GWSoilZoneColumns: the value -50 is negative'),
                            ('heads', sol[:a2] + ' '.join(['nan'] + hv[1:]) + '\n' + sol[b2:], ':GWHeads: the value nan is not a finite number'),
                            ('good', sol, None)):
            d = case('I18_' + lab, days=2); open(os.path.join(d, 'm.rvc'), 'w').write(t)
            ok, txt = run_err(d)
            g = ok if msg is None else ((not ok) and msg in txt)
            print('  I18 %-5s: %s' % (lab, ('runs' if ok else 'stops') + ('' if msg is None else (' with the message' if msg in txt else ' (message missing)'))))
            good &= g
    res.append(('I18 damaged soil-zone hotstart values stop the run', good))
    # I19: Raven transport in a coupled run stops the run; without :GroundwaterModel it runs
    good = True
    for lab, phys, constit, coupled in (('cn', False, 'Nitrate', True), ('ca', False, 'AGE', True), ('pn', True, 'Nitrate', True),
                                        ('nn', False, 'Nitrate', False)):
        d = case('I19_' + lab, days=2, physical=phys)
        tx = open(os.path.join(d, 'm.rvi')).read().replace(':EndHydrologicProcesses\n', ':EndHydrologicProcesses\n:Transport %s\n' % constit)
        if not coupled: tx = tx.replace(':GroundwaterModel MODFLOW6\n', '')
        open(os.path.join(d, 'm.rvi'), 'w').write(tx)
        ok, txt = run_err(d)
        msg = ':Transport %s cannot be used with :GroundwaterModel MODFLOW6' % constit
        g = ((not ok) and msg in txt) if coupled else (ok and msg not in txt)
        print('  I19 %s, :Transport %-7s%s: %s' % ('PHYSICAL' if phys else 'CONCEPTUAL', constit, '' if coupled else ' (no groundwater)',
                                                 ('runs' if ok else 'stops') + (' with the message' if msg in txt else '')))
        good &= g
    res.append(('I19 :Transport with :GroundwaterModel MODFLOW6 stops', good))

    # I20: head boundaries placed by their highest head in the run; a boundary left with no cells is reported
    def chd_cells(d):
        m = re.search(r'GHB cells / CHD cells : (\d+) / (\d+)', sz_check.summary(d)); return int(m.group(2)) if m else -1
    good = True
    d = case('I20_series', days=3, chd=0.0)
    open(os.path.join(d, 'm.rvt'), 'a').write('\n:BoundaryHead EDGE m\n  2000-01-01 00:00:00 1.0 3\n  99.5\n  99.5\n  99.5\n:EndBoundaryHead\n')
    ok, txt = run_err(d)
    n1 = chd_cells(d); q = 0.0
    if ok:
        import pandas as pd
        q = float(pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))['CHD [m3/d]'].abs().sum())
    g1 = ok and n1 > 0 and q > 0 and 'has no cells' not in errors(d)
    d = case('I20_low', days=3, chd=0.0)
    ok2, txt2 = run_err(d)
    n2 = chd_cells(d); e2 = errors(d)
    g2 = ok2 and n2 == 0 and 'boundary EDGE has no cells' in e2 and 'highest' in e2
    print('  I20: HEAD 0 with a :BoundaryHead series of 99.5 m: %d CHD cells, CHD flow %.0f m3 (%s); HEAD 0 alone: %d cells, warning %s'
          % (n1, q, 'ok' if g1 else 'FAIL', n2, 'present' if 'boundary EDGE has no cells' in e2 else 'MISSING'))
    res.append(('I20 head boundaries placed by their series, no-cell warning', g1 and g2))

    # I21: boundary cells switched off on steps whose head lies at or below their bottom; the same cells on a restart
    import pandas as pd
    def bnd(name, kind, layers, series, init, days=6, start=None, rvc=None):
        d = case(name, days=6, physical=False, top=3.0, rain=0.0, perc=0.0, nhru=4, init_depth=init, chd=90.0)
        p = os.path.join(d, 'm.rvg'); line = ':SpecifiedHeadBoundary EDGE edge.geojson HEAD 90'
        new = line + ' LAYERS ' + layers
        if kind == 'GHB': new = new.replace(':SpecifiedHeadBoundary', ':GeneralHeadBoundary') + ' CONDUCTANCE 1000'
        edit(p, line, new)
        if series is not None:
            open(os.path.join(d, 'm.rvt'), 'a').write('\n:BoundaryHead EDGE m\n  2000-01-01 00:00:00 1.0 %d\n' % len(series) + ''.join('  %g\n' % v for v in series) + ':EndBoundaryHead\n')
        q = os.path.join(d, 'm.rvi'); t = open(q).read()
        t = re.sub(r':Duration \d+', ':Duration %d' % days, t)
        if start: t = t.replace(':StartDate 2000-01-01', ':StartDate ' + start)
        open(q, 'w').write(t)
        if rvc: shutil.copy(rvc, os.path.join(d, 'm.rvc'))
        ok, txt = sz_check.run(d)
        return d, ok
    def cells(d):
        m = re.search(r'GHB cells / CHD cells : (\d+) / (\d+)', sz_check.summary(d)); return (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    def gwb(d): return pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))
    S = [99.0] + [90.0] * 5
    da, oka = bnd('I21_ghb_series', 'GHB', 'TOP', S, 5.0)
    ds, oks = bnd('I21_ghb_static', 'GHB', 'TOP', None, 5.0)
    d9, ok9 = bnd('I21_ghb_s90', 'GHB', 'TOP', [90.0] * 6, 5.0)
    g = oka and oks and ok9
    if g:
        q = gwb(da)['GHB [m3/d]'].values; qs = gwb(ds)['GHB [m3/d]'].values
        a, b = gwb(ds).select_dtypes('number'), gwb(d9).select_dtypes('number')
        same = len(a) == len(b) and list(a.columns) == list(b.columns) and sz_check.tc.max_diff(a, b, max(a.abs().max().max(), 1.0)) <= 1e-9
        offl = re.search(r'head boundaries off\s*:\s*(\d+)', sz_check.summary(da))
        g = bool((q[1:] <= 0.0).all()) and bool((qs <= 0.0).all()) and same and offl is not None and int(offl.group(1)) > 0
        print('  I21a: GHB series 99, 90 m against an aquifer at 95 m: GHB on days 2-6 %s m3/d (HEAD 90 alone %s); series of 90 m = HEAD 90 alone: %s; '
              'cell-steps off %s -> %s' % (', '.join('%.0f' % x for x in q[1:]), ', '.join('%.0f' % x for x in qs[1:]), same, offl.group(1) if offl else 'MISSING', 'ok' if g else 'FAIL'))
    else:
        print('  I21a: run FAILED')
    res.append(('I21a GHB below its cell: conductance 0 (drains as with HEAD 90)', g))
    db, okb = bnd('I21_chd_top', 'CHD', 'TOP', S, 2.0)
    g = okb
    if g:
        h = pd.read_csv(os.path.join(db, 'out', 'GWHRUState.csv'))['head_4 [m]'].values
        g = bool((h[1:] < 97.0).all())
        print('  I21b: CHD LAYERS TOP, series 99, 90 m: head under the outlet HRU on days 2-6 %s m (layer 1 bottom 97 m) -> %s'
              % (', '.join('%.3f' % x for x in h[1:]), 'ok' if g else 'FAIL'))
    else:
        print('  I21b: run FAILED')
    res.append(('I21b CHD below its cell: not held at the cell bottom', g))
    S2 = [99.0] * 3 + [90.0] * 3
    dc, okc = bnd('I21_rs_cont', 'CHD', 'ALL', S2, 2.0)
    d1, ok1 = bnd('I21_rs_part1', 'CHD', 'ALL', S2, 2.0, days=3)
    g = okc and ok1
    if g:
        d2, ok2 = bnd('I21_rs_part2', 'CHD', 'ALL', S2, 2.0, days=3, start='2000-01-04', rvc=os.path.join(d1, 'out', 'solution.rvc'))
        g = ok2
    if g:
        a = gwb(dc).set_index('date'); b = gwb(d2).set_index('date')
        ha = pd.read_csv(os.path.join(dc, 'out', 'GWHRUState.csv')).set_index('date'); hb = pd.read_csv(os.path.join(d2, 'out', 'GWHRUState.csv')).set_index('date')
        ix = b.index
        dq = sz_check.tc.max_diff(a.loc[ix, 'CHD [m3/d]'], b['CHD [m3/d]'], max(a['CHD [m3/d]'].abs().max(), 1.0))
        dh = sz_check.tc.max_diff(ha.loc[ix, 'head_4 [m]'], hb['head_4 [m]'])
        g = cells(dc) == cells(d2) and dq < 1e-6 and dh < 1e-6
        print('  I21c: restart on day 4: CHD cells %s against %s; CHD flow within %.2g, heads within %.2g m -> %s' % (cells(d2)[1], cells(dc)[1], dq, dh, 'ok' if g else 'FAIL'))
    else:
        print('  I21c: run FAILED')
    res.append(('I21c boundary cells the same on a restart', g))
    # I21d: a column all of whose CHD cells are switched off is an ordinary column on those steps
    import numpy as np
    sys.path.insert(0, os.path.dirname(HERE)); import combinations as C
    for phys in (False, True):
        tag = 'phys' if phys else 'conc'
        d = os.path.join(W, 'I21d_' + tag); shutil.rmtree(d, ignore_errors=True)
        sz_models.make_case(d, days=6, physical=phys, top=3.0, rain=20.0, perc=20.0, nhru=8, hru_w=100.0, init_depth=1.0, chd=90.0, phi0=(200.0, 200.0))
        edit(os.path.join(d, 'm.rvg'), 'HEAD 90', 'HEAD 90 LAYERS ALL')
        open(os.path.join(d, 'm.rvt'), 'a').write('\n:BoundaryHead EDGE m\n  2000-01-01 00:00:00 1.0 6\n' + ''.join('  %g\n' % v for v in (99, 99, 70, 70, 70, 70)) + ':EndBoundaryHead\n')
        ok, txt = sz_check.run(d); g = ok
        if g:
            bad, _ = C.check_run(d, txt); b = gwb(d)
            gcol = lambda c: b[c].values if c in b else 0.0 * b['CHD [m3/d]'].values
            onto = np.abs(gcol('recharge onto CHD cells [m3/d]')) + np.abs(gcol('soil zone to specified heads [m3/d]')) + np.abs(gcol('specified heads to soil zone [m3/d]'))
            q = b['CHD [m3/d]'].values
            if phys: sx = gcol('soil zone to aquifer [m3/d]') + gcol('aquifer to soil zone [m3/d]'); extra = bool((sx[2:] > 0.0).all())
            else: extra = bool(np.abs(b['MF6 recharge [m3/d]'].values[2:] - b['Raven recharge [m3/d]'].values[2:]).max() <= 1e-6 * b['Raven recharge [m3/d]'].abs().max())
            g = not bad and bool((np.abs(q[:2]) > 0.0).all()) and float(np.abs(q[2:]).max()) == 0.0 and float(onto[2:].max()) == 0.0 and extra
            print('  I21d %s: days 1-2 CHD %s m3/d, onto CHD cells %s; days 3-6 CHD %s, booked onto CHD cells %s m3/d; %s; check_run %s -> %s'
                  % (tag, ', '.join('%.0f' % x for x in q[:2]), ', '.join('%.0f' % x for x in onto[:2]), ', '.join('%.0f' % x for x in q[2:]),
                     ', '.join('%.0f' % x for x in onto[2:]), ('soil zone <-> aquifer on days 3-6 %s m3/d' % ', '.join('%.0f' % x for x in sx[2:])) if phys
                     else ('MF6 recharge = Raven recharge on days 3-6: %s' % extra), bad or 'ok', 'ok' if g else 'FAIL'))
        else:
            print('  I21d %s: run FAILED' % tag)
        res.append(('I21d %s: no cell held: an ordinary column' % tag, g))
    # I21e: a series that never reaches below layer 1 places the cells of layer 1 only
    for kind in ('CHD', 'GHB'):
        de, oke = bnd('I21e_' + kind.lower(), kind, 'TOP', [99.0] * 6, 2.0)
        g = oke
        if g:
            n = cells(de)[1 if kind == 'CHD' else 0]; m = re.search(r'head boundaries off\s*:\s*(\d+)', sz_check.summary(de))
            g = n == 2 and m is not None and int(m.group(1)) == 0
            print('  I21e %s: series 99 m on every day, HEAD 90: %d cells (layer 1: 2), %s cell-steps off -> %s' % (kind, n, m.group(1) if m else 'MISSING', 'ok' if g else 'FAIL'))
        else:
            print('  I21e %s: run FAILED' % kind)
        res.append(('I21e %s cells placed by the series' % kind, g))
    # I21f: the steady-state period counts in the run total of cells switched off
    S3 = [90.0, 99.0, 99.0, 90.0, 90.0, 99.0]; offs = {}
    for tag, st in (('ss', 1.0), ('nos', None)):
        dd = case('I21f_' + tag, days=6, physical=False, top=3.0, rain=0.0, perc=0.0, nhru=4, init_depth=2.0, chd=90.0, steady=st)
        edit(os.path.join(dd, 'm.rvg'), ':SpecifiedHeadBoundary EDGE edge.geojson HEAD 90', ':SpecifiedHeadBoundary EDGE edge.geojson HEAD 90 LAYERS TOP')
        open(os.path.join(dd, 'm.rvt'), 'a').write('\n:BoundaryHead EDGE m\n  2000-01-01 00:00:00 1.0 6\n' + ''.join('  %g\n' % v for v in S3) + ':EndBoundaryHead\n')
        ok, _ = sz_check.run(dd); m = re.search(r'head boundaries off\s*:\s*(\d+)', sz_check.summary(dd))
        offs[tag] = int(m.group(1)) if (ok and m) else -1
    g = offs['nos'] == 6 and offs['ss'] == offs['nos'] + 2
    print('  I21f: cell-steps off with a steady-state first period %d, without %d (the steady period at 90 m: 2 cells) -> %s' % (offs['ss'], offs['nos'], 'ok' if g else 'FAIL'))
    res.append(('I21f steady-state period in the cell-steps off', g))
    # I22: :InitialGWHeads and :GWHeads values read strictly
    good = True
    for val, want in (('98,5', "has the surplus value '5'"), ('H98.5', "'H98.5' is not a number"), ('0x62', "'0x62' is not a number"),
                      ('98.5', None), ('98.5# note', None), ('98.5 # note', None)):
        d = case('I22_' + re.sub(r'\W', '_', val), days=2, physical=False, init_depth=2.0)
        open(os.path.join(d, 'm.rvc'), 'a').write('\n:InitialGWHeads ELEVATION %s\n' % val)
        ok, txt = run_err(d)
        if want:
            g = (not ok) and want in txt and ':InitialGWHeads' in [l for l in txt.split('\n') if want in l][0] if want in txt else False
            print('  I22 :InitialGWHeads ELEVATION %s: %s -> %s' % (val, 'stops: ' + [l for l in txt.split('\n') if want in l][0].strip()[:140] if want in txt else ('runs' if ok else 'stops without the message'), 'ok' if g else 'FAIL'))
        else:
            h = None
            if ok:
                ic = open(os.path.join(d, 'out', 'mf6', 'gwf.ic')).read().split('INTERNAL FACTOR 1.0')[1].split('END')[0]
                h = max(float(x) for x in ic.split())   # (the active cells' starting head; inactive cells 0)
            g = ok and h is not None and abs(h - 98.5) < 1e-9
            print('  I22 :InitialGWHeads ELEVATION %s: %s, starting head %s m -> %s' % (val, 'runs' if ok else 'FAILED', h, 'ok' if g else 'FAIL'))
        good &= g
    d = case('I22_from_profile_0', days=2, physical=False, init_depth=2.0)
    open(os.path.join(d, 'm.rvc'), 'a').write('\n:InitialGWHeads FROM_PROFILE 0\n')
    ok, txt = run_err(d); want = "has the surplus value '0' (FROM_PROFILE takes no value)"; g = (not ok) and want in txt
    print('  I22 :InitialGWHeads FROM_PROFILE 0: %s -> %s' % ('stops: FROM_PROFILE takes no value' if g else ('runs' if ok else 'stops without the message'), 'ok' if g else 'FAIL'))
    good &= g
    d = case('I22_gwheads', days=2, physical=False, init_depth=2.0)
    ok0, _ = sz_check.run(d); g = ok0
    if g:
        rvc = open(os.path.join(d, 'out', 'solution.rvc')).read()
        i = rvc.index(':GWHeads'); j = rvc.index('\n', i) + 1; k = rvc.index('\n', j)
        w = rvc[j:k].split(); i0 = [n for n, x in enumerate(w) if float(x) != 0.0][0]; w[i0] = w[i0] + 'x'; rvc = rvc[:j] + '  ' + ' '.join(w) + rvc[k:]
        open(os.path.join(d, 'm.rvc'), 'w').write(rvc)
        ok, txt = run_err(d); g = (not ok) and ':GWHeads: the value %s is not a finite number' % w[i0] in txt
        print('  I22 :GWHeads value %s: %s -> %s' % (w[i0], 'stops with the message' if g else ('runs' if ok else 'stops without the message'), 'ok' if g else 'FAIL'))
    good &= g
    res.append(('I22 strict numbers in the .rvc', good))
    for n, g in res:
        print('  %-50s %s' % (n, 'ok' if g else 'FAILED'))
    good = all(g for _, g in res)
    print('input tests: %s' % ('ALL PASSED' if good else 'FAILED'))
    return good

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
