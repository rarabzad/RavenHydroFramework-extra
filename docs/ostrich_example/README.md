# Calibrating the Raven-MODFLOW 6 coupling with Ostrich

`ostIn.txt` calibrates gravel K, gravel Sy and upland-till K against monitoring-well heads (GW_HEAD in
Raven's Diagnostics.csv) with DDS. `Liard.rvp.tpl` is the .rvp with parameter tokens in :AquiferClasses.
The responses read Diagnostics.csv as Ostrich counts: lines from 0 (the header is line 0), columns from 1. With
`:EvaluationMetrics NASH_SUTCLIFFE RMSE KLING_GUPTA` the RMSE is column 4 (observed_data_series, filename,
DIAG_NASH_SUTCLIFFE, DIAG_RMSE, DIAG_KLING_GUPTA), and the four GW_HEAD series are lines 1-4 when they are the model's
only observations. Other metrics or other observations move them: check the line and column of each response against
your own Diagnostics.csv before running.

Not run with the Ostrich executable here. The same search (identical templates, objective and bounds) was run with a
Python DDS driver on the synthetic subbasin-52 test; the results are in the manual, chapter "Applying the coupling",
section "A synthetic test".
