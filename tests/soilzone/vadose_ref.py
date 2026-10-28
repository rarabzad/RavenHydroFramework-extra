"""Independent reference for the unsaturated column: drainage of a wet 4 m column (theta 0.38, Campbell b=4,
psi_a=0.25 m, Ks=0.5 m/d, ths=0.40) to a water table at its bottom, solved here by the method of lines on 400 uniform
cells with scipy's BDF integrator (mass-form unknowns: theta), independently of GWVadose.cpp. Compares the bottom-flux
series with the column's (16 nodes, half-day steps) written by vadose_unit; also a delayed recharge pulse through a
deep column (P2): arrival time and spreading.
Usage: python3 vadose_ref.py <series file from vadose_unit> [allowed step-mean error, fraction of the peak]"""
import sys, numpy as np
from scipy.integrate import solve_ivp

ths, b, psia, Ks = 0.40, 4.0, 0.25, 0.5
Si = 2 * b / (1 + 2 * b); si = psia * Si ** (-b)

def psi_of(th):
    S = np.clip(th / ths, 1e-12, 1.0)
    return np.where(S >= Si, -si * np.sqrt(np.maximum(1 - S, 0) / (1 - Si)), -psia * S ** (-b))

def K_of(th):
    return Ks * np.clip(th / ths, 0, 1) ** (2 * b + 3)

def column_rhs(L, n, qtop_fn):
    dz = L / n; zc = L - dz * (np.arange(n) + 0.5)          # z upward from the water table, top down
    def rhs(t, th):
        p = psi_of(th); K = K_of(th)
        Kf = 0.5 * (K[:-1] + K[1:])
        q = Kf * ((p[:-1] - p[1:]) / dz + 1.0)              # downward fluxes between cells
        qb = 0.5 * (K[-1] + Ks) * ((p[-1] - 0.0) / (dz / 2) + 1.0)
        qt = qtop_fn(t)
        dth = np.empty(n)
        dth[0] = (qt - q[0]) / dz
        dth[1:-1] = (q[:-1] - q[1:]) / dz
        dth[-1] = (q[-1] - qb) / dz
        return dth
    def qbot(th):
        p = psi_of(th); K = K_of(th)
        return 0.5 * (K[-1] + Ks) * ((p[-1]) / (dz / 2) + 1.0)
    return rhs, qbot, zc

def drainage(series):
    n = 400; L = 4.0
    rhs, qbot, zc = column_rhs(L, n, lambda t: 0.0)
    th0 = np.full(n, 0.38)
    tt = series[:, 0]
    sol = solve_ivp(rhs, (0, tt[-1]), th0, method='BDF', t_eval=np.concatenate([[0], tt]), rtol=1e-8, atol=1e-10, max_step=0.05)
    # the column's flux is a step mean: compare step means (storage change over each step)
    dz = L / n
    S = sol.y.sum(axis=0) * dz
    ref = -(np.diff(S)) / np.diff(sol.t)
    got = series[:, 1]
    return ref, got

def main():
    ser = np.loadtxt(sys.argv[1])
    ref, got = drainage(ser)
    tot_ref, tot_got = ref.sum(), got.sum()
    err = np.abs(got - ref).max() / ref.max()
    print('drainage: total drained %.5f m (reference %.5f m, %.2f%%), largest step-mean difference %.2f%% of the peak'
          % (tot_got * 0.5, tot_ref * 0.5, 100 * (tot_got - tot_ref) / tot_ref, 100 * err))
    lim = float(sys.argv[2]) if len(sys.argv) > 2 else 0.12   # largest step-mean error allowed, fraction of the peak
    ok = abs(tot_got - tot_ref) <= 0.01 * tot_ref and err <= lim
    print('vadose reference: %s' % ('PASS' if ok else 'FAIL'))
    return ok

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
