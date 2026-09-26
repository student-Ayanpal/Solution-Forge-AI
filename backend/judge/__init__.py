"""
backend/judge/__init__.py

The Judge is the fifth and last step of the consultation pipeline. It runs
after the four agents and before the blueprint is finalised.

Module map
----------
rubric.py       criteria, weights, quality bands, severity penalties
constraints.py  deterministic hard-constraint checks (pure Python)
scoring.py      weighted scoring + penalty application (pure Python)
judge.py        combines all of the above into the single judge_output dict
"""
