"""Synthetic Raven + MODFLOW 6 models for the soil-zone tests (manual, "Verification", "The soil zone").

make_case(d, **cfg) writes a complete model in folder d:
  a strip of nhru HRUs (each hru_w x width m) along x, ground sloping down along x at `slope` (DEM raster),
  soil SOIL[0..1] (thickness H0,H1 m; POROSITY n, FIELD_CAPACITY sfc, HYDRAUL_COND ksat mm/d),
  rain `rain` mm/d (list of daily values or constant) into SOIL[0], percolation SOIL[0]->SOIL[1] and SOIL[1]->GROUNDWATER
  (`perc_type`, default PERC_CONSTANT at `perc` mm/d; PERC_GAWSER_CONSTRAIN drains only water above field capacity),
  time step `timestep` d (daily forcing), one unconfined aquifer layer (Sy, Kh, Kv, thickness to bedrock), optional fixed head at the
  downslope end, :SoilZone PHYSICAL SOIL[0] SOIL[1] (or CONCEPTUAL with physical=False).
  dem_fn(x, y) [m]: optional relief added to the planar land (irregular "amorphous" ground; default None: the plane, unchanged);
  dem_res: DEM raster columns (default 200).
"""
import os, json, math

LAT0, LON0 = 55.0, -120.0
R_EARTH = 6371007.181          # sphere of Raven's Lambert azimuthal equal-area projection (origin = model centre)
_P0, _L0 = math.radians(LAT0), math.radians(LON0)

def ll(x, y):
    """lon, lat of projected x, y [m] (inverse LAEA), so HRU edges fall exactly on cell edges"""
    rho = math.hypot(x, y)
    if rho < 1e-9:
        return (LON0, LAT0)
    c = 2.0 * math.asin(rho / (2.0 * R_EARTH))
    lat = math.asin(math.cos(c) * math.sin(_P0) + y * math.sin(c) * math.cos(_P0) / rho)
    lon = _L0 + math.atan2(x * math.sin(c), rho * math.cos(_P0) * math.cos(c) - y * math.sin(_P0) * math.sin(c))
    return (math.degrees(lon), math.degrees(lat))

def xy(lon, lat):
    """projected x, y [m] of lon, lat (forward LAEA)"""
    p, l = math.radians(lat), math.radians(lon) - _L0
    k = math.sqrt(2.0 / (1.0 + math.sin(_P0) * math.sin(p) + math.cos(_P0) * math.cos(p) * math.cos(l)))
    return (R_EARTH * k * math.cos(p) * math.sin(l), R_EARTH * k * (math.cos(_P0) * math.sin(p) - math.sin(_P0) * math.cos(p) * math.cos(l)))

