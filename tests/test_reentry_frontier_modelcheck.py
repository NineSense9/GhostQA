"""Bounded lifecycle model for v0.3.16."""
from benchmark.reentry_frontier_modelcheck import RAW_TRACE_COUNT, enumerate_traces


def test_reentry_frontier_model_has_no_invariant_failures():
    report = enumerate_traces()
    assert report["raw_traces"] == RAW_TRACE_COUNT == 37448
    assert report["invariant_failures"] == 0
    assert report["valid_traces"] > 0
