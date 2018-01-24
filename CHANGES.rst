CHANGELOG
~~~~~~~~~

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
