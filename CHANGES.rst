CHANGELOG
~~~~~~~~~

0.9.0
-----
Date: 31.05.2018

- fully simplify knobs to being only var names, all conversions are now done
  by using appropriate expressions in the model!!

0.8.0
-----
Date: 16.04.2018

- adapt to changes in madgui ``1.9.0`` API
- simplify ``get_knob`` logic significantly
- remove support for inserted kickers into SBENDs (now modelled as ``K0 !=
  ANGLE/L``)
- fix an error in stub with 32bit
- flip monitor X position to convert from HIT to MAD-X coordinate system (HIT
  uses a left-handed system in HEBT!)
- discard ``-9999`` records from monitors
- remove setuptools entrypoint for madgui, must now be loaded manually using
  the ``onload`` handler
- expose ``dll`` variable to user shell
- read and add offsets to MWPC measurements

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
