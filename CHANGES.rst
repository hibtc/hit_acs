CHANGELOG
~~~~~~~~~

0.7.0
-----
Date: 25.03.2018

- update madgui plugin to new unit handling in madgui
- compatible with madgui 1.8.0, hit_models 0.8.0

0.6.0
-----
Date: 02.03.2018

- fix knob access for skew quadrupoles
- compatible with madgui 1.7.1, hit_models 0.7.0

0.5.0
-----
Date: 26.01.2018

- update to madqt 0.0.6: unification of workspace/segment -> model

0.4.0
-----
Date: 24.01.2018

- 64bit support
- add win32 and qt standalone modes
- port to madqt
- initialize strengths/monitors from current model instead of using the
  example values in the parameter list (which would often lead to crashes)
- renamed package
- finally implement SetNewValueCallback (untested)
- massive simplification of the madqt interface (knobs API)
- can query beam parameters
- ship DVM parameter list with the package itself
- always load DVM parameters from CSV (no more YAML)
- can guess correct parameter names more reliably, based on several clues