def make_case(d, nhru=1, hru_w=200.0, width=200.0, cell=100.0, slope=0.0, z0=100.0,
              H0=0.5, H1=0.5, n=0.4, sfc=0.5, ksat=100.0, phi0=None,
              rain=10.0, perc=10.0, days=60, Sy=0.2, Kh=10.0, Kv=1.0, aq_thick=20.0,
              init_depth=2.0, chd=None, physical=True, smooth=0.5, subgrid=5,
              iteration=None, pet=0.0, steady=None, extra_rvg='', perc_type='PERC_CONSTANT', timestep=1.0,
              soil_b=None, soil_psia=None, aq_b=None, aq_psia=None, top=None, demf=None, aq_conf=False, extra_proc='', extra_soil=None, aq_layers=None,
              dem_fn=None, dem_res=None):
    # top: thickness [m] of a separate top aquifer layer (default: one layer to bedrock); demf(x, y): relief [m] added to the
    # planar DEM (e.g. an egg-crate); aq_conf: the layer below the top layer is CONFINED_AQUIFER;
    # extra_proc: process lines added after the percolation; extra_soil: {parameter: value} added to the soil parameters
    # (e.g. GR4J_X2); aq_layers: [(thickness or 'TO_BEDROCK', type), ...] the aquifer profile's layers
    # dem_fn(x, y): the same as demf (name used by the depth-class tests); dem_res: DEM raster columns (default 200)
    if demf is None: demf = dem_fn
    os.makedirs(d, exist_ok=True)
    L = nhru * hru_w
    # HRU polygons, centred on (LON0, LAT0): Raven's grid origin snaps to whole cells around that centre, so with
    # L and width multiples of 2*cell the HRUs fill whole cells
    feats = []
    xs, ys = -0.5 * L, -0.5 * width
    for k in range(nhru):
        x0, x1 = xs + k * hru_w, xs + (k + 1) * hru_w
        ring = [ll(x0, ys), ll(x1, ys), ll(x1, ys + width), ll(x0, ys + width), ll(x0, ys)]  # edges ~1e-4 m from straight
        feats.append({"type": "Feature", "properties": {"HRU_ID": k + 1}, "geometry": {"type": "Polygon", "coordinates": [ring]}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(d, 'hru.geojson'), 'w'))
    # DEM raster (ESRI ASCII, lon/lat), fine enough to resolve the slope inside cells
    ncol, nrow = (200, 20) if dem_res is None else (int(dem_res), 20)   # dem_res: DEM columns (irregular land needs a finer raster)
    lonA, latA = ll(xs - 0.05 * L, ys - 0.5 * width); lonB, latB = ll(xs + 1.05 * L, ys + 1.5 * width)
    cs = (lonB - lonA) / ncol
    nrow = max(2, int(math.ceil((latB - latA) / cs)))
    with open(os.path.join(d, 'dem.asc'), 'w') as f:
        f.write('ncols %d\nnrows %d\nxllcorner %.10f\nyllcorner %.10f\ncellsize %.12f\nNODATA_value -9999\n' % (ncol, nrow, lonA, latA, cs))
        for r in range(nrow):
            row = []
            for c in range(ncol):
                x, y = xy(lonA + (c + 0.5) * cs, latA + (nrow - r - 0.5) * cs)
                row.append('%.4f' % (z0 - slope * (x - xs) + (demf(x, y) if demf else 0.0)))
            f.write(' '.join(row) + '\n')
    # .rvh
    with open(os.path.join(d, 'm.rvh'), 'w') as f:
        f.write(':SubBasins\n  :Attributes, NAME, DOWNSTREAM_ID, PROFILE, REACH_LENGTH, GAUGED\n  :Units, none, none, none, km, none\n  1, box, -1, NONE, ZERO-, 1\n:EndSubBasins\n')
        f.write(':HRUs\n  :Attributes, AREA, ELEVATION, LATITUDE, LONGITUDE, BASIN_ID, LAND_USE_CLASS, VEG_CLASS, SOIL_PROFILE, AQUIFER_PROFILE, TERRAIN_CLASS, SLOPE, ASPECT\n')
        f.write('  :Units, km2, m, deg, deg, none, none, none, none, none, none, deg, deg\n')
        for k in range(nhru):
            xc = (k + 0.5) * hru_w
            lon, lat = ll(xs + xc, 0.0)
            f.write('  %d, %.8f, %.4f, %.6f, %.6f, 1, OPEN, GRASS, SOILP, AQ, [NONE], 0, 0\n' % (k + 1, hru_w * width / 1e6, z0 - slope * xc, lat, lon))
        f.write(':EndHRUs\n')
    # .rvi
    with open(os.path.join(d, 'm.rvi'), 'w') as f:
        f.write(':StartDate 2000-01-01 00:00:00\n:Duration %d\n:TimeStep %.10g\n:Method ORDERED_SERIES\n' % (days, timestep))
        f.write(':SoilModel SOIL_MULTILAYER 2\n:Routing ROUTE_NONE\n:CatchmentRoute ROUTE_DUMP\n:Evaporation PET_CONSTANT\n')
        f.write(':RainSnowFraction RAINSNOW_DATA\n:OroTempCorrect OROCORR_NONE\n:OroPrecipCorrect OROCORR_NONE\n')
        f.write(':HydrologicProcesses\n  :Precipitation PRECIP_RAVEN ATMOS_PRECIP MULTIPLE\n  :Infiltration INF_RATIONAL PONDED_WATER MULTIPLE\n')
        if pet > 0:
            f.write('  :SoilEvaporation SOILEVAP_ALL SOIL[0] ATMOSPHERE\n')
        f.write('  :Percolation   %s SOIL[0] SOIL[1]\n  :Percolation   %s SOIL[1] GROUNDWATER\n' % (perc_type, perc_type) + extra_proc + ':EndHydrologicProcesses\n')
        f.write(':GroundwaterModel MODFLOW6\n:WriteMassBalanceFile\n:SilentMode\n')
    # .rvp
    with open(os.path.join(d, 'm.rvp'), 'w') as f:
        f.write(':SoilClasses\n  :Attributes\n  :Units\n  SOIL\n:EndSoilClasses\n')
        f.write(':SoilProfiles\n  SOILP, 2, SOIL, %g, SOIL, %g\n:EndSoilProfiles\n' % (H0, H1))
        f.write(':VegetationClasses\n  :Attributes, MAX_HT, MAX_LAI, MAX_LEAF_COND\n  :Units, m, none, mm_per_s\n  GRASS, 1, 1, 5\n:EndVegetationClasses\n')
        f.write(':LandUseClasses\n  :Attributes, IMPERM, FOREST_COV\n  :Units, frac, frac\n  OPEN, 0, 0\n:EndLandUseClasses\n')
        xs_n = ''.join(', ' + k for k in (extra_soil or {})); xs_u = ', none' * len(extra_soil or {})
        xs_v = ''.join(', %g' % v for v in (extra_soil or {}).values())
        if soil_b is None:
            f.write(':SoilParameterList\n  :Parameters, POROSITY, FIELD_CAPACITY, SAT_WILT, HYDRAUL_COND, MAX_PERC_RATE%s\n  :Units, none, none, none, mm_per_d, mm_per_d%s\n' % (xs_n, xs_u))
            f.write('  [DEFAULT], %g, %g, 0.0, %g, %g%s\n:EndSoilParameterList\n' % (n, sfc, ksat, perc, xs_v))
        else:  # Campbell retention of the soil (capillary rise): CLAPP_B [-], AIR_ENTRY_PRESSURE [mm]
            f.write(':SoilParameterList\n  :Parameters, POROSITY, FIELD_CAPACITY, SAT_WILT, HYDRAUL_COND, MAX_PERC_RATE, CLAPP_B, AIR_ENTRY_PRESSURE\n'
                    '  :Units, none, none, none, mm_per_d, mm_per_d, none, mm\n')
            f.write('  [DEFAULT], %g, %g, 0.0, %g, %g, %g, %g\n:EndSoilParameterList\n' % (n, sfc, ksat, perc, soil_b, soil_psia))
        f.write(':LandUseParameterList\n  :Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], 0.0\n:EndLandUseParameterList\n')
        if aq_b is None:
            f.write(':AquiferClasses\n  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY\n  :Units, m/d, m/d, 1/m, none, none\n')
            f.write('  SAND, %g, %g, 1.0E-5, %g, 0.3\n:EndAquiferClasses\n' % (Kh, Kv, Sy))
        else:  # retention of the aquifer material (unsaturated columns): CLAPP_B [-], AIR_ENTRY_PRESSURE [m]
            f.write(':AquiferClasses\n  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY, CLAPP_B, AIR_ENTRY_PRESSURE\n  :Units, m/d, m/d, 1/m, none, none, none, m\n')
            f.write('  SAND, %g, %g, 1.0E-5, %g, %g, %g, %g\n:EndAquiferClasses\n' % (Kh, Kv, Sy, max(0.3, Sy + 0.05), aq_b, aq_psia))
        if aq_layers:
            f.write(':AquiferProfiles\n  AQ, %d, ' % len(aq_layers) + ', '.join('SAND, %s, %s' % (t if isinstance(t, str) else '%g' % t, ty) for t, ty in aq_layers) + '\n:EndAquiferProfiles\n')
        elif top is None:
            f.write(':AquiferProfiles\n  AQ, 1, SAND, TO_BEDROCK, AQUIFER\n:EndAquiferProfiles\n')
        else:
            f.write(':AquiferProfiles\n  AQ, 2, SAND, %g, AQUIFER, SAND, TO_BEDROCK, %s\n:EndAquiferProfiles\n' % (top, 'CONFINED_AQUIFER' if aq_conf else 'AQUIFER'))
        f.write(':AquiferProfileParameters\n  :Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH\n')
        f.write('  :Units, m, m, 1/d, m\n  AQ, %g, %g, 1.0, %g\n:EndAquiferProfileParameters\n' % (init_depth, aq_thick + H0 + H1, smooth))
    # .rvt
    rains = rain if isinstance(rain, (list, tuple)) else [rain] * days
    with open(os.path.join(d, 'm.rvt'), 'w') as f:
        lon, lat = ll(0.0, 0.0)
        f.write(':Gauge G\n  :Latitude %.6f\n  :Longitude %.6f\n  :Elevation %g\n' % (lat, lon, z0))
        f.write('  :Data RAINFALL mm/d\n    2000-01-01 00:00:00 1.0 %d\n' % days + ''.join('    %g\n' % r for r in rains) + '  :EndData\n')
        f.write('  :Data SNOWFALL mm/d\n    2000-01-01 00:00:00 1.0 %d\n' % days + '    0\n' * days + '  :EndData\n')
        f.write('  :Data TEMP_AVE C\n    2000-01-01 00:00:00 1.0 %d\n' % days + '    10\n' * days + '  :EndData\n')
        if pet > 0:
            f.write('  :Data PET mm/d\n    2000-01-01 00:00:00 1.0 %d\n' % days + ('    %g\n' % pet) * days + '  :EndData\n')
        f.write(':EndGauge\n')
    # .rvc: soil at field capacity unless given
    cap0, cap1 = H0 * 1000 * n, H1 * 1000 * n
    p0 = phi0 if phi0 is not None else (cap0 * sfc, cap1 * sfc)
    with open(os.path.join(d, 'm.rvc'), 'w') as f:
        f.write(':UniformInitialConditions SOIL[0] %g\n:UniformInitialConditions SOIL[1] %g\n' % p0)
    # .rvg
    with open(os.path.join(d, 'm.rvg'), 'w') as f:
        f.write(':HRUGeometry hru.geojson HRU_ID\n:LandSurface dem.asc\n:GridCellSize %g\n:MinCellCoverage 0.25\n:SolverHeadTolerance 0.000001\n' % cell)
        if physical:
            f.write(':SoilZone PHYSICAL SOIL[0] SOIL[1]\n:SoilZoneSubgrid %d\n' % subgrid)
        if iteration:
            f.write(':SoilZoneIteration %d %g %g\n' % iteration)
        if steady is not None:
            f.write(':GWInitialization STEADY_STATE %g\n' % steady)
        if chd is not None:  # fixed head along the downslope edge: polygon over the last cell column (its edge a quarter
            x0 = xs + L - 0.75 * cell  # cell inside the column: an edge on the cell centres selected no cell)
            ring = [ll(x0, ys - width), ll(xs + L + width, ys - width), ll(xs + L + width, ys + 2 * width), ll(x0, ys + 2 * width), ll(x0, ys - width)]
            json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": 1}, "geometry": {"type": "Polygon", "coordinates": [ring]}}]},
                      open(os.path.join(d, 'edge.geojson'), 'w'))
            f.write(':SpecifiedHeadBoundary EDGE edge.geojson HEAD %g\n' % chd)
        f.write(extra_rvg)
    return d
