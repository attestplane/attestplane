# Issue 175 Validation Evidence

Plan ID: `e1a00e102aecf1fc`

## Required Commands

```text
$ PYTHONPATH=sdk/python/src pytest tests/canonicalization -k property
collected 73 items
tests/canonicalization/test_canonicalization_properties.py ............. [ 17%]
............................................................             [100%]
73 passed in 0.12s
```

```text
$ PYTHONPATH=sdk/python/src pytest tests/verifier -k round_trip
collected 23 items / 18 deselected / 5 selected
tests/verifier/test_signed_schema_roundtrip.py .....                     [100%]
5 passed, 18 deselected in 0.05s
```

## Focused Supporting Checks

```text
$ PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -q
8 passed in 0.05s
```

```text
$ PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -q
14 passed in 0.06s
```

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_canonical.py -q
19 passed in 0.03s
```

## Blocked / Environment-Limited Checks

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_canonical.py sdk/python/tests/test_properties.py -q
ERROR sdk/python/tests/test_properties.py
ModuleNotFoundError: No module named 'hypothesis'
```

`sdk/python/tests/test_properties.py` was pre-existing and imports Hypothesis at collection time. The new Issue 175 tests avoid that dependency and pass under the local runner environment.

```text
$ run_gate attestplane
[run_gate] project dir not found: /Users/macworkers/attestplane
```

The generic local gate helper does not recognize this checkout path as `attestplane`; focused issue validation commands above were run instead.
