# Phase-1a mock harness. Run from the aira-dojo repo root:  make -C phase1 smoke
PY ?= python

.PHONY: smoke test quick clean
smoke:          ## full mock sweep -> CSV + summary table + sample-efficiency PNGs
	cd .. && $(PY) -m phase1.smoke

quick:          ## tiny sweep (seconds)
	cd .. && $(PY) -m phase1.smoke --quick

test:           ## pytest acceptance gate
	cd .. && $(PY) -m pytest phase1/tests -q

clean:
	rm -rf _smoke_out **/__pycache__ .pytest_cache
