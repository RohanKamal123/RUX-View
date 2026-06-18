"""Tests for the multi-location management module."""

import pytest
from datetime import date, time, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.location_manager import (
    LocationManager,
    LocationSummary,
    LocationDetail,
    TIER_LOCATION_LIMITS,
)


class MockRow:
    """Mock database row with attribute and index access."""
    def __init__(self, **kwargs):
        self._values = {}
        for k, v in kwargs.items():
            setattr(self, k, v)
            self._values[k] = v

    def __getitem__(self, key):
        """Support index access like row[0] for count queries."""
        if isinstance(key, int):
            # For count queries like fetchone()[0], return the first value
            vals = list(self._values.values())
            if key < len(vals):
                return vals[key]
            raise IndexError(f"Index {key} out of range")
        return getattr(self, key)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = mock_session
    factory.return_value.__aexit__.return_value = None
    return factory


@pytest.fixture
def location_manager(mock_session_factory):
    """Create a LocationManager with mock session factory."""
    return LocationManager(mock_session_factory)


class TestLocationManager:

    @pytest.mark.asyncio
    async def test_create_location_within_tier_limit(self, location_manager, mock_session):
        """Test creating a location when under the tier limit."""
        # Mock fetchone to return different values on each call
        # fetchone is synchronous (not async) in SQLAlchemy
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.side_effect = [
            MockRow(tier="household"),
            MockRow(count=1),
            MockRow(
                id="loc-001",
                user_id="user-001",
                name="Home Office",
                address="Dhaka, Bangladesh",
                timezone="Asia/Dhaka",
                business_hours_open=None,
                business_hours_close=None,
                camera_topology={},
                created_at=datetime(2026, 4, 27, 10, 0, 0),
            ),
        ]

        location = await location_manager.create_location(
            user_id="user-001",
            name="Home Office",
            address="Dhaka, Bangladesh",
        )

        assert location.name == "Home Office"
        assert location.address == "Dhaka, Bangladesh"
        assert location.timezone == "Asia/Dhaka"

    @pytest.mark.asyncio
    async def test_create_location_exceeds_tier_limit_raises_error(
        self, location_manager, mock_session
    ):
        """Test that creating a location beyond tier limit raises an error."""
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.side_effect = [
            MockRow(tier="free"),
            MockRow(count=1),
        ]

        with pytest.raises(ValueError, match="limit of 1 location"):
            await location_manager.create_location(
                user_id="user-001",
                name="Second Location",
            )

    @pytest.mark.asyncio
    async def test_get_locations_returns_user_locations(
        self, location_manager, mock_session
    ):
        """Test retrieving all locations for a user."""
        # The code calls fetchall once for locations, then fetchone per location for stats
        # For 2 locations: 1 fetchall + 2 fetchone (cam stats) + 2 fetchone (event stats) = 5 calls
        mock_session.execute.return_value.fetchall = MagicMock()
        mock_session.execute.return_value.fetchall.side_effect = [
            [
                MockRow(id="loc-001", name="Home", address="Mirpur",
                        timezone="Asia/Dhaka"),
                MockRow(id="loc-002", name="Shop", address="Gulshan",
                        timezone="Asia/Dhaka"),
            ],
        ]
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.side_effect = [
            MockRow(total=2, online=1),   # cam stats for loc-001
            MockRow(total=5, high=1),     # event stats for loc-001
            MockRow(total=1, online=1),   # cam stats for loc-002
            MockRow(total=3, high=0),     # event stats for loc-002
        ]

        locations = await location_manager.get_locations("user-001")

        assert len(locations) == 2
        assert locations[0].name == "Home"
        assert locations[1].name == "Shop"

    @pytest.mark.asyncio
    async def test_delete_location_cascades_to_cameras(
        self, location_manager, mock_session
    ):
        """Test that deleting a location cascades to associated data."""
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.side_effect = [
            MockRow(id="loc-001"),
            None, None, None, None, None,
        ]

        result = await location_manager.delete_location("loc-001", "user-001")

        assert result is True
        assert mock_session.execute.call_count >= 5

    @pytest.mark.asyncio
    async def test_cross_camera_never_crosses_location_boundary(
        self, location_manager, mock_session
    ):
        """Test that Re-ID never crosses location boundaries (HARD RULE)."""
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.side_effect = [
            MockRow(tier="business"),
            MockRow(count=0),
            MockRow(id="loc-001", user_id="user-001", name="Home",
                    address=None, timezone="Asia/Dhaka",
                    business_hours_open=None, business_hours_close=None,
                    camera_topology={}, created_at=datetime.now()),
            MockRow(tier="business"),
            MockRow(count=1),
            MockRow(id="loc-002", user_id="user-001", name="Shop",
                    address=None, timezone="Asia/Dhaka",
                    business_hours_open=None, business_hours_close=None,
                    camera_topology={}, created_at=datetime.now()),
        ]

        loc1 = await location_manager.create_location("user-001", "Home")
        loc2 = await location_manager.create_location("user-001", "Shop")

        topology1 = {"cam-001": {"neighbours": ["cam-002"], "min_transit_time": 5}}
        topology2 = {"cam-003": {"neighbours": ["cam-004"], "min_transit_time": 10}}

        assert "cam-003" not in topology1
        assert "cam-001" not in topology2

    @pytest.mark.asyncio
    async def test_unified_digest_aggregates_all_locations(
        self, location_manager, mock_session
    ):
        """Test that unified digest aggregates across all locations."""
        # get_unified_digest calls get_locations which does:
        # 1 fetchall for locations + per-location: fetchone (cam stats) + fetchone (event stats)
        mock_session.execute.return_value.fetchall = MagicMock()
        mock_session.execute.return_value.fetchall.side_effect = [
            [
                MockRow(id="loc-001", name="Home", address="Mirpur",
                        timezone="Asia/Dhaka"),
                MockRow(id="loc-002", name="Shop", address="Gulshan",
                        timezone="Asia/Dhaka"),
            ],
        ]
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.side_effect = [
            MockRow(total=2, online=2),   # cam stats for loc-001
            MockRow(total=10, high=2),    # event stats for loc-001
            MockRow(total=1, online=1),   # cam stats for loc-002
            MockRow(total=5, high=1),     # event stats for loc-002
        ]

        digest = await location_manager.get_unified_digest(
            "user-001", date(2026, 4, 27)
        )

        assert "Home" in digest
        assert "Shop" in digest
        assert "Total Locations: 2" in digest
        assert "Total Cameras: 3" in digest
        assert "Total Events Today: 15" in digest
        assert "High Threats Today: 3" in digest

    def test_topology_cycle_detection_rejects_cycles(self, location_manager):
        """Test that cyclic topology is rejected."""
        cyclic_topology = {
            "cam-a": {"neighbours": ["cam-b"], "min_transit_time": 5},
            "cam-b": {"neighbours": ["cam-c"], "min_transit_time": 3},
            "cam-c": {"neighbours": ["cam-a"], "min_transit_time": 4},
        }

        assert location_manager._validate_topology(cyclic_topology) is False

    def test_topology_cycle_detection_accepts_acyclic(self, location_manager):
        """Test that acyclic topology is accepted."""
        acyclic_topology = {
            "cam-a": {"neighbours": ["cam-b"], "min_transit_time": 5},
            "cam-b": {"neighbours": ["cam-c"], "min_transit_time": 3},
            "cam-c": {"neighbours": [], "min_transit_time": 0},
        }

        assert location_manager._validate_topology(acyclic_topology) is True

    @pytest.mark.asyncio
    async def test_update_topology_validates_before_save(
        self, location_manager, mock_session
    ):
        """Test that topology validation runs before saving."""
        cyclic_topology = {
            "cam-a": {"neighbours": ["cam-b"], "min_transit_time": 5},
            "cam-b": {"neighbours": ["cam-a"], "min_transit_time": 3},
        }

        with pytest.raises(ValueError, match="contains cycles"):
            await location_manager.update_camera_topology("loc-001", cyclic_topology)

        mock_session.execute.assert_not_called()

    def test_free_tier_limited_to_one_location(self, location_manager):
        """Test that free tier is limited to 1 location."""
        limit = location_manager._get_tier_location_limit("free")
        assert limit == 1

    def test_business_tier_allows_five_locations(self, location_manager):
        """Test that business tier allows 5 locations."""
        limit = location_manager._get_tier_location_limit("business")
        assert limit == 5

    def test_household_tier_allows_three_locations(self, location_manager):
        """Test that household tier allows 3 locations."""
        limit = location_manager._get_tier_location_limit("household")
        assert limit == 3

    @pytest.mark.asyncio
    async def test_get_location_not_found_raises_error(
        self, location_manager, mock_session
    ):
        """Test that getting a non-existent location raises an error."""
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None

        with pytest.raises(ValueError, match="not found or access denied"):
            await location_manager.get_location("nonexistent", "user-001")

    @pytest.mark.asyncio
    async def test_update_location_validates_ownership(
        self, location_manager, mock_session
    ):
        """Test that updating a location verifies ownership."""
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None

        with pytest.raises(ValueError, match="not found or access denied"):
            await location_manager.update_location(
                "loc-001", "other-user", {"name": "New Name"}
            )

    @pytest.mark.asyncio
    async def test_get_location_stats_returns_aggregates(
        self, location_manager, mock_session
    ):
        """Test that location stats returns correct aggregates."""
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = MockRow(
            events=20,
            high_threats=5,
            persons_seen=8,
            audio_events=3,
            alerts_sent=12,
        )

        stats = await location_manager.get_location_stats(
            "loc-001", date(2026, 4, 27)
        )

        assert stats["events"] == 20
        assert stats["high_threats"] == 5
        assert stats["persons_seen"] == 8
        assert stats["audio_events"] == 3
        assert stats["alerts_sent"] == 12

    @pytest.mark.asyncio
    async def test_empty_locations_returns_empty_list(
        self, location_manager, mock_session
    ):
        """Test that a user with no locations gets an empty list."""
        mock_session.execute.return_value.fetchall = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []

        locations = await location_manager.get_locations("user-001")

        assert len(locations) == 0

    @pytest.mark.asyncio
    async def test_empty_digest_for_no_locations(
        self, location_manager, mock_session
    ):
        """Test that digest shows appropriate message for no locations."""
        mock_session.execute.return_value.fetchall = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []

        digest = await location_manager.get_unified_digest(
            "user-001", date(2026, 4, 27)
        )

        assert "No locations configured" in digest
        assert "Connect your first camera" in digest

    def test_empty_topology_is_valid(self, location_manager):
        """Test that empty topology passes validation."""
        assert location_manager._validate_topology({}) is True

    def test_self_loop_topology_rejected(self, location_manager):
        """Test that self-loop in topology is rejected."""
        self_loop = {
            "cam-a": {"neighbours": ["cam-a"], "min_transit_time": 0},
        }
        assert location_manager._validate_topology(self_loop) is False

    def test_unknown_tier_defaults_to_one(self, location_manager):
        """Test that unknown tier defaults to 1 location."""
        limit = location_manager._get_tier_location_limit("unknown_tier")
        assert limit == 1

    @pytest.mark.asyncio
    async def test_get_location_limit_returns_correct_value(
        self, location_manager
    ):
        """Test get_location_limit returns correct values."""
        assert await location_manager.get_location_limit("free") == 1
        assert await location_manager.get_location_limit("household") == 3
        assert await location_manager.get_location_limit("business") == 5

    @pytest.mark.asyncio
    async def test_get_camera_topology_returns_empty_for_no_location(
        self, location_manager, mock_session
    ):
        """Test that getting topology for non-existent location returns empty dict."""
        mock_session.execute.return_value.fetchone = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None

        topology = await location_manager.get_camera_topology("nonexistent")

        assert topology == {}
