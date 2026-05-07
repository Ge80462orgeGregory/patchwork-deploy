"""Tests for patchwork.metricscollector."""
import pytest
from patchwork.metricscollector import MetricSample, MetricsCollector, MetricsError


@pytest.fixture
def collector() -> MetricsCollector:
    return MetricsCollector()


class TestMetricSample:
    def test_to_dict_contains_required_keys(self):
        s = MetricSample(name="deploys", value=3.0, labels={"env": "prod"})
        d = s.to_dict()
        assert d["name"] == "deploys"
        assert d["value"] == 3.0
        assert d["labels"] == {"env": "prod"}
        assert "timestamp" in d

    def test_repr_contains_name_and_value(self):
        s = MetricSample(name="errors", value=1.0, labels={"svc": "api"})
        r = repr(s)
        assert "errors" in r
        assert "1.0" in r


class TestMetricsCollector:
    def test_record_stores_sample(self, collector):
        collector.record("deploy.ok", 1.0)
        assert len(collector) == 1

    def test_increment_adds_value(self, collector):
        collector.increment("deploy.ok")
        collector.increment("deploy.ok")
        assert collector.total("deploy.ok") == 2.0

    def test_increment_by_custom_amount(self, collector):
        collector.increment("bytes", by=512.0)
        assert collector.total("bytes") == 512.0

    def test_by_name_filters_correctly(self, collector):
        collector.record("a", 1.0)
        collector.record("b", 2.0)
        collector.record("a", 3.0)
        results = collector.by_name("a")
        assert len(results) == 2
        assert all(s.name == "a" for s in results)

    def test_total_sums_values(self, collector):
        collector.record("latency", 100.0)
        collector.record("latency", 200.0)
        assert collector.total("latency") == 300.0

    def test_total_unknown_metric_is_zero(self, collector):
        assert collector.total("nonexistent") == 0.0

    def test_summary_returns_all_totals(self, collector):
        collector.record("ok", 3.0)
        collector.record("fail", 1.0)
        s = collector.summary()
        assert s["ok"] == 3.0
        assert s["fail"] == 1.0

    def test_clear_removes_all_samples(self, collector):
        collector.record("x", 1.0)
        collector.clear()
        assert len(collector) == 0

    def test_empty_name_raises(self, collector):
        with pytest.raises(MetricsError):
            collector.record("", 1.0)

    def test_negative_value_raises(self, collector):
        """Recording a negative metric value should raise MetricsError."""
        with pytest.raises(MetricsError):
            collector.record("deploy.ok", -1.0)

    def test_labels_stored_on_sample(self, collector):
        collector.record("deploy", 1.0, labels={"env": "staging", "svc": "web"})
        sample = collector.by_name("deploy")[0]
        assert sample.labels["env"] == "staging"

    def test_all_samples_returns_copy(self, collector):
        collector.record("a", 1.0)
        samples = collector.all_samples()
        samples.clear()
        assert len(collector) == 1
