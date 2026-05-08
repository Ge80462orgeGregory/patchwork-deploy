"""Tests for patchwork.trafficshaper."""
import pytest

from patchwork.trafficshaper import (
    TrafficShaperError,
    TrafficWeight,
    TrafficRule,
    TrafficShaper,
)


# ---------------------------------------------------------------------------
# TrafficWeight
# ---------------------------------------------------------------------------

class TestTrafficWeight:
    def test_to_dict_contains_all_keys(self):
        w = TrafficWeight(version="v1", weight=60)
        d = w.to_dict()
        assert d["version"] == "v1"
        assert d["weight"] == 60

    def test_round_trip(self):
        w = TrafficWeight(version="v2", weight=40)
        assert TrafficWeight.from_dict(w.to_dict()) == w

    def test_repr_contains_version(self):
        w = TrafficWeight(version="v1", weight=100)
        assert "v1" in repr(w)


# ---------------------------------------------------------------------------
# TrafficRule
# ---------------------------------------------------------------------------

def _weights(pairs):
    return [TrafficWeight(version=v, weight=w) for v, w in pairs]


class TestTrafficRule:
    def test_valid_rule_created(self):
        rule = TrafficRule("svc", _weights([("v1", 70), ("v2", 30)]))
        assert rule.service == "svc"
        assert len(rule.weights) == 2

    def test_empty_weights_allowed(self):
        rule = TrafficRule("svc")
        assert rule.weights == []

    def test_weights_not_summing_to_100_raises(self):
        with pytest.raises(TrafficShaperError, match="sum to 100"):
            TrafficRule("svc", _weights([("v1", 50), ("v2", 40)]))

    def test_negative_weight_raises(self):
        with pytest.raises(TrafficShaperError, match=">= 0"):
            TrafficRule("svc", _weights([("v1", -10), ("v2", 110)]))

    def test_empty_service_raises(self):
        with pytest.raises(TrafficShaperError, match="empty"):
            TrafficRule("")

    def test_to_dict_structure(self):
        rule = TrafficRule("api", _weights([("v1", 100)]))
        d = rule.to_dict()
        assert d["service"] == "api"
        assert len(d["weights"]) == 1

    def test_round_trip(self):
        rule = TrafficRule("api", _weights([("v1", 60), ("v2", 40)]))
        restored = TrafficRule.from_dict(rule.to_dict())
        assert restored.service == rule.service
        assert len(restored.weights) == 2

    def test_repr_contains_service(self):
        rule = TrafficRule("my-svc", _weights([("v1", 100)]))
        assert "my-svc" in repr(rule)


# ---------------------------------------------------------------------------
# TrafficShaper
# ---------------------------------------------------------------------------

@pytest.fixture()
def shaper():
    return TrafficShaper()


class TestTrafficShaper:
    def test_initially_empty(self, shaper):
        assert len(shaper) == 0

    def test_add_and_get_rule(self, shaper):
        rule = TrafficRule("svc", _weights([("v1", 100)]))
        shaper.add_rule(rule)
        assert shaper.get("svc") is rule

    def test_len_increments(self, shaper):
        shaper.add_rule(TrafficRule("a", _weights([("v1", 100)])))
        shaper.add_rule(TrafficRule("b", _weights([("v1", 100)])))
        assert len(shaper) == 2

    def test_get_missing_returns_none(self, shaper):
        assert shaper.get("nonexistent") is None

    def test_remove_existing_returns_true(self, shaper):
        shaper.add_rule(TrafficRule("svc", _weights([("v1", 100)])))
        assert shaper.remove("svc") is True
        assert len(shaper) == 0

    def test_remove_missing_returns_false(self, shaper):
        assert shaper.remove("ghost") is False

    def test_all_rules_returns_list(self, shaper):
        shaper.add_rule(TrafficRule("x", _weights([("v1", 100)])))
        shaper.add_rule(TrafficRule("y", _weights([("v1", 100)])))
        assert len(shaper.all_rules()) == 2

    def test_to_dict_keyed_by_service(self, shaper):
        shaper.add_rule(TrafficRule("api", _weights([("v1", 100)])))
        d = shaper.to_dict()
        assert "api" in d
        assert d["api"]["service"] == "api"

    def test_add_rule_overwrites_existing(self, shaper):
        shaper.add_rule(TrafficRule("svc", _weights([("v1", 100)])))
        shaper.add_rule(TrafficRule("svc", _weights([("v2", 100)])))
        assert shaper.get("svc").weights[0].version == "v2"
        assert len(shaper) == 1
