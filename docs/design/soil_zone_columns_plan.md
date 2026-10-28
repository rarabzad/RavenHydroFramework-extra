# Soil zone v2: the unsaturated zone, capillary rise, timing, column classes, specified heads, existing models

This note extends `soil_zone_coupling_plan.md` (v1, as built). It covers the seven gaps left in v1. Notation follows
v1. Lengths are in m, times in d, water contents are volumetric [-], and pressure heads ψ are in m (negative when
unsaturated). Raven's soil water φ is in mm.

## 0. Goals and budget

| Gap in v1 | v2 |
|---|---|
| no delay or storage between the soil-zone base and a deep water table | a per-column 1-D unsaturated column (Richards' equation) between the soil-zone base and the water table |
| no capillary rise from the water table | capillary rise into the soil zone from the unsaturated column; analytic steady rise when the water table is in or just below the soil zone |
| buckets only, no perched water | the unsaturated column carries a moisture profile; a low-conductivity layer holds a perched saturated zone |
| Raven's processes run before the exchange (first-order splitting) | the exchange of the previous step is applied as a source inside Raven's step, and only the change is applied after it |
| Raven's processes act on the HRU's mean soil water | Raven's processes run per column class: up to K classes per HRU, grouped by wetness |
| no exchange over specified-head cells | columns over specified-head cells exchange with the specified head (booked against the specified head) |
| not available with `:MF6Simulation` | the soil-zone packages are added to an existing model; the soil-zone base is the model top |

**Cost budget.** The 365-day Liard PHYSICAL run must stay within 1.5× its v1 time (271 s), with all features on. The
time is found partly by speeding up v1's local solve (bisection, about 50 iterations, becomes safeguarded Newton,
about 5 iterations). Every new feature is optional, and the defaults keep v1's results unless the feature is asked
for. `:SoilZone PHYSICAL` with no new options must stay byte-identical to v1 (regression tests).

## 1. The unsaturated column below the soil zone (`:SoilZoneVadose RICHARDS`)

### 1.1 Domain

