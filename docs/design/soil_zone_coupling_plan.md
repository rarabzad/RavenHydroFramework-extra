# Soil-zone ↔ groundwater coupling (`:SoilZone PHYSICAL`): design as built

Status: implemented on `mf6-groundwater` (Raven) with tests and docs in `RavenHydroFramework-extra`. This file replaces
the design plan of 2026-10-20 (written after James Craig's review: the water table must be able to rise into the Raven
soil profile, on flat ground and on slopes). Where the build departs from the plan, the reason is given. When code and
this file disagree, fix one of them in the same commit.

Code: `src/GWSoilZone.h/.cpp` (pure functions of one soil-zone column, namespace `gwsz`, unit tested on their own),
`src/GWSoilZoneModel.cpp` (the `CGroundwaterModel::SZ*` methods), and the soil-zone parts of `GroundwaterModel.cpp/.h`,
`MF6Engine.cpp`, `ParseGWFile.cpp`, `ParsePropertyFile.cpp`, `ParseInitialConditionFile.cpp`.

---

## 0. What it does

With `:SoilZone CONCEPTUAL` (the default) soil and aquifer meet only through recharge and the seepage drain at the model
top; the results are byte-identical to the code before this work. With `:SoilZone PHYSICAL SOIL[0] … SOIL[M-1]`:

1. **One owner for every depth.** Raven owns the soil zone `SOIL[0..M-1]` of every coupled HRU with soil; MODFLOW owns
   everything below. The MODFLOW model top is the land surface minus the soil-zone thickness.
2. **Two-way, head-driven exchange** at the soil-zone base (GHB package `SZX_RAVEN`, one entry per HRU–cell link): the
   water table rises into the soil and saturated soil drains to the aquifer.
