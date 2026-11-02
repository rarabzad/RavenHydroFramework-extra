"""fig_rough_cases.png: three cases of the rough-terrain suite (:SoilZoneVadose NONE): DEM, grid and HRUs; a section with
land, soil-zone base, layer bottoms and water tables; the saturated fraction of every HRU over the run.

usage: RAVEN_EXE=... RAVEN_MF6_LIB=... RAVEN_TEST_WORK=... python3 make_rough_figure.py [seed seed seed]"""
import os, sys, json, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'tests', 'soilzone'))
import numpy as np, pandas as pd, flopy
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import rough_models as rm, sz_check
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#6250d6']; INK2 = '#52514e'

def case(seed):
    S = rm.gen_spec(seed, 'gen'); d = sz_check.tc.work('soilzone', 'rough_fig', 'g%d' % seed); shutil.rmtree(d, ignore_errors=True)
    meta = rm.build(d, S, 'NONE'); ok, txt = sz_check.run(d)
    if not ok: raise SystemExit('g%d did not run: %s' % (seed, txt[-300:]))
    return S, meta, d

def main():
    seeds = [int(x) for x in sys.argv[1:4]] or [5, 17, 26]
    fig, ax = plt.subplots(3, 3, figsize=(11, 9.5), gridspec_kw=dict(width_ratios=[1, 1.4, 1]))
    for r, seed in enumerate(seeds):
        S, meta, d = case(seed); o = os.path.join(d, 'out')
        g = flopy.mf6.utils.MfGrdFile(os.path.join(o, 'mf6', 'gwf.dis.grb')); mg = g.modelgrid
        G = rm.geometry(d, S, meta, grid=(mg.xoffset, mg.yoffset, mg.nrow, mg.ncol))
        x0, x1, y0, y1 = S['domain']; cs = S['cell']
        X, Y = np.meshgrid(np.linspace(x0, x1, 200), np.linspace(y0, y1, 150)); Z = rm.field(S['land'], X, Y)
        a = ax[r, 0]; a.imshow(Z, origin='lower', extent=(x0, x1, y0, y1), cmap='Greys_r', aspect='equal')
        for ic in range(G['ncpl']):
            a.add_patch(plt.Rectangle((G['cx'][ic] - cs / 2, G['cy'][ic] - cs / 2), cs, cs, fill=False, lw=0.4, ec='#aaaaaa' if G['prof'][ic] >= 0 else '#dddddd'))
        for p in meta['polys']:
            p = np.array(p); a.plot(p[:, 0], p[:, 1], color=C[1], lw=1.2)
        ys = 0.5 * (y0 + y1); a.plot([x0, x1], [ys, ys], '--', color=C[0], lw=1)
        a.set_title('g%d: slope %.0f %%, relief %.1f m, D %.1f m' % (seed, 100 * S['slope'], S['relief'], max(meta['Dk'])), fontsize=8); a.tick_params(labelsize=7)
        # section along the dashed line
        a = ax[r, 1]; xs = np.linspace(x0, x1, 400); a.plot(xs, rm.field(S['land'], xs, ys + 0 * xs), color=INK2, lw=1, label='land')
        row = int((mg.yoffset + mg.nrow * cs - ys) // cs); cols = range(mg.ncol)
        nl = G['nlay']; hf = flopy.utils.HeadFile(os.path.join(o, 'mf6', 'gwf.hds')); times = hf.get_times()
        rain = np.array(S['rain'][:len(times)]); tend = int(np.nonzero(rain)[0][-1]) + 1 if rain.any() else len(times) // 2
        for c in cols:
            ic = row * mg.ncol + c
            if G['prof'][ic] < 0: continue
            xa, xb = mg.xoffset + c * cs, mg.xoffset + (c + 1) * cs
            a.plot([xa, xb], [G['top'][ic]] * 2, color=C[1], lw=1.2)
            for l in range(nl):
                a.plot([xa, xb], [G['botm'][l, ic]] * 2, color='#999999', lw=0.6, ls='-' if G['idomain'][l, ic] > 0 else ':')
            for t, col in ((times[0], C[4]), (times[min(tend, len(times)) - 1], C[0]), (times[-1], C[2])):
                h = hf.get_data(totim=t).reshape(nl, -1)[:, ic]; idm = G['idomain'][:, ic]; hv = h[idm > 0]
                if len(hv): a.plot([xa, xb], [hv.max()] * 2, color=col, lw=1.5)
        a.set_title('section: soil-zone base (orange), layer bottoms (grey), water table day 1 / %d / %d' % (tend, len(times)), fontsize=8); a.tick_params(labelsize=7)
        s = pd.read_csv(os.path.join(o, 'GWSoilExchange.csv')); a = ax[r, 2]
        for k, (hid, q) in enumerate(s.groupby('HRU_ID')):
            a.plot(q['time [d]'], q['saturated fraction [-]'], color=C[k % 5], lw=1)
        a.bar(np.arange(1, len(rain) + 1), rain / max(rain.max(), 1.0), color='#cfd8e6', width=1.0, zorder=0)
        a.set_ylim(0, 1.02); a.set_title('saturated fraction of each HRU (bars: rain, scaled)', fontsize=8); a.tick_params(labelsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig_rough_cases.png'), dpi=150)
    print('wrote fig_rough_cases.png')

if __name__ == '__main__':
    main()
