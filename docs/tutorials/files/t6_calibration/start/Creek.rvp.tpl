# Creek.rvp - Tutorial Creek: parameters
:AvgAnnualRunoff 450.0
:GlobalParameter RAINSNOW_TEMP 0.0

:SoilClasses
  :Attributes
  :Units
  TOPSOIL
  SUBSOIL
  DEEP
:EndSoilClasses

:SoilProfiles
  # name,       #horizons, {class, thickness [m]} x #horizons
  LAKE,         0
  VALLEY_SOIL,  3, TOPSOIL, 0.3, SUBSOIL, 1.0, DEEP, 5.0
  SLOPE_SOIL,   3, TOPSOIL, 0.3, SUBSOIL, 0.7, DEEP, 5.0
  ROCK_SOIL,    3, TOPSOIL, 0.1, SUBSOIL, 0.2, DEEP, 5.0
  WETLAND_SOIL, 3, TOPSOIL, 0.3, SUBSOIL, 1.0, DEEP, 5.0
:EndSoilProfiles

:SoilParameterList
  :Parameters, POROSITY, FIELD_CAPACITY, SAT_WILT, HBV_BETA, MAX_PERC_RATE, PERC_COEFF, BASEFLOW_COEFF
  :Units,      none,     none,           none,     none,     mm/d,          1/d,        1/d
  TOPSOIL,     0.45,     0.30,           0.10,     2.0,      20.0,          0.0,        0.0
  SUBSOIL,     0.40,     0.25,           0.10,     2.0,      0.0,           0.04,       0.01
  DEEP,        0.30,     0.05,           0.0,      1.0,      0.0,           0.0,        0.005
:EndSoilParameterList

:VegetationClasses
  :Attributes, MAX_HT, MAX_LAI, MAX_LEAF_COND
  :Units,      m,      none,    mm_per_s
  GRASS,       0.5,    2.0,     5.0
  FOREST,      20.0,   5.0,     5.0
  BARE,        0.0,    0.0,     0.0
:EndVegetationClasses

:VegetationParameterList
  :Parameters, RAIN_ICEPT_PCT, SNOW_ICEPT_PCT
  :Units,      none,           none
  [DEFAULT],   0.0,            0.0
:EndVegetationParameterList

:LandUseClasses
  :Attributes, IMPERM, FOREST_COV
  :Units,      frac,   frac
  OPEN,        0.0,    0.0
  FOREST,      0.0,    1.0
  ROCK,        0.3,    0.0
  WATER,       0.0,    0.0
  WETLAND,     0.0,    0.0
:EndLandUseClasses

:LandUseParameterList
  :Parameters, DEP_THRESHOLD, DEP_N, DEP_MAX_FLOW, DEP_MAX, DEP_SEEP_K, OW_PET_CORR, LAKE_PET_CORR
  :Units,      mm,            none,  mm/d,         mm,      1/d,        none,        none
  [DEFAULT],   100.0,         1.0,   20.0,         300.0,   0.01,       1.0,         1.0
:EndLandUseParameterList

:ChannelProfile CREEK_CHANNEL
  :Bedslope 0.005
  :SurveyPoints
    0.0  4.0
    8.0  1.5
    10.0 0.0
    16.0 0.0
    18.0 1.5
    26.0 4.0
  :EndSurveyPoints
  :RoughnessZones
    0.0 0.04
  :EndRoughnessZones
:EndChannelProfile

# --- groundwater (Raven-MODFLOW 6) ---------------------------------------------
:AquiferClasses
  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY
  :Units,      m/d,     m/d,    1/m,          none,       none
  GRAVEL,      40.0,    4.0,    1.0E-5,       0.20,       0.30
  SAND,        par_K_sand,     0.8,    1.0E-5,       0.15,       0.32
  TILL,        par_K_till,     0.2,    1.0E-4,       0.08,       0.30
:EndAquiferClasses

:AquiferProfiles
  # name,      #layers, {class, thickness [m] or TO_BEDROCK, layer type} x #layers
  VALLEY_FILL, 2, GRAVEL, 12.0, AQUIFER, SAND, TO_BEDROCK, AQUIFER
  SLOPE_TILL,  2, TILL,   4.0,  AQUIFER, TILL, TO_BEDROCK, AQUIFER
:EndAquiferProfiles

:AquiferProfileParameters
  :Attributes, INITIAL_HEAD_DEPTH, SEEPAGE_LEAKANCE
  :Units,      m,                  1/d
  VALLEY_FILL, 2.0,                1.0
  SLOPE_TILL,  5.0,                1.0
:EndAquiferProfileParameters