3. **Recharge rejection** where the ground is saturated (Raven's gravity drainage stops there), and saturation-excess
   overflow to `SURFACE_WATER` when the soil zone is full.
4. **Sub-grid saturated area** from the DEM samples of each cell, so a water table that is in the soil at the toe of a
   slope and below it at the top is represented.
5. **Interface iteration inside MODFLOW's outer loop**: the soil zone is solved again after MODFLOW's iterations until
   both agree (a Robin interface condition), so the result does not depend on an explicit lag.

References: GSFLOW (Markstrom et al., 2008, USGS TM 6-D1): soil zone above the MODFLOW domain, gravity reservoirs per
HRU–cell, gravity drainage ceases where the water table is in the soil zone, groundwater discharge to the soil zone,
Dunnian runoff, PRMS soil modules called in the MODFLOW iteration loop. iMOD Coupler MetaSWAP–MODFLOW 6: the unsaturated
zone solved inside every MODFLOW outer iteration through XMI.

---

## 1. Notation

Indices: HRU $k$; grid cell $i$; link $e=(k,i)$ (an HRU–cell overlap with a soil-zone exchange entry); column $c$;
soil layer $j$ of the soil zone, counted **from the bottom** ($j=1$ is `SOIL[M-1]`); DEM sample $s$ of a cell
($N$ samples); time step $n$; MODFLOW outer iteration $\nu$.

| Symbol | Meaning | Unit | Code |
|---|---|---|---|
| $A_k$ | HRU area | m² | `GetArea()*M2_PER_KM2` |
| $A_{k,i}$ | overlap of HRU $k$ and cell $i$ | m² | `gw_link::area` |
| $P_k$ | polygon area of HRU $k$, at least $\sum_i A_{k,i}$ | m² | |
| $a_c$ | area of column $c$ | m² | `_szColA` |
| $H_j$ | layer thickness | m | `sz_layer::H` |
| $\phi_j$ | layer water | mm | `SOIL[m]`, `_szColPhi` |
| $\phi_{max,j}=1000H_jn_j(1-SF_j)$, $\phi_{fc,j}=\phi_{max,j}S_{fc,j}$ | capacity, field capacity | mm | `sz_layer::phimax, phifc` |
| $D_k=\sum_jH_j$ | soil-zone thickness | m | `_szD` |
| $\lambda$ | saturated thickness of a column (mean over its samples) | m | `_szxLam` |
| $z_{b,s}=z_{land,s}-D_k$ | soil-zone base at sample $s$ (sorted ascending) | m | `sz_cell::zbs` |
| $L_v$ | soil water level of a column (flat over its samples) | m | `SubgridLevel` |
| $h$ | head in the top active cell | m | `_X` |
| $h_c$ | connection head (sets the connection weights; $=h$ at convergence) | m | `_szxHc` |
| $d_s$ | connection smoothing depth (`SEEPAGE_SMOOTHING_DEPTH` of the aquifer profile) | m | `sz_cell::ds` |
| $w_s$; $F$ | contact weight of sample $s$; saturated fraction (§5.4) | – | `SubgridFlux`; `_linkF` |
| $C$ | soil–aquifer conductance of a link | m²/d | `sz_cell::C`, `_szxC` |
| $q$ | exchange of a link, **positive into the aquifer** | m³/d | `_szxQc` (local solve), `_szxQ` (MODFLOW's booked flow) |
| $C_g$, $H_g$ | conductance and head of the Robin boundary given to MODFLOW | m²/d, m | `_szxCg`, GHB `BHEAD/COND` |
| $\Delta t$ | time step | d | |

---

## 2. Configuration (`.rvg`)

```
:SoilZone PHYSICAL SOIL[0] SOIL[1]        # soil-zone layers, listed from the top; recharge must leave SOIL[M-1]
:SoilZone CONCEPTUAL                      # default; the last :SoilZone command counts
:SoilZoneIteration 100 1.0E-4 1.0E-6      # updates after MODFLOW converged (0 = explicit predictor only),
                                          #   head tolerance [m], flow tolerance [-]; tolerances optional
:SoilZoneSubgrid 5                        # DEM samples per cell side (N = 25); 1 = cell-mean land surface
:SoilZoneOutput HRU_GROUP                 # optional: GWSoilExchange.csv for one HRU group only
```

Checks (start-up errors unless noted):

- `SOIL[0..M-1]` contiguous from the top and present in the model; every coupled HRU with soil has all of them with
  $H_j>0$, $\phi_{max,j}>\phi_{fc,j}$ (drainable porosity), and `HYDRAUL_COND` $>0$ in `SOIL[M-1]`. HRUs of type LAKE,
  WATER, GLACIER, ROCK, or with a soil zone thinner than 1 µm, have no soil zone and keep the seepage drain.
- `HYDRAUL_COND`, `POROSITY`, `FIELD_CAPACITY` are registered as needed soil parameters when the `.rvg` asks for
  PHYSICAL (`GWFileUsesPhysicalSoilZone`, read ahead of the `.rvp`; otherwise Raven discards them as not needed).
  `HYDRAUL_COND` must be given for the class of the bottom soil-zone layer of every coupled HRU: Raven's automatic
  value (0.001 mm/d) is a placeholder, so the set-up stops there (classes recorded before Raven's auto-calculation,
  `NoteSoilClassWithoutKsat`). Classes used only outside the soil zone do not need it.
- Every process with `GROUNDWATER` as target in a coupled HRU must draw from `SOIL[M-1]`; lateral processes may not
  move water into or out of `GROUNDWATER` of a coupled HRU. Where a `PERC_CONSTANT` process from `SOIL[M-1]` applies
  (per HRU, through its conditions) the recharge leaves the columns by area (§4).
- $D_k\le20$ m (warning above 5 m). `SOIL_ZONE_DEPTH` is ignored (warning). `:SeepageReturnTo` applies only to the HRUs
  without a soil zone (warning).
- Storage consistency: warning where the top layer's $S_y$ and the drainable porosity of `SOIL[M-1]` differ by more
  than a factor 2 (the water table then rises at different rates below and inside the soil, §5.7).
- `RECHARGE_DELAY` > 0 in the profile of a soil-zone HRU: error (the delay store would hold recharge that the saturated
  soil zone rejects).
- Warnings: `SEEPAGE_SMOOTHING_DEPTH` below 0.05 m (the contact switches almost abruptly); `:SolverMaxOuterIterations`
  below 20 (the interface is updated within MODFLOW's outer iterations); an HRU whose soil-zone base lies more than
  max(0.05 m, 0.1 D) from the model top (cells shared with lakes or other soil-zone thicknesses: between the two levels
  soil and aquifer both store water, or neither does).
- `:SoilZoneIteration`, `:SoilZoneSubgrid`, `:SoilZoneOutput` without PHYSICAL: warning, ignored.
- Existing-model mode (`:MF6Simulation`): PHYSICAL is refused (not yet available).

---

## 3. Geometry

### 3.1 Soil-zone base and model top

$$z_{top,i}=z_{land,i}-\frac{\sum_kA_{k,i}D_k}{\sum_kA_{k,i}}$$

(HRUs without a soil zone contribute $D_k=0$.) The base of a link follows the DEM inside the cell: at sample $s$ it is
$z_{b,s}=z_{land,s}-D_k$.

### 3.2 Conductance (no new parameter)

Series resistance of half the bottom soil-zone layer and half the top active aquifer cell:

$$C_e=\frac{A_{k,i}}{\dfrac{H_1}{2\,k_{sat,1}/1000}+\dfrac{b_{top,i}}{2\,K_{v,top,i}}}\quad[\mathrm{m^2/d}]$$

($b_{top}$ the full thickness of the top active cell, so $C$ is fixed during the step.)

### 3.3 Links and entries

One `SZX_RAVEN` GHB entry per link whose top cell is active and not a specified-head cell (`gwf.szx`, written with
head $\max(z_b,\ \text{bottom}+1\,\text{mm})$ and conductance 0; Raven sets both in memory). A WEL package `SZQ_RAVEN`
(`gwf.szq`) and a smoothed DRN package `SZD_RAVEN` (`gwf.szd`, auxiliary `DDRN`) have one entry per link as well
(§7.1, §7.3). The seepage drain `DRN_RAVEN` keeps only the share of the cell
covered by HRUs without a soil zone (conductance × that share), and its discharge returns only to those HRUs.

---

## 4. Soil-zone columns

The soil zone of HRU $k$ is split into one column per link with an SZX entry plus a **rest** column (the parts of the HRU
over specified-head cells or outside the grid); this is GSFLOW's gravity reservoir per HRU–cell.

$$a_e=A_{k,i}\,\frac{A_k}{P_k},\qquad a_{rest}=A_k-\sum_ea_e\ (\ge0)$$

The link's conductance (§3.2) is scaled by $a_e/A_{k,i}$ too, so that it acts on the column's area (with the overlap
area, an HRU whose polygon is larger than its `AREA` exchanged its soil water that much faster).

Each column keeps its own layer water $\phi_{c,j}$. Raven's `SOIL[m]` of the HRU is the area-weighted mean of its
columns. Raven's processes change the HRU totals between exchanges; `gwsz::Distribute` shares the changes among the
columns as the processes would have made them in each column, in Raven's order:

1. the percolation between the layers is reconstructed from the bottom up: the flux $P_l$ from layer $l+1$ into layer
   $l$ explains layer $l$'s change together with what it passed down ($P_l=\max(0,\ \Delta_l+P_{l-1})$, the bottom
   layer's change counted before the recharge $R$, end-of-step `GROUNDWATER`, which only `SOIL[M-1]` fills); what
   remains of each layer's change are its other gains (rain) and losses (evaporation);
2. the percolation is applied from the top down within each column: each layer receives what its own column's layer
   above passed down and gives up its own share to the same column's layer below, by area for a constant rate
   (`PERC_CONSTANT`: each column alike, where it has the water) or from free water first for a drainage (the other
   types: in proportion to each column's water above field capacity); then the bottom layer gives up the recharge the
   same way;
3. the other losses (evaporation) are taken alike on every column, limited to its water;
4. the other gains (rain) fall on every column alike; what a full layer of a column cannot hold moves up in the same
   column, and what its top layer cannot hold overflows to the HRU's `SURFACE_WATER` (saturation excess on the full
   columns) and is counted in the soil-zone overflow.

Where the columns that hold an upper layer's water have a full layer below and the columns with room below have no
water above, the percolation Raven computed on the HRU mean cannot happen in any column; it stays in the upper layer
(moved back up), and Raven's layers are then set to the column means. That volume is reported per step in
`GWBudget.csv` (*soil-zone layer redistribution*; always 0 with a single soil-zone layer, and the sync of hotstart
columns with the `.rvc` soil water counts in the first step). Mixed percolation types: the sharing rule (by area for
`PERC_CONSTANT`, else free water first) follows the process from `SOIL[M-1]` to `GROUNDWATER` (also inside a
`:ProcessGroup`, under the group's conditions as well as its own) and is used for the
percolation between the soil-zone layers as well.

(Taking the recharge before the percolation that fed it, the previous build drove columns below zero; unit test
"Raven's process order".)

`SZSyncColumns` does this at the start of every exchange, after which Raven's `SOIL[m]` is set to the column means.
(The first builds shared gains by room and all losses from free water first: rain on the saturated toe of a slope moved
instantly to the dry columns upslope, and percolation and evaporation moved water from the saturated to the dry columns.
Against ten one-cell HRUs, one HRU over the same ten cells now gives the hillslope's total outflow within 3% for
`PERC_CONSTANT`, `PERC_GAWSER`, `PERC_GAWSER_CONSTRAIN` and `PERC_LINEAR` on gentle and steep slopes, within 3% with one
or two layers and evaporation, 7% with three layers; robustness tests R2, R2c.)

Departure from the plan: the plan had one soil water level per HRU. With a slope, one level per HRU makes the cells
of the HRU exchange with each other through the soil instantly; per-link columns keep the exchange local, as in GSFLOW.

---

## 5. Physics of one column (`GWSoilZone.cpp`)

### 5.1 Saturated thickness

Saturated share of layer $j$: $s_j=\mathrm{clip}\big((\phi_j-\phi_{fc,j})/(\phi_{max,j}-\phi_{fc,j}),0,1\big)$
(a layer without free-water capacity counts as saturated only when full). Product closure, layers from the bottom:

$$\lambda=\sum_jH_j\,s_j\prod_{i<j}s_i$$

With every layer below full this is the stack definition (the level rises through a layer once the layers below are
full). Free water perched above a partly saturated layer counts in proportion to how saturated the layers below are,
which keeps $\lambda$ continuous and non-decreasing in every $\phi_j$ (the plan's hard "count only once the layer
below is full" jumps when the layer below fills, and then the local solve has no root).

### 5.2 Fill and drain

`Fill(V)`: from the bottom up, each layer to $\phi_{max}$; what does not fit is overflow. `Drain(V)`: free water
($\phi-\phi_{fc}$) from the top of the saturated stack downwards; never perched water above it. `Apply(dV)`: Fill for
$dV>0$, Drain for $dV<0$; a removal that free water cannot supply (round-off only) is taken below field capacity,
and what even that cannot supply is the shortfall (reported; 0 in all tests).

### 5.3 Sub-grid soil water level

The column's free water is a flat soil water level $L_v$ over the cell's samples (as MODFLOW's head is flat over the
cell): the saturated thickness at sample $s$ is $\mathrm{clip}(L_v-z_{b,s},0,D)$ and

$$\frac1N\sum_s\mathrm{clip}(L_v-z_{b,s},0,D)=\lambda$$

defines $L_v(\lambda)$ (`SubgridLevel`: exact walk over the breakpoints $z_{b,s}$ and $z_{b,s}+D$; the inverse is
`SubgridThickness`). $\mathrm dL_v/\mathrm d\lambda=N/n_{active}$ is taken on the segment above a breakpoint.

### 5.4 Contact and saturation

$$w_s=\sigma\!\left(\frac{h_c-z_{b,s}}{d_s}+1\right),\qquad F=\frac1N\sum_s\sigma\!\left(\frac{h_c-z_{b,s}}{d_s}\right),\qquad \sigma(x)=\begin{cases}0&x\le0\\3x^2-2x^3&0<x<1\\1&x\ge1\end{cases}$$

Contact $w_s$ (the exchange): a sample comes into hydraulic contact as the water table rises through the depth $d_s$
*below* its base (the capillary fringe), fully at its base. Saturation $F$ (rejection, water-table ET, the reported
saturated fraction): as the water table rises through $d_s$ *above* the base. ($d_s\le0$: steps at the base.)

Departure from the first build: the contact ramp was above the base. MODFLOW's top cell has the soil-zone base as its
top and no specific yield above it, so an outlet that opened only above the base left a confined gap in which the head
jumped by metres within one outer iteration and the interface cycled (robustness test R1). With full contact at the
base the soil zone's storage takes over exactly where MODFLOW's ends, as the seepage drain's smoothing does below the
model top. Rejection keeps the ramp above the base: recharge stops only where the water table is in the soil.

### 5.5 Exchange law

$$q=\frac CN\sum_sw_s\Big(\mathrm{clip}(L_v,z_{b,s},z_{b,s}+D)-\max(h,z_{b,s})\Big)$$

With one sample and the water table above the base: $q=C(z_b+\lambda-h)$. The aquifer side of a sample is the water
table, or its base where the water table is below it: a sample in contact while the water table is still within $d_s$
below its base (or while $h_c$ lags above $h$) drains just its own saturated water to the aquifer, never the empty soil
beneath it, and nothing can rise into it (so $q\le0$ at $\lambda=0$ always). The exchange is continuous in $h$ for
$d_s>0$ (a sample holding perched water starts draining it smoothly as the water table comes within $d_s$); with
$d_s=0$ it jumps.

Partial derivatives (`SubgridFlux`): $q_h=-\frac CN\sum_{z_{b,s}<h}w_s$, $q_{h_c}$,
$q_\lambda=\frac CN\sum_{\text{active }s}w_s\,\mathrm dL_v/\mathrm d\lambda$.

Why GHB and not RIV/DRN: a RIV's disconnected branch would add a second gravity-drainage path next to Raven's
percolation; DRN is one-directional. The cut-off below the base comes from the contact weights.

### 5.6 Local backward-Euler solve (per column, given $h$, $h_c$)

$\phi^*$ = column water after Raven's processes plus the link's rejected recharge (§6.1). With $c=1000\Delta t/a_c$
[mm per m³]:

$$g(dV)=dV+c\,q\big(\lambda(\mathrm{Apply}(\phi^*,dV)),h,h_c\big)=0,\qquad dV\in[-\text{free water},\ \text{room}]$$

$g$ is continuous and strictly increasing ($q$ is non-decreasing in $\lambda$), so it has one root; `LocalSolve` finds
it by bisection (relative 10⁻¹³). If $g(\text{room})<0$ the column fills and $-g(\text{room})$ overflows. It returns
$\lambda$ at the root and $\lambda'=\mathrm d\lambda/\mathrm dV$ there (one-sided on the side that stays inside the
interval; 0 when full).

### 5.7 Storage consistency

Below the base the water table rises at $r/S_y$, inside the soil at $r/S_d$ ($S_d$ the drainable porosity). Different
materials make the rate change at the base; the start-up warning (§2) flags a factor above 2. T1b tests it.

---

## 6. Recharge, ET and the seepage drain

### 6.1 Recharge rejection

The HRU's recharge this step (end-of-step `GROUNDWATER`) is shared among its links in proportion to the recharge each
link's column gave up (§4, step 1; by area if the recharge is 0). (Shared by area, drainage from saturated columns at
the toe of a slope recharged the aquifer upslope and circulated back: robustness tests R2, R2c. Shared by the free water
a column lost in the net change, a column 1e-12 mm wetter than the others received the whole HRU's recharge: test R8.) Of a link's share, $F$ is rejected (returned to that link's column before its local solve) and $(1-F)$
goes to MODFLOW's RCH. Recharge onto specified-head cells and outside the grid is handled as in CONCEPTUAL mode.
`Raven recharge` in `GWBudget.csv` includes the rejected water (Raven drains the free water each step and rejection
returns it), so the net recharge is `MF6 recharge`.

### 6.2 Water-table ET

`EVT_RAVEN` surface = model top (the soil-zone base); its rate is scaled by $(1-\bar F_i)$ (the area-weighted $F$ of
the cell): saturated soil already evaporates in Raven.

### 6.3 Seepage drain

See §3.3: `DRN_RAVEN` serves only the HRUs without a soil zone; groundwater reaching the land surface under soil-zone
HRUs fills the soil and leaves as overflow.

---

## 7. Interface with MODFLOW

### 7.1 Robin boundary

For each link MODFLOW gets $q=C_g(H_g-h)$, linear in its own head, which reproduces the local solve's exchange $q^*$ at
the current head $h^*$ and its slope with the column's response included (implicit function theorem on §5.6, $h_c$
held):

$$C_g=\frac{-q_h}{1+c\,q_\lambda\,\lambda'},\qquad H_g=h^*+\frac{q^*}{C_g}$$

Floors on $C_g$ (a slope too large only slows the convergence, one too small can make it diverge):

- the secant through the last local solve of the step, $-(q^*-q_{prev})/(h^*-h_{prev})$ (capped at $-q_h$): the
  exchange steepens as a function of the head where the column fills ($\lambda'\to0$, the slope jumps from
  $-q_h/(1+c\,q_\lambda\lambda')$ to $-q_h$); a slope from the unfilled side let MODFLOW overshoot across the kink and
  cycle (Liard T7, an HRU with drainable porosity 0.02 against $S_y=0.25$);
- for $q^*<0$ (water rising into the soil) the secant $-q^*/(h^*-(z_{b,min}-d_s))$ to the level where the contact ends,
  so a linear boundary never extracts water from a cell below every base (a floor taken at the base itself was far too
  stiff just above it and the iteration crept);
- $10^{-9}C$. Where $C_g\le10^{-6}C$ the link is passed as a rate (GHB conductance 0, WEL carries $q^*$).

$C_g$ sets only how fast the interface converges: at a converged interface MODFLOW's flow equals the local solve's
whatever $C_g$.

MODFLOW refuses a GHB head below the cell bottom. Where $H_g<\text{bottom}+1$ mm the GHB head is the bottom
(+1 mm) and the WEL `SZQ_RAVEN` carries $C_g(H_g-\text{bottom})$; the boundary $q(h)=C_g(H_g-h)$ is unchanged.

### 7.2 Step sequence

1. `Exchange`: `SZSyncColumns` (Raven's processes → columns).
2. Predictor: $h_c=h^n$; $F$, recharge split, local solves, arrays (`SZLinkFractions`, `SZRecharge`, `SZLocalSolves`,
   `SZSetArrays`).
3. MODFLOW's outer loop (`CMF6Engine::SolveTimeStep`) with the callback `SZIterate` after every outer iteration.
4. Final flows read from MODFLOW (`HCOF·h − RHS` of SZX + SZQ), the non-convergence guard, `SZApply`.

### 7.3 Schedule and budget

The interface is updated after each of the first $\min(5,\ \text{max outer}/5)$ outer iterations (on easy steps both
converge together), and after that only after iterations on which MODFLOW has converged, so the changing boundary does not keep MODFLOW's own
iteration (under-relaxation, backtracking) from converging. Updates made after MODFLOW converged count against the
budget (`:SoilZoneIteration` max, default 100); when it is used up the values are frozen. 0 = the explicit predictor
only. MODFLOW's tolerance relaxation for hard steps counts only iterations MODFLOW did not converge on. The last
$\max(2,\ \text{max outer}/10)$ outer iterations are left to MODFLOW on the boundary it has: an update just before the
limit left MODFLOW's final solve unconverged, and its residual was water created or lost (robustness test R5). Iteration
1 always updates when there is a second; with `:SolverMaxOuterIterations` 1 only the predictor runs, supply-limited as
in explicit mode, and the step is reported as not converged. The update after outer iteration
$\text{max outer}-\max(2,\ \text{max outer}/10)$, the last one possible, and the last one the update budget allows
make their boundary supply-limited as in explicit mode. Once the interface is frozen nothing changes any more: a further supply-limited update after the freeze
(tried in round 6) left too few solves for MODFLOW to absorb it on steps MODFLOW could not converge, and its residual
was water created or lost (relative MODFLOW error up to 6e-3 with 30 outer iterations, against 1e-12 without it;
audit round 7), while no case showed a shortfall it prevented.
A boundary MODFLOW keeps without further updates (explicit mode, `:SoilZoneIteration 0`; the update after iteration
$\text{max outer}-\max(2,\ \text{max outer}/10)$; the last update the budget allows) may not take more from a column
than it holds, whatever the head does:

- where the soil drains to the aquifer ($q\ge0$) the slope is limited so that $C_g(H_g-\text{bottom})$ never exceeds
  the column's free water over the step (robustness test R7);
- where water rises into the soil ($q<0$), the line could take more than the column holds (its slope above that
  limit) and the cell is not dry at the head of linearization, the line is given to MODFLOW as a drain, `SZD_RAVEN`: $q=-C_g(h-H_g)$ above $H_g$, nothing below, with the
  onset smoothed by MODFLOW's `DDRN` over half the distance to $H_g$ (at most $d_s$, at least $d_s/4$). The secant
  floor keeps $H_g$ at or above the end of the contact, so it neither reverses into flow from the soil nor lifts water
  from below the contact. A drain level below the cell bottom is raised to the bottom by steepening the line (at most
  to the link conductance), not continued by a fixed rate that would pump a dried cell (robustness test R10). In a cell
  dry at the head of linearization the line stays: a drain there is inactive at that head, MODFLOW's first Newton
  iterate saw no boundary and its head ran away (audit round 10: heads 70 m above the cell top, MODFLOW unconverged,
  10⁷ m³/d booked in explicit discharge-zone runs; overflow 28–420% too high even where MODFLOW converged).

A linear boundary cannot hold both limits for rising water. With the secant floor winning, a head falling below $H_g$
reversed the boundary and drained columns without free water (water created; audit round 8: 4100 m³ with an update
budget of 1, 7900 m³ in explicit mode on a steep low-storage hillslope); with the supply limit winning, the boundary
kept lifting water when the head fell below every base (audit round 9: explicit outflows 44–164% off, a restart chain
diverging). The drain does neither: the explicit runs of the audit batch now give the iterated runs' outflow within
0.1–2% (they were 30–50% off), and the budget and explicit shortfall cases are 0 with 30 or more outer iterations. With fewer than 10
MODFLOW solves left (low outer-iteration limits) the line stays, limited as far as the secant floor allows, because
MODFLOW did not settle on the changed boundary in so few iterations; a reversal can then still overdraw (§11). Dropped
remedies: an unsmoothed drain everywhere (MODFLOW failed to converge where much water rises), limiting the slopes of
the boundary MODFLOW already has at the freeze, and extracting a carried shortfall from the aquifer in later steps
(both turned the shortfall into larger MODFLOW residuals).

### 7.4 Connection head update

After an iteration on which MODFLOW converged, per link, residual $r=h-h_c$:

- plain update $h_c\leftarrow h$;
- secant extrapolation while $r$ keeps its sign and shrinks ($0<r/r_{prev}<0.95$);
- Illinois regula falsi once $r$ has changed sign (bracket reset when it collapses).

Before MODFLOW has converged, $h_c=h$ and the history is reset (brackets from unconverged heads mislead).

Departure from the plan: the plan iterated the soil level with under-relaxation $\omega$. Relaxing the level (and
Aitken acceleration of $\lambda$ and $F$) cycled on stiff cases; lagging only the connection, with the column's
response inside $C_g$, converges in ≤ 8 updates on the stiffest test (T5).

### 7.5 Convergence and consistency

Converged when

$$\max_e\Big(|\Delta\lambda_e|,\ \frac{|q(h,h)-q(h,h_c)|}{C}\Big)<\delta_h\quad\text{and}\quad|\Delta Q|\le\max\Big(\delta_q\textstyle\sum|q|,\ \sum FC\cdot\max(\delta_h,\mathrm{DVCLOSE})\Big)$$

($Q=\sum_eq_e$, change since the previous update; $F$ here is the contact fraction, the mean contact weight of the
link) and MODFLOW has converged. On convergence, and after the last
allowed outer iteration (no solve follows), the state MODFLOW last solved with is restored ($F$, $h_c$, $\lambda$, $q$,
$C_g$, rejection) and the arrays are not rewritten, so MODFLOW's budget and the flows Raven books agree exactly.

A step whose interface did not converge is reported (warning, first 10, with the HRU and cell); Raven still applies
MODFLOW's booked flows, so mass is conserved. The guard for steps on which MODFLOW did not converge (seepage and river
gains returned to Raven limited to the step's inflow) does not limit the soil-zone exchange: the soil zone takes any
flow MODFLOW booked, and what does not fit overflows.

### 7.6 Applying the step (`SZApply`)

Per link column: Fill(rejected recharge), then Apply($-q\Delta t/a_c$) with $q$ = MODFLOW's booked flow; overflow →
`SURFACE_WATER` of the HRU (routed the same step); shortfall counted. Raven's `SOIL[m]` = column mean.

---

## 8. Initialization, steady state, hotstart

- **Cold start**: after MODFLOW's initial heads (and the optional steady state) and before Raven takes its initial
  storage, each link column is filled up to $\lambda=$ `SubgridThickness`$(h_0)$ (`SZInitColumns`); the rest column
  keeps Raven's initial soil water; Raven's `SOIL` becomes the column mean.
- **Steady-state initialization**: the soil zone has no storage; the boundary is the local exchange law with
  $\lambda=0$ (water table above the base drains at the base), iterated the same way.
- **Hotstart**: `:GWSoilZoneColumns` in `solution.rvc` (HRU ID, cell = grid column number of the link, 0 for the rest
  column, water of each layer from the bottom up); columns are matched by cell, not by order. A block that does not
  match the HRU's columns (grid or `:SoilZone` changed) is reported and the columns start from the water table. Soil
  water in the `.rvc` beyond what full columns hold starts in `SURFACE_WATER` (warning). (The block was keyed by
  column order only in unreleased development builds; there are no files of that format to read.)
- In a run without `:GroundwaterModel MODFLOW6`, groundwater blocks in the `.rvc` are skipped (each to its own end
  line) with a warning.

---

## 9. Water balance (checked every step by the tests and `tools_audit.py`)

1. Recharge: Raven recharge = MF6 recharge + rejected + recharge onto CHD cells + change of the delay store.
2. Soil zone: exchange applied to Raven = rejected + (aquifer → soil − soil → aquifer)·Δt + shortfall.
3. MODFLOW residual (all packages, SZX and SZQ included) ≈ 0.
4. Raven's mass-balance error = change of the pass-through `GROUNDWATER` store (pre-existing Raven reporting).

`GWBudget.csv` columns: soil zone to aquifer, aquifer to soil zone [m³/d], rejected recharge, soil-zone overflow,
exchange applied to Raven, shortfall [m³], interface updates, interface converged, interface change [m], soil-zone
layer redistribution [m³]. `GWSoilExchange.csv` per
step and HRU: base, soil water level, water table, saturated fraction, exchange both ways, rejected, overflow, soil
water and capacity, interface updates and change. `tools/plot_soilzone.py` draws both.

---

## 10. Tests (`tests/soilzone/`, in `run_all.py`)

| Step | What |
|---|---|
| `soilzone_unit` | `soilzone_unit.cpp`: λ, Fill/Drain/Apply mass, sub-grid level and its inverse, flux derivatives against finite differences, continuity across sample bases, local solve (monotone, root, mass, $h_c\neq h$ included), the Robin slope, Distribute; 20 000 random cases each |
| `soilzone_spike` | V1–V3: named input arrays reach the solver between outer iterations, coefficients recomputed every iteration, a solve after convergence is a normal iteration |
| `soilzone_column` | T1/T1b flat column: rise 50 (125) mm/d below the base, 50 mm/d inside the soil, water table = soil level once connected, soil full on day ~41, storage warning |
| `soilzone_hillslope` | T2/T3 hillslope vs a monolithic MODFLOW reference (soil as top layer, DRN at the land surface): heads, soil water, outflow |
| `soilzone_dynamics` | T4 step size (1 d, 6 h, 1 h against same-Δt references; errors fall with Δt), T5 stiff conductance (iterated vs explicit), sub-grid case |
| `soilzone_restart` | 300 d vs 150 + 150 d from `solution.rvc`: identical to 1e-6 relative |
| `soilzone_inputs` | input handling: missing `HYDRAUL_COND`, short `:SoilZoneIteration`, last `:SoilZone` counts, ignored options, mismatched and reordered hotstart, `.rvc` groundwater blocks without a groundwater model |
| `soilzone_robustness` | R1 stiff column (drainable porosity 0.02, $S_y$ 0.25) converges in few updates; R2/R2c one HRU over ten cells = ten HRUs (total outflow within 3% with free-water drainage and with constant-rate percolation); R3 `RECHARGE_DELAY` refused; R4 small smoothing depth reported; R5 hourly steps with 0.001 m smoothing leave no MODFLOW residual; R6 steep sub-grid hillslope converges; R7 explicit mode has no shortfall; R8 recharge shares insensitive to round-off; R9 hotstart layer redistribution reported in step 1; R10 frozen (budget 1) and explicit boundaries never overdraw on rising water; R11 explicit mode within 3% of the iterated outflow (0.1%; a line was 32% off); R12 explicit discharge zone with cells dry at the head of linearization converges and matches the iterated outflow; R13 neither MODFLOW's residual nor the soil-zone shortfall is handed to Raven (outflow x1.00 of the iterated run; was x17) |
| `soilzone_liard` | T7 Liard PHYSICAL variant (365 d): all identities |

Regression: every existing test without `:SoilZone` gives byte-identical outputs (both Liard examples compared).

---

## 11. Known limitations

- **Operator splitting.** Raven's vertical processes run before the exchange in each step, so daily steps carry a
  first-order splitting error against a monolithic model (hillslope: mean 1.5 cm daily, 0.5 cm at 6 h, 0.16 cm at 1 h;
  outflow within 0.03%). Shorter steps reduce it.
- Raven's processes act on the HRU mean of the soil water; the columns differ through the exchange and the rules of
  §4. One HRU over ten cells against ten one-cell HRUs (total outflow): within 3% for one or two layers with drainage
  types, 4–7% with three or four layers, up to 12% with `PERC_CONSTANT`, and up to about 20% with evaporation from
  saturated soil (the HRU keeps evaporating at the rate of its mean moisture).
- The rest column (parts of the HRU over specified-head cells or outside the grid) has no exchange: it does not see a
  specified head above its base.
- Churn with fast drainage: Raven drains a column's free water every step and rejection returns the saturated share,
  while the unsaturated share recharges the aquifer, which on steep sub-grid cells discharges it back into the low
  points of the same cell. Mass is conserved and the net exchange is right, but `Raven recharge`, `MF6 recharge` and
  the gross exchange both ways can exceed the rain several times (5x5 samples on slope 0.1 with `PERC_GAWSER_CONSTRAIN`
  at 1000 mm/d). Weighting the rejection by where the free water sits did not remove it and made the interface converge
  worse, so it was not kept.
- `GWSoilExchange.csv`: the interface columns (updates, change) are model-wide values repeated on every HRU row; with
  sub-grid samples the HRU's soil water level is an area-weighted mean and can stand above its mean water table.
- Not available with an existing MODFLOW model (`:MF6Simulation`).
- MODFLOW 6.5 or later (user guide): from 6.4.3 on the drain's `DDRN` is read from the input context (`AUXVAR_IDM`),
  which Raven writes; 6.4.2 would take the `AUXVAR` fallback but gives different explicit-mode results even without
  the drain.
- With $d_s=0$, perched water joining the water table makes the exchange jump; keep $d_s>0$.
- **Low outer-iteration limits.** When MODFLOW does not converge within `:SolverMaxOuterIterations` (below about 20 it
  is warned at setup), two things can create water on such steps:
  - the boundary it keeps can be one from an earlier, not supply-limited update, or (below 10 solves left: explicit
    mode with a limit below 10, an update budget of 1–2 with a limit below about 30) a line rather than the one-sided
    drain, and MODFLOW's head can move far from where it was linearized: it can then take more from a column than it
    holds (`soil-zone shortfall [m3]`);
  - MODFLOW's last iterate can book more outflow than its inflows and storage release supply (its residual, `MF6
    balance error`).

  Neither is handed to Raven as water: on every step the shortfall the booked exchange would leave (a trial of the
  booking) and, on an unconverged step, a negative residual are withheld from all discharge to Raven (seepage, gains of
  enabled subbasins, surface-store gains, the exchange into the soil zone) in proportion (`discharge to Raven withheld
  [m3]`). Audit rounds 11–12: an outer-iteration limit of 12 on a stiff hillslope gave 17 times the iterated outflow,
  then 1.85 times with the residual withheld, and 1.00 times with the shortfall withheld as well (R13). What the step's
  discharge cannot cover stays in the aquifer's storage and can leave in later steps; only negative residuals are
  withheld, so positive and negative residuals of consecutive steps no longer cancel in the cumulative balance. None
  of this occurs with the default limits (500 outer iterations, budget 100) in any test. (The older guard that capped
  discharge at the step's inflows left out the storage release and removed real discharge; with `:SoilZone PHYSICAL`
  it is not used.)

## 12. Answers to the plan's open questions

(a) Equilibrium above the water table: kept (free water collects at the bottom of the stack, §5.1), with perched water
counted in proportion. (b) Rejected recharge returns to the link's column (from the bottom up, §5.2). (c) The smoothing
depth is `SEEPAGE_SMOOTHING_DEPTH` of the aquifer profile (no new parameter).
