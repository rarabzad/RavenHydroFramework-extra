# Manual notation (Phase 0 clean-up)

Documentation-only clean-up of `docs/manual/chapters/*.tex` so that every symbol has one meaning and the symbols
shared with Raven follow the Raven User's Manual (v4.1). No equation's mathematics or any result changed.
Item codes (A1-C5) are those of the Phase 0 list in the soil-zone design plan (section 2).

## Index conventions

| Index | Meaning |
|---|---|
| $k$ ($k'$) | HRU |
| $i$ (neighbour $j$) | grid cell / column |
| $p$ | subbasin |
| $m$ | Raven soil layer (`SOIL[m]`), reserved |
| $\ell$ ($\ell'$) | MODFLOW layer |
| $a$ | aquifer profile |
| $\beta$ | boundary (summation index in the flow equation) |
| $v$ | polygon corner |
| $n$ | time step, always a superscript |

## Mapping applied

| Item | Old | New | Where |
|---|---|---|---|
| A1 | $h_{loc}$ | $h_{gw}$ (Raven's $S(h)=k(h-h_{gw})$) | ch4_exchanges (reservoirs: text, 2 equations, parameter table), appendix (algorithms table, commands table) |
| A2 | $R_k$ | $r_k$ (recharge depth, mm) | ch4_existing (overlap formula) |
| A3 | $A_{ki}$, $A_{kj}$ | $A_{k,i}$, $A_{k,j}$ | ch4_existing |
| A4 | -- | sentence: `SOIL_ZONE_DEPTH` is ignored under `:SoilZone PHYSICAL` for HRUs with a soil zone (thickness = sum of the listed soil layers) | ch3_building (model top), appendix (profile table) |
| A5 | -- | sentence: `SEEPAGE_LEAKANCE` is not used for soil-zone HRUs (exchange through the soil-zone conductance) | ch4_exchanges (seepage), appendix (profile table) |
| A6/B5 | $V^{applied}_{p,n}$, $G_{p,n}$, $K_{p,n}$ | $V^{applied,n}_p$, $G^n_p$, $V^{carry,n}_p$ | ch4_exchanges (river loss carried) |
| B1 | reservoir $k$ | $k_{seep}$ (HRU index stays $k$) | ch4_exchanges (text, equation, example, listing comment, table), appendix (commands, notation) |
| B2 | flow equation cell $n$, neighbour $m$ ($C_{nm}$, $h_n$, $h_m$) | $i$, $j$ ($C_{ij}$, $h_i$, $h_j$) | ch2_concepts (flow equation, head-dependent boundaries) |
| B2 | polygon corner count $n$, corner index $j$ | $N_v$, $v$ | ch3_building (shoelace formula) |
| B3 | $\sum_m A_{m,i}$ | $\sum_{k'}A_{k',i}$ | ch4_exchanges (seepage back to Raven) |
| B3 | $\sum_m T_m$ | $\sum_{\ell'}T_{\ell'}$ | ch4_exchanges (well split) |
| B4 | leakances $L$, $L_s$ | $\Lambda$, $\Lambda_s$ (river lengths keep $L_p$, $L_{p,i}$; Darcy distance $L$ in ch2 unchanged) | ch2 (units table), ch4_exchanges (seepage, stores), appendix |
| B6 | delay store $S_k$ ($S_k^*$, $S_k^n$) | $V^{dl}_k$ ($V^{dl,*}_k$, $V^{dl,n}_k$); $\Delta S^{delay}\to\Delta V^{dl}$ | ch4_exchanges, ch5_accounting, ch8_verification |
| B6 | storage capacity $S_n$ | $\mathcal{S}_i$ [m^2] | ch2_concepts |
| B7 | store depth $s_k$ [m] | $\phi^{st}_k$ [mm] (equations divide by 1000) | ch4_exchanges (stores), appendix |
| B7 | grid snapping $s_b$ | $\delta_b$ | ch3_building (HRU mesh seeds) |
| B8 | profile index $p$: $d_{sz,p}$, $D_p$, $p(k)$, $p(i)$ | $d_{sz,a}$, $D_a$, $a(k)$, $a(i)$ | ch3_building |
| B9 | duration $T$ in $N=\mathrm{round}(T/\Delta t)$ | $t_{end}$ ($T$ stays transmissivity) | ch3_building |
| B10 | projection $\phi,\lambda$ ($\phi_0,\lambda_0$) | $\mathrm{lat},\mathrm{lon}$ ($\mathrm{lat}_0,\mathrm{lon}_0$) | ch3_building |
| B11 | boundary index $b$ in $\sum_b q_{b,n}$ | $\beta$: $\sum_\beta q_{\beta,i}$ ($q_b$, $C_b$, $h_b$ of a single boundary keep $b$ as a label) | ch2_concepts |
| B12 | Earth radius $R$ | $R_\oplus$ | ch3_building (projection) |
| B12 | recharge rate $R_i$ | $r_i$ [m/d] | ch4_exchanges |
| C1 | $\Delta^2$ meaning cell area | $\lvert\Omega_i\rvert$: recharge rate, seepage $C=\Lambda_s\lvert\Omega_i\rvert$, ET ($E_i$, $Q^{evt}_i$), activation $f_{min}\lvert\Omega_i\rvert$, appendix algorithms. Cell area $A_i$ in ch3 also $\to\lvert\Omega_i\rvert$. $\Delta^2$ kept only where it is the regular-grid cell count estimate (ch3 "Choosing the cell size") | ch3, ch4_exchanges, appendix |
| C2 | $A_k$ said to be in m^2 | $A_k$ in km^2, $10^6A_k$ in m^2 equations ($V_k$, $V^{ret}_k\to$ mm, store volumes, ch4_existing overlap formula, appendix) | ch4_exchanges, ch4_existing, appendix |
| C3 | $Q^{out}_p$ "in m^3/d" | $Q^{out}_p$ [m^3/s] with $86\,400$ shown in the river conductance limit | ch4_exchanges |
| C5 | (note only) | Raven manual gives the reservoir seepage constant in "[m^3/d]", the code (`Reservoir.cpp`, ~l.1640) uses m^3/s per m; the manual keeps m^3/s/m. To report to James Craig. | -- |

Additional renames needed for one meaning per symbol (consequences of the items above):

| Old | New | Why |
|---|---|---|
| projection scale factor $k'$ | $\kappa$ | $k'$ is now a second HRU index (B3) |
| covered area $a_i$ | $A^{cov}_i$ | $a$ is now the profile index (B8); ch3 activation rule and ch5 steady-state start |
| mean store depth $\bar s_i$ | $\bar d^{\,st}_i$ [m] | $s$ is the river stage |
| store volumes $V_{k,i}$, $V_i$ | $V^{st}_{k,i}$, $V^{st}_i$ | $V_k$ is the recharge volume |
| $C=K_bWL/M_b$ (appendix) | $C=K_bW_pL_{p,i}/M_b$ | same symbols as ch4 |
| recharge refcard row $\Delta$ | row $\lvert\Omega_i\rvert$ (cell area, $\Delta^2$ on a regular grid) | the recharge equations no longer use $\Delta$ |

The appendix notation table (A.14) was rewritten with an index line and every symbol above.

## Left as they are

- Command-syntax placeholders inside `\cmd{}` (e.g. `:SurfaceWaterExchange SV group LEAKANCE L`, `STEADY_STATE r`):
  they are typed text, not symbols.
- Local symbols of single formulas: row/column $r$, $c$ of the regular-grid corner formula and $\rho$, $c$ of the
  inverse projection (ch3); Thiem radius $r$ (ch8); Darcy $L$, $L_1$, $L_2$ (ch2).
- Figures: the only image figure with symbols, `fig_curves.png`, shows $\tau$, $d_s$, $d_x$, $h$, none of which
  changed. No figure script (`make_*.py`) or TikZ figure contains a renamed symbol.
- The user guide (`Raven_MF6_Groundwater_UserGuide.md`) has none of the renamed symbols (only the command
  placeholder `LEAKANCE L`).

## Checks

- Sweep (grep) for every old symbol over the chapters and tables: none left except the cases listed above.
- Build: pdflatex, bibtex, pdflatex x2: 0 errors, 0 undefined references or citations, 0 overfull boxes (13
  underfull boxes, the same as before the clean-up), 109 pages. Changed pages (flow equation, projection, recharge,
  rivers, stores, notation table) rendered and checked.
