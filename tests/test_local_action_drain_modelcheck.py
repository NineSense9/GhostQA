"""Bounded lifecycle model for v0.3.17 local action drain."""
from benchmark.local_action_drain_modelcheck import RAW_TRACE_COUNT, enumerate_traces


def test_local_action_model_covers_every_short_trace_without_invariant_failures():
    report = enumerate_traces()
    assert RAW_TRACE_COUNT == 66429
    assert report["raw_traces"] == 66429
    assert report["valid_traces"] + report["rejected_traces"] == 66429
    assert report["invariant_failures"] == 0
    assert report["rejected_traces"] > 0
    assert report["valid_traces"] > 0