Each soil-zone column (one per link) gets an unsaturated column from the soil-zone base $z_b$ (the link's mean
sample base) down to the water table $h$ (the top active cell's head). Its length is $L=z_b-h$. The column exists
when $L>L_{\min}$ (default $d_s$, the smoothing depth). Below that, the v1 contact law and the saturated fraction
handle the exchange as before, and the column hands its water to the aquifer.

Properties come from the MODFLOW layer each node lies in, through that layer's aquifer class:
- $\theta_s$: `POROSITY`;
- $b$: `CLAPP_B`, default 4;
- $\psi_a$: `AIR_ENTRY_PRESSURE` [m], default 0.3;
- $K_s$: `K_VERT`.

A low-$K$ layer under a higher-$K$ layer therefore holds a perched saturated zone ($\psi>0$ above the interface)
without anything special.

### 1.2 Equations

Mixed-form Richards' equation, with $z$ upward:
$$\frac{\partial\theta(\psi)}{\partial t}=\frac{\partial}{\partial z}\Big[K(\psi)\Big(\frac{\partial\psi}{\partial z}+1\Big)\Big].$$
It uses the Campbell retention curve with the Hutson–Cass parabola near saturation, so that it is smooth at $\psi_a$:
$$\theta(\psi)=\begin{cases}\theta_s\,(\psi/\psi_a')^{-1/b} & \psi\le\psi_i\\ \theta_s\big[1-\frac{(1-S_i)\psi^2}{\psi_i^2}\big] & \psi_i<\psi\le0\\ \theta_s+S_s\psi & \psi>0\end{cases}\qquad
K=K_s\,(\theta/\theta_s)^{2b+3}.$$
Here $\psi_a'=-\psi_a$, $S_i=2b/(1+2b)$ and $\psi_i=\psi_a'S_i^{-b}$ (Hutson and Cass 1987). Interface conductances use
the arithmetic mean of the two nodes, upstream-weighted when the lower node is drier, which is more robust for
infiltration fronts.

**Boundary conditions:**
- **Top, at $z_b$:** flux $q_{top}=P-R_c$. $P$ is the column's share of Raven's recharge (the percolation out of
  $\mathrm{SOIL}[M-1]$ that v1 sent straight to MODFLOW). $R_c$ is the capillary rise into the soil zone (§2). If the
  top node saturates and cannot take $P$, the excess goes back to the soil column, as rejected recharge.
- **Bottom, at $h$:** $\psi=0$ (the water table). The bottom flux $q_{bot}$ is the column's recharge to the aquifer.
  It is computed as $q_{top}-\Delta S/\Delta t$, so the column conserves mass to round-off.

### 1.3 Numerics

- **Grid:** $N$ cell-centred finite volumes (default 16) on a grid that is geometric from both ends (ratio 1.3).
  Nodes are fine at the soil-zone base, where infiltration enters, and at the water table, where the fringe is.
- **Solver:** implicit Euler. Newton with the analytic $d\theta/d\psi$ and $dK/d\psi$ terms, and a tridiagonal
  solve (Thomas).
- **Adaptive sub-steps:** at most 8 Newton iterations; the sub-step is halved on failure or when
  $\max|\Delta\theta|>0.05$, and grown ×1.5 after easy steps. The first sub-step is the step left.
- **Fast path:** a column at hydrostatic equilibrium with $q_{top}=0$ is skipped.
- **Water-table moves between steps:** the grid is rebuilt on the new length. Water is remapped conservatively by
  overlap integrals of $\theta$.
  - Water below the new water table (a rising table) is handed to the aquifer as recharge at the start of the next
    step (one-step lag; see §1.4).
  - A falling table opens new cells at $\theta=\theta_s-S_y$: MODFLOW released $S_y$ there, and the rest drains
    later as delayed yield.
- **Coupling to the interface iteration:** the column is solved once per Raven step. It uses the water table at the
  start of the step and Raven's percolation of that step, before the MODFLOW solve, and gives MODFLOW its recharge
  $q_{bot}$. It is not re-solved within MODFLOW's iterations (its dynamics are slower than a step), which keeps the
  cost at one column solve per step.
- **Expected cost:** about $10^7$–$10^8$ flops per step for 4300 Liard columns.

### 1.4 Mass bookkeeping

Each column stores $S_v=\sum\theta_i\Delta z_i$, reported per HRU and in total in `GWBudget.csv` as *unsaturated
zone storage [m3]*.

Per step: Raven's recharge plus the water absorbed last step equals the column inflow plus direct recharge. The
column outflow $q_{bot}$ goes to MODFLOW RCH. The column storage change equals inflow minus outflow minus capillary
rise.

Each column's state ($N$, the lengths and $\theta_i$) is written to the hotstart as `:GWVadoseColumns`.

### 1.5 Consistency with MODFLOW's storage

MODFLOW treats the pore space above the water table as drained, holding $S_y$ less than saturation. The column's
water lives in that pore space, so the two never count the same water.

When the water table rises into wet soil, MODFLOW's $S_y$ needs $S_y\Delta h$ of water, while the soil actually
lacks $(\theta_s-\theta)\Delta h$. The absorbed water $\theta\Delta h$ is handed to MODFLOW the next step as
recharge, so mass is exact, and head dynamics are right when $S_y\approx\theta_s-\theta_{fc}$. A warning is written
when an aquifer class's $S_y$ and its Campbell drainable porosity at $\psi=-1$ m differ by more than a factor 2.

## 2. Capillary rise into the soil zone

**From the unsaturated column (water table below the soil zone).** The upward part of the Darcy flux between the
bottom soil layer and the top node of the column is
$$R_c=\max\Big(0,\;-\bar K\Big(\frac{\psi_{soil}-\psi_1}{\Delta z}+1\Big)\Big),$$
with $\psi_{soil}$ from the soil's Campbell curve. It uses Raven's `AIR_ENTRY_PRESSURE` [mm] and `CLAPP_B` (both
always set by Raven's auto-calculation), at the layer's saturation $\phi/\phi_{\max}$. $\bar K$ is the geometric
mean of the two conductances. $R_c$ is limited by the soil layer's room and by the top node's water above residual.
The downward part is not used, because Raven's percolation process already moves water down; this avoids counting
percolation twice.

**From a water table in or just below the soil zone (no column, or $L<L_{\min}$).** The steady upward flux from a
water table at depth $d$ below the drying layer's mid-depth (Gardner 1958, in Campbell form, Eagleson 1978) is
$$R_c=K_s\,\Big(1+\frac{1.5}{m-1}\Big)\Big(\frac{\psi_a}{d}\Big)^{m},\qquad m=2+3/b,$$
limited by the layer's deficit below field capacity over the step. It is part of the column's exchange $q$ in the
local solve. $q$ remains monotone in the column water: $R_c$ falls as the layer wets, so the local balance keeps a
unique root, and the bisection or Newton guard still applies. The Robin slope $C_g$ gains $\partial R_c/\partial h$.

Capillary rise is on with `:SoilZoneCapillaryRise ON` (default ON when `:SoilZoneVadose RICHARDS` is set, otherwise
OFF, which keeps v1's results).

## 3. Timing: exchange inside Raven's step (`:SoilZoneExchangeTiming LAGGED`)

v1 runs Raven's vertical processes, then the exchange; ET and percolation do not see the water that rises in during
the step. v2 applies each column's exchange of the previous step, $q^{n-1}$, as a source at the start of the step,
before Raven's processes.
- **Before the processes:** the soil-zone layers receive the source $-q^{n-1}\Delta t$, placed by the column's
  `Fill`/`Apply` rules.
- **After them:** the exchange applies only the correction $-(q^n-q^{n-1})\Delta t$.

The splitting error then scales with the change of the exchange between steps instead of with the exchange itself.
Mass is conserved exactly: the source and the correction add up to MODFLOW's booked flow. A lagged source larger
than the column holds is clipped, and the remainder goes into the correction.

The hillslope test (v1: daily mean error 1.5 cm) measures the gain. The default stays `AFTER` (v1) until the tests
show `LAGGED` is never worse.

## 4. Raven's processes per column class (`:SoilZoneClasses K`)

Each soil-zone HRU's columns are grouped at the start of every step into up to $K$ classes, by quantiles of the
columns' soil-zone wetness (saturated thickness λ, then total water), weighted by area. Each class $c$ has area weight
$w_c$ and the area-weighted mean soil water $\bar\phi_c$ of its columns.

In Raven's ORDERED_SERIES loop, for an HRU with $K>1$:
- Each class runs the HRU's process sequence on a copy of the HRU state, with the soil-zone layers set to
  $\bar\phi_c$ (and the lagged source of §3 added).
- The HRU's other states become the weighted mean of the class results.
- Balances are incremented with weights $w_c$.
- Each class's soil-zone result is handed to its columns through v1's `Distribute` rules, class by class instead of
  for the whole HRU.

Cost: K process evaluations per soil-zone HRU per step, which is small next to MODFLOW. Default $K=1$ (v1).

Three Raven processes read the HRU's stored, start-of-step state rather than the state vector: INF_HBV's
saturation check, potential melt and sublimation. They see the HRU mean, as they would in v1.

Other solver methods (EULER, ITERATED_HEUN) run with $K=1$ and a warning.

## 5. Columns over specified-head cells

Links on cells whose top active layer is a specified head get soil-zone columns too.
- Their exchange uses the v1 local solve with $h$ fixed at the specified head, which is exact; no MODFLOW boundary
  is needed.
- The flow is booked against the specified head and reported as *soil zone to/from specified heads [m3/d]*.
- Their recharge goes to the specified head as before (*recharge onto CHD cells*). On saturated ground it is
  rejected back to the column.
- The rest column now covers only the parts of the HRU outside the grid, where there is no aquifer and no exchange
  (documented).

## 6. Existing MODFLOW models (`:MF6Simulation` with `:SoilZone PHYSICAL`)

- **Packages:** SZX/SZQ/SZD are written as `raven.szx`, `raven.szq`, `raven.szd` and inserted into the model's name
  file like `raven.rch`.
- **Soil-zone base:** the model top. The land surface is the top plus D.
- **Sub-grid relief:** comes from the DEM (`:LandSurface`), relative to each cell's mean, when one is given.
  Otherwise each link has a single sample at the top.
- **Units:** heads are converted from model units with `_hf`, conductances and rates with `_extLf²/_extTf` and
  `_qf`.
- **Classes:** where an external profile has no layers, the conductance and unsaturated properties come from the
  class named in the profile's first entry, or from `:SoilZoneAquiferClass` when no class is given.

## 7. Speed work on v1

- `gwsz::LocalSolve`: safeguarded Newton–bisection on ΔV (bracket kept, Newton steps from the analytic slope),
  with a relative tolerance of 1e-12. This replaces about 50 bisections with about 5 iterations.
- Sample loops: break on sorted bases. `SubgridLevel` is computed incrementally.
- Snapshot copies in `SZIterate`: swap buffers instead of copying nine vectors.
- A profile timer (`RAVEN_GW_PROFILE`) per phase: MODFLOW solve, local solves, column solves, booking.

## 8. Tests

- **V1 vadose unit:** a steady infiltration profile against the analytic Campbell steady-state solution; drainage
  of a column to a water table against a fine-grid reference (N=400); mass to 1e-12; perched water over a low-K
  layer.
- **V2 delay:** the recharge pulse arrives later and spread out, compared with a reference solved independently
  with a fine-grid implicit solver in Python. A deeper water table gives a later arrival.
- **V3 rising and falling water table** through a wet column: mass exact; the head matches a fine reference within
  2%.
- **C1 capillary rise:** a dry soil above a shallow water table gains water at the analytic Gardner rate; none when
  the water table is deep.
- **T1 timing:** the hillslope error at a daily step against the hourly reference, `AFTER` vs `LAGGED`.
- **K1 classes:** one HRU against ten HRUs with ET from saturated soil (v1: 20%), K=1,3,6.
- **S1 specified heads:** a column over a specified head fills to it and drains when it falls.
- **E1 existing model:** the T2 hillslope as an existing MODFLOW model against the generated one.
- **Regime matrix** (water-table position: deep, in the unsaturated column, at the soil base, in each soil layer, at
  the surface, rising, falling): every identity, mass, and against references.
- **Regression:** v1 byte-identical with the new options off; CONCEPTUAL byte-identical; full suite; Liard time.

## 9. As built (changes to the plan above)

- **Capillary rise (§2).** The Gardner/Eagleson approximation was replaced by the exact steady relation
  `dz = ∫ dψ / (1 + q/K(ψ))` between two suctions (`gwvz::RiseBetween`; tabulated per Clapp–Hornberger b, root by
  Brent; within 2 % of the direct solution, suctions within e² integrated directly). The approximation overestimates
  the rise by up to 70 % at moderate dryness. From the water table the rise goes into every soil-zone layer below field
  capacity whose middle is above the water table (not only the lowest), capped by the largest rise to the lowest such
  layer; it is taken from the aquifer as a fixed rate through SZQ_RAVEN and added to the layers in SZApply (after the
  columns' sync, which would otherwise undo it). The rise from an unsaturated column uses the same relation between
  the column's top node and the bottom layer.
- **Timing (§3).** LAGGED is the default. The lagged source is taken back out of the columns at the sync (the local
  solves and SZApply then work as in v1); what the processes used of it beyond the step's exchange is a *debt* the
  aquifer repays through SZQ_RAVEN in the following steps (`lagged-exchange debt/repayment`; `:GWSoilZoneLag` holds the
  last exchange and the open debt). Without the debt the lent water is created when the step's exchange is smaller
  (robustness R7: 144 m³). With it every robustness test passes with LAGGED, and the v1 suite errors fall (T4 largest
  head difference 7.3 → 3.3 cm; hillslope mean 1.8 → 0.7 cm).
- **Classes (§4).** As planned; `CModel::AddToBalance` adds the weighted flows of the later classes. A class target
  that lateral processes would make negative falls back to the HRU-wide sync.
- **Specified heads (§5).** The columns are solved after MODFLOW's solve: the specified head is in MODFLOW's heads only
  from its first iteration on, so a predictor solve sees the initial head in step 1. With an existing model the
  specified-head cells follow IBOUND step by step; exchange columns on such cells are solved the same way, have no
  MODFLOW boundary, take no lagged source and send their recharge to the head.
- **Existing models (§6).** The soil-zone code now works in metres and m³/d throughout and converts only at MODFLOW's
  arrays (heads /`_hf`, conductances ·`_hf/_qf`, rates /`_qf`). Conductance and Sy come from the model's NPF K33 (else
  K) and STO SY, read in the probe; `:SoilZoneAquiferClass` supplies b, ψa and θs for the unsaturated columns. The DEM
  gives the relief within cells about their mean; `:LandSurface` is accepted with an existing model only together with
  the soil zone.
- **Brent in the local solve (§7).** Soil-zone runs agree with v1 within the interface tolerances, not byte for byte.
  CONCEPTUAL runs and models without groundwater are unchanged byte for byte (Liard CONCEPTUAL and existing-model
  examples, Raven benchmark set).
- **Found on the way.** The reservoir stage check ran before Raven sets the reservoirs' initial stages, so every
  coupled reservoir was refused (lake, behaviour, budget_xcheck, edge N30). It now checks the dry stage at start-up and
  the stage in the first step.
- **Storage reference of the unsaturated columns (§1.4–1.5), audit round 1.** Opening cells at θs − Sy when the
  water table falls left a dry band beside the water table that refilled from the aquifer in the next step; with Sy
  larger than the drainable porosity the retention curve implies near the water table, this explicit feedback has a
  gain near 1 and diverged on Liard (recharge ±2·10⁹ m³/d by day 4). The columns now carry water relative to the
  hydrostatic profile; the water table's fluctuation storage is MODFLOW's Sy. The remap keeps the excess at its
  elevation, clips to porosity and air-dry (difference to the aquifer), and new columns start at equilibrium (as a
  restart does). Also: Newton damping in log steps towards saturation and a suction floor of 10⁵ m (air-dry columns
  no longer lock up), saturated-top memory (inflow ≫ Ks no longer takes 10⁵ substeps), the substep guard rejects
  instead of losing water, and an unmet upward demand is returned signed.
- **Audit round 2.** Ponded-top runs could drive the pressure up without bound; Dirichlet rules now hold the top at
  ψ = 0 (saturated) or ψ = −10⁵ m (air-dry), chosen by the column's memory of which applied last. Newton cycled at
  ψ = 0 where the capacity jumps; the Jacobian's capacity is floored at Ss above −ψa. An unmet upward demand at a dry
  top reached the guard as lost water; the air-dry rule now takes it. With capillary rise off and an existing model the
  rise arrays were unsized (segfault); they are always sized. Whether classes apply was decided by round-off; soil
  water within 10⁻⁹ mm counts as equal.
- **Liard with the columns: 26 812 outer iterations against 6 128 without them.** Columns whose top MODFLOW cell had nearly dried
  passed tiny negative recharge (upward flow through the bottom) to cells MODFLOW was rewetting. With the water table
  within max(5 % of the cell, 5 cm) of the cell bottom the column's bottom takes no upward flow, and a negative bottom
  flux is taken back from the bottom node; the minimum column length is 5 cm. Liard with the columns then needs
  6 349 iterations, close to the 6 128 without them (O2 builds: v1 122 s, v2 default 78 s, all options 100 s).
- **Audit round 3: capillary rise across the shortest column.** Above 5 cm the column's rise was capped at its top
  node's water (about L/3.3 thick, so a few mm per step); below 5 cm the rise from the water table was limited only by
  the soil's deficit, at the start-of-step head. They differed about 20 times (4 042 against 187 m³ on day 1), and a
  thin top layer that dried and rewet made the water table swing 0.4 m from step to step (213 against 110–139 outer
  iterations). Now one routine (`SZRiseLayers`) gives the rise into every layer below field capacity for both: from
  the water table it is implicit in its own drawdown, Q = T(Q dt/(Sy a(1−F))) (Illinois root; no lateral resupply, the
  bound of a single column); from a column it starts at the top node, goes into the same layers on the unsaturated
  share only (it was on the whole column before), and is capped per step by the larger of the top node's water and the
  water table's implicit rate, so the two meet as the column shortens (1 765 against 1 733 m³; test V2i).
- **Found on the way (pre-existing).** With no initial reservoir flow or stage in the .rvc file Raven keeps the stage
  at 0 until its first routing, so the step-1 stage check refused every such reservoir (lake, behaviour, budget_xcheck,
  edge N30 had failed since the base). The check runs after the first step; a warning names the missing initial stage,
  which otherwise makes a one-off jump in Raven's balance (behaviour test: 349 mm; the test now gives the stage). A
  reservoir whose :HRUID lies in another subbasin crashes Raven itself (CReservoir::SetPrecip, also without
  groundwater); the coupled model now stops with a message (edge N32 expects the error).
- **Audit round 4.**
  (B1) While the water table is below the base the exchange is a rate; a head that rose past the base during MODFLOW's
  solve went into the elastic storage above the cell top (heads up to 352 m above the base, MODFLOW's relaxed
  tolerance, unconverged interfaces; the root of the explicit-mode spikes and of most interface non-convergence). Such
  links get a drain in SZD_RAVEN at the lowest base point, smoothed over ds, conductance max(C, Q_in/D) with Q_in the
  link's rate plus its share of the cell's recharge: no flow below the base; above it the water returns to the soil.
  (B2) Sy below the drainable porosity of the column material: a rising water table released more from the column at
  each step (gain eps/Sy > 1). The start-up warning the plan promised (§1.5) is written, and a rising water table
  releases at most Sy dh per step (the column's bottom follows more slowly). With inconsistent Sy a wet column still
  drains into an aquifer that cannot store it: a one-step overshoot remains (warned twice); with consistent Sy none.
  (B3) Upward flows (rise, column upflow, debt repayment) came only out of the top cell, so a water table below a thin
  top layer fed nothing. They now come out of the cell holding the water table through a new WEL package SZW_RAVEN (one
  entry per active cell below each link's top cell); near drying they fade out smoothly (s²(3−2s) over the margin),
  the part of the column's upflow MODFLOW does not supply is taken back out of its bottom node.
  (B4) With columns on, the rise without a column (water table < 5 cm below the base) ignored the aquifer material
  between the water table and the base; it is capped by that material's rise to a dry top over the gap.
  Also: the rise's caps use the lowest layer above the source whether or not it is below field capacity (they jumped
  when it reached field capacity: X3 round trip 0.29 → 2.6e-4); the drawdown root keeps the best lower bound (T(Qw) for
  trials above the root), stops at 0.2 %, and the inner Brent search starts from Gardner's estimate (rise-active runs
  1.7× faster than in round 3); reservoir checks skip disabled HRUs. Pre-existing, documented: the saturated fraction
  that rejects recharge is fixed for the step, so on a slowly permeable aquifer a storm that lifts the water table
  through the base in one step can overshoot for that step.
- **Found on the way (Raven itself).** Raven's ensembles do not reset routing and reservoir outflow between members (also
  without groundwater): the behaviour test now requires the first member to equal the single run and the second to
  start from the same groundwater state with exact accounts.
- **After round 4.** Liard with :SoilZone PHYSICAL, one year, O2 builds: v1 126 s / 4 809 outer iterations; v2 defaults
  77 s / 6 163; columns, rise and three classes 105 s / 6 536; identities below 1e-10. Full suite, CONCEPTUAL Liard and
  existing-model examples (byte for byte but for paths and timings) and the Raven benchmark set (13 models, identical)
  pass.
- **Audit round 5.** (1) A cell below a dried top cell that holds the water table can be a specified head (a generated
  model puts the CHD in the first layer whose bottom is below the head; existing models' IBOUND < 0): MODFLOW ignores a
  well there, but the rise was booked as taken through SZW_RAVEN — water created (half the rise in the test). Now
  NodeCHD (MODFLOW's IBOUND) flags it: the rise is computed without drawdown and booked as specified heads to soil zone,
  the column's upflow as negative recharge onto CHD cells, no repayment is drawn there; the two budget columns are
  written whenever the model has specified heads. (2) Upward rates were not limited by the water of the source cell: a
  thin lowest wet cell was pumped dry within a step and MODFLOW diverged (to NaN with columns). The rise, the column's
  bound Qw and its upflow are at most ½ Sy a (h − bottom)/dt per step; what the column does not get is taken back over its
  nodes from the bottom up. Also the margin of a cell under an inactive one uses the cell directly above, and a column's
  upflow without a source cell goes to the top cell's recharge (never booked without a package). Test V2j.
- **Audit round 6.** The water a falling water table's new column nodes take (MoveBottom's negative excess, _vzAbsQ)
  was neither capped nor routed: it went into the dried top cell's recharge and made MODFLOW diverge (NaN from day 18 in
  a thin-cell test while Raven reported success). The column's bottom now falls only as far as the source cell can give
  (bisection), the uptake goes through SZW_RAVEN (or is supplied by a specified head), and one limit per source cell
  (SZUpCap: ½ f Sy a (h − bottom)/dt) is shared by that uptake, the column's upflow, the rise and the debt repayment
  (repayment beyond it waits). Raven now stops when MODFLOW's heads are not finite. The test helper's recharge identity
  is normalised by the terms' magnitudes (it divided by Raven's recharge, zero in dry spells) and receives the step
  length. Test V2j covers the case. Open, not confirmed as a defect: the lagged-exchange debt of a link whose source is
  a specified head waits until the source is an aquifer cell again (never seen to accumulate).
- **Audit round 7.** When the source cell is the top cell, the column's upflow and uptake go through the top cell's
  recharge (not _vzUp/_vzUpA), and SZRepayRates did not count them: with an open lagged-exchange debt a cell could lose
  twice the limit in a step (a 1 m cell drained to 1 µm above its bottom). The repayment now subtracts them. Existing
  models without NEWTON get a start-up warning (a dried top cell leaves MODFLOW's solve with head HDRY; the soil zone
  over it is then inactive). Not confirmed: unsupplied upflow left after the column's take-back reaches air-dry would
  still be booked from MODFLOW (never observed). Sweeps of 560 pairs against the previous build: no regression.
- **Audit round 8.** (A) A rising water table took the deficit of a column dried by capillary rise (MoveBottom's negative
  excess) whole, into the top cell's recharge: up to 20 times the source cell's limit; MODFLOW unconverged with a balance
  error 26 times the recharge, NaN in the previous build, in thin low-Sy aquifers. The rising branch now limits a
  deficit like the falling one (the bottom follows more slowly), routes it through SZW_RAVEN for a lower source, and
  the water table reaching the base is handled in the same branch. (B) In existing models without NEWTON the dry head
  HDRY (−1e30) was taken as the water table (a column bottom at −1e30 m, 2e32 m³ booked): such columns are now left as they
  are until the cell rewets, and a column read at start-up uses the water table below a dry top cell. (C, open,
  pre-existing) without NEWTON, recharge MODFLOW moves from a dry top cell to the active cell below is not read back
  (Raven's recharge package has no FIXED_CELL): the start-up warning asks for NEWTON. Restarts: MODFLOW's starting heads
  (gwf.ic / raven.ic) are written with 17 significant digits when the soil zone is on (10 before: a head 3e-10 m above a
  cell bottom was rounded away, and with it the upward limits). (The hotstart blocks of solution.rvc are written in
  fixed notation, already 12-15 decimals: unchanged.) A restart can still depart from the continuous run because
  Raven's own HRU state file keeps 5 decimals (round 9: median 2e-6, 90th percentile 3e-4 over 40 random restarts; two
  cases above 1e-2, which a diagnostic build with 15 decimals brings to 3e-7): a limit of Raven's state file, not of the
  coupling. Test V2j extended.
- **Audit round 9.** (A) A column removed in a step (its deficit filled up to the source cell's limit) and the rise from
  the water table in the same step each used the full limit: up to twice it (14 % over in a constructed case). The rise
  now subtracts what the removed column took. (B, pre-existing) A diverged MODFLOW step with finite but absurd heads
  (2e13 m) was accepted and booked impossible volumes (1e15 m³ shortfall); in one ill-conditioned model the more precise
  starting heads tipped a step into it. Raven now stops when a head is not finite or lies beyond the model's highest top or
  lowest bottom by more than 10 times its total relief (at least 1 km), except a dry cell's HDRY without NEWTON (a
  per-cell bound stopped legitimate artesian heads in steep fuzz models). Also: a column's bottom does not
  fall below the aquifer's bottom (a dry column's head can be lower). Sweeps of 768 randomised runs with per-step
  invariants (contents within air-dry and porosity, bottom at or below the base, no unexplained lag, every cap held)
  found nothing else.
