"""
Tests for config_store.py — Runtime tunable threshold system.

Uses mocked Redis client to avoid real Redis dependency.
Each test patches get_redis_client to return a controlled mock.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from backend.core.config_store import (
    DEFAULTS,
    CATEGORY_GROUPS,
    LIVE_EFFECTIVE,
    get_config,
    set_config,
    reset_config,
)

# Audit-verified constant count — must match NUMERICAL_AUDIT.md
EXPECTED_DEFAULTS_COUNT = 59


@pytest.fixture
def mock_redis():
    """Return a mock Upstash Redis client backed by an in-memory dict.

    The ``store`` dict simulates Redis persistence so ``set`` followed
    by ``get`` returns the updated data — just like real Redis.
    """
    store: dict = {}

    async def fake_get(key: str) -> str | None:
        return json.dumps(store.get(key)) if key in store else None

    async def fake_set(key: str, value: str, ttl: int | None = None) -> None:
        store[key] = json.loads(value)

    async def fake_delete(key: str) -> None:
        store.pop(key, None)

    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=fake_get)
    redis.set = AsyncMock(side_effect=fake_set)
    redis.delete = AsyncMock(side_effect=fake_delete)
    return redis


class TestDefaultsCount:
    """Confirm the DEFAULTS dict matches the audit."""

    def test_defaults_count(self):
        """DEFAULTS must contain exactly EXPECTED_DEFAULTS_COUNT keys."""
        assert len(DEFAULTS) == EXPECTED_DEFAULTS_COUNT, (
            f"DEFAULTS has {len(DEFAULTS)} keys, expected {EXPECTED_DEFAULTS_COUNT}. "
            "Update NUMERICAL_AUDIT.md count or DEFAULTS dict."
        )


class TestCategoryGroups:
    """Verify category_groups metadata is complete and consistent."""

    def test_category_groups_covers_all_defaults(self):
        """Every DEFAULTS key must appear in exactly one category group."""
        all_grouped = set()
        for cat, keys in CATEGORY_GROUPS.items():
            all_grouped.update(keys)
        assert all_grouped == set(DEFAULTS.keys()), (
            "Category groups do not cover all DEFAULTS keys. "
            f"Missing: {set(DEFAULTS.keys()) - all_grouped}. "
            f"Extra: {all_grouped - set(DEFAULTS.keys())}."
        )

    def test_no_overlap_between_categories(self):
        """No DEFAULTS key appears in more than one category group."""
        seen: dict[str, str] = {}
        for cat, keys in CATEGORY_GROUPS.items():
            for k in keys:
                assert k not in seen, (
                    f"Key '{k}' appears in both '{seen[k]}' and '{cat}'"
                )
                seen[k] = cat


class TestLiveEffective:
    """Verify LIVE_EFFECTIVE set is correct."""

    def test_live_effective_subset_of_defaults(self):
        """Every LIVE_EFFECTIVE key must exist in DEFAULTS."""
        for k in LIVE_EFFECTIVE:
            assert k in DEFAULTS, f"LIVE_EFFECTIVE key '{k}' not in DEFAULTS"

    def test_live_effective_excludes_non_detection_categories(self):
        """Excluded categories: ALERTS, STORAGE_DB, ACCOUNT_QUOTA, CACHING,
        RETENTION, RTSP_CAMERA_CLIENT, AI_CLIENT."""
        excluded_cats = [
            "ALERTS", "STORAGE_DB", "ACCOUNT_QUOTA",
            "CACHING", "RETENTION", "RTSP_CAMERA_CLIENT", "AI_CLIENT",
        ]
        excluded_keys: set[str] = set()
        for cat in excluded_cats:
            excluded_keys.update(CATEGORY_GROUPS.get(cat, []))
        for k in excluded_keys:
            # Determine which category this key came from
            source_cat = next(
                (c for c in excluded_cats if k in CATEGORY_GROUPS.get(c, [])),
                "unknown",
            )
            assert k not in LIVE_EFFECTIVE, (
                f"LIVE_EFFECTIVE should not contain '{k}' (category {source_cat})"
            )

    def test_live_effective_size(self):
        """LIVE_EFFECTIVE = DETECTION(4) + MOTION(5) + FRAME_QUALITY_GATES(5)
        + TRACKING(3) + INCIDENTS_GEMINI(6) + RE_ID(6) + GHOST_REPEAT(6) = 35"""
        expected = sum(len(CATEGORY_GROUPS[cat]) for cat in [
            "DETECTION", "MOTION", "FRAME_QUALITY_GATES",
            "TRACKING", "INCIDENTS_GEMINI", "RE_ID", "GHOST_REPEAT",
        ])
        assert len(LIVE_EFFECTIVE) == expected, (
            f"LIVE_EFFECTIVE has {len(LIVE_EFFECTIVE)} keys, expected {expected}"
        )


@pytest.mark.asyncio
async def test_get_config_returns_defaults_when_redis_empty(mock_redis):
    """When Redis has no stored config, get_config returns all defaults."""
    with patch("backend.core.config_store.get_redis_client",
               return_value=mock_redis):
        result = await get_config()

    assert result["values"] == DEFAULTS
    assert result["defaults"] == DEFAULTS
    assert result["modified_keys"] == []
    assert len(result["values"]) == EXPECTED_DEFAULTS_COUNT
    assert len(result["defaults"]) == EXPECTED_DEFAULTS_COUNT
    # category_groups present
    assert "category_groups" in result
    assert result["category_groups"] == {
        cat: list(keys) for cat, keys in CATEGORY_GROUPS.items()
    }
    # live_effective present
    assert "live_effective" in result
    assert set(result["live_effective"]) == LIVE_EFFECTIVE
    assert isinstance(result["live_effective"], list)


@pytest.mark.asyncio
async def test_get_config_merges_stored_with_defaults(mock_redis):
    """Partial stored config merges over defaults, preserving other keys."""
    # Pre-populate Redis store via the mock's side effect
    await mock_redis.set("visionos:tunable_config",
                         json.dumps({"yolo_confidence_threshold": 0.50}))

    with patch("backend.core.config_store.get_redis_client",
               return_value=mock_redis):
        result = await get_config()

    assert result["values"]["yolo_confidence_threshold"] == 0.50
    # Other keys untouched
    assert result["values"]["motion_min_area"] == DEFAULTS["motion_min_area"]
    assert "yolo_confidence_threshold" in result["modified_keys"]
    assert len(result["modified_keys"]) == 1
    # Full key count preserved
    assert len(result["values"]) == EXPECTED_DEFAULTS_COUNT


@pytest.mark.asyncio
async def test_get_config_handles_corrupted_json(mock_redis):
    """Corrupted JSON in Redis falls back to full defaults."""
    with patch.object(mock_redis, 'get',
                      AsyncMock(return_value="not-json{{{")):
        with patch("backend.core.config_store.get_redis_client",
                   return_value=mock_redis):
            result = await get_config()

    assert result["values"] == DEFAULTS
    assert result["modified_keys"] == []


@pytest.mark.asyncio
async def test_set_config_updates_and_persists(mock_redis):
    """set_config merges updates, writes to Redis, returns new envelope."""
    with patch("backend.core.config_store.get_redis_client",
               return_value=mock_redis):
        result = await set_config({"yolo_confidence_threshold": 0.80})

    # Verify Redis.set was called with the config key
    mock_redis.set.assert_awaited()
    call_args = mock_redis.set.call_args[0]
    assert call_args[0] == "visionos:tunable_config"
    written = json.loads(call_args[1])
    assert written["yolo_confidence_threshold"] == 0.80

    # Return envelope shows the updated value
    assert result["values"]["yolo_confidence_threshold"] == 0.80
    assert "yolo_confidence_threshold" in result["modified_keys"]


@pytest.mark.asyncio
async def test_reset_config_deletes_key_returns_defaults(mock_redis):
    """reset_config deletes Redis key and returns default envelope."""
    # Pre-populate
    await mock_redis.set("visionos:tunable_config",
                         json.dumps({"yolo_confidence_threshold": 0.99}))

    with patch("backend.core.config_store.get_redis_client",
               return_value=mock_redis):
        result = await reset_config()

    # Redis.delete was called
    mock_redis.delete.assert_awaited_once_with("visionos:tunable_config")
    # Return is all defaults, no modified keys
    assert result["values"] == DEFAULTS
    assert result["modified_keys"] == []


@pytest.mark.asyncio
async def test_set_config_then_get_config_round_trip(mock_redis):
    """Simulate a full save-then-read cycle via the in-memory store."""
    with patch("backend.core.config_store.get_redis_client",
               return_value=mock_redis):
        # Initial: empty — all defaults
        result1 = await get_config()
        assert result1["values"] == DEFAULTS
        assert result1["modified_keys"] == []

        # Save one key
        result2 = await set_config({"track_match_iou": 0.50})
        assert result2["values"]["track_match_iou"] == 0.50
        assert "track_match_iou" in result2["modified_keys"]

        # Re-read verifies persistence via the in-memory store
        result3 = await get_config()
        assert result3["values"]["track_match_iou"] == 0.50

        # Reset
        result4 = await reset_config()
        assert result4["values"] == DEFAULTS

        # Confirm reset stuck
        result5 = await get_config()
        assert result5["values"] == DEFAULTS
        assert result5["modified_keys"] == []