"""
Tests for Sprint 3.3 — Re-ID Engine.

Tests person re-identification, embedding extraction, and matching.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.ai.reid_engine import ReIDEngine


class TestReIDEngine:
    def test_appearance_signature_format(self):
        """Appearance signature should follow expected format."""
        engine = ReIDEngine()
        person_result = {
            "gender": "male",
            "clothing": "red_shirt_blue_jeans",
            "hand_objects": "none",
            "action": "walking",
        }
        sig = engine.appearance_signature(person_result)
        assert sig == "male|red_shirt_blue_jeans|none|walking"

    def test_appearance_signature_defaults(self):
        """Appearance signature should handle missing fields with defaults."""
        engine = ReIDEngine()
        sig = engine.appearance_signature({})
        # The implementation defaults: unknown, unknown, none, standing
        assert sig == "unknown|unknown|none|standing"

    def test_string_similarity_identical(self):
        """Identical strings should have similarity 1.0."""
        engine = ReIDEngine()
        sim = engine.string_similarity("male|red_shirt|none|walking",
                                       "male|red_shirt|none|walking")
        assert sim == 1.0

    def test_string_similarity_different(self):
        """Completely different strings should have similarity 0.0."""
        engine = ReIDEngine()
        sim = engine.string_similarity("male|red_shirt|none|walking",
                                       "female|green_dress|bag|standing")
        assert sim == 0.0

    def test_string_similarity_partial(self):
        """Partially matching strings should have intermediate similarity."""
        engine = ReIDEngine()
        sim = engine.string_similarity("male|red_shirt|none|walking",
                                       "male|blue_shirt|none|running")
        assert 0.0 < sim < 1.0

    @pytest.mark.asyncio
    async def test_crop_person_valid_bbox(self):
        """Valid bbox should return a cropped person."""
        engine = ReIDEngine()
        # Create a test frame (100x100 RGB)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[20:80, 20:80] = [255, 255, 255]  # White square in center

        crop = await engine.crop_person(
            frame=frame,
            bbox_normalized=[0.2, 0.2, 0.8, 0.8],
            frame_width=100,
            frame_height=100,
        )
        assert crop is not None
        assert crop.shape[0] < 100  # Cropped height
        assert crop.shape[1] < 100  # Cropped width

    @pytest.mark.asyncio
    async def test_crop_person_invalid_bbox_returns_none(self):
        """Invalid bbox (x2 < x1) should return None."""
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        crop = await engine.crop_person(
            frame=frame,
            bbox_normalized=[0.5, 0.5, 0.4, 0.6],  # x2 < x1
            frame_width=100,
            frame_height=100,
        )
        assert crop is None

    @pytest.mark.asyncio
    async def test_crop_person_out_of_bounds_bbox(self):
        """Out of bounds bbox should be clamped and still return a crop."""
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        crop = await engine.crop_person(
            frame=frame,
            bbox_normalized=[-0.1, -0.1, 1.5, 1.5],
            frame_width=100,
            frame_height=100,
        )
        # The implementation clamps to frame boundaries, so it should still return a crop
        assert crop is not None

    @pytest.mark.asyncio
    async def test_extract_embedding_returns_512_dim(self):
        """Embedding should be 512-dimensional."""
        engine = ReIDEngine()
        # Create a test person crop (64x128 RGB)
        person_crop = np.random.randint(0, 255, (128, 64, 3), dtype=np.uint8)

        embedding = await engine.extract_embedding(person_crop)
        assert len(embedding) == 512

    @pytest.mark.asyncio
    async def test_extract_embedding_returns_float32(self):
        """Embedding should be float32 type."""
        engine = ReIDEngine()
        person_crop = np.random.randint(0, 255, (128, 64, 3), dtype=np.uint8)

        embedding = await engine.extract_embedding(person_crop)
        assert embedding.dtype == np.float32

    @pytest.mark.asyncio
    async def test_identify_returns_tuple(self):
        """identify should return (person_uid, confidence) tuple."""
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        person_result = {
            "gender": "male",
            "clothing": "red_shirt",
            "hand_objects": "none",
            "action": "walking",
            "bbox": [0.2, 0.2, 0.5, 0.8],
        }

        person_uid, confidence = await engine.identify(
            db=None, frame=frame, person_result=person_result,
            location_id="loc-001", user_id="user-001",
        )
        assert isinstance(person_uid, str)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.asyncio
    async def test_identify_returns_person_uid(self):
        """identify should return a PERSON_XXX format UID."""
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        person_result = {
            "gender": "male",
            "clothing": "red_shirt_blue_jeans",
            "hand_objects": "none",
            "action": "walking",
            "bbox": [0.2, 0.2, 0.5, 0.8],
        }

        uid, conf = await engine.identify(
            db=None, frame=frame, person_result=person_result,
            location_id="loc-001", user_id="user-001",
        )
        assert uid.startswith("PERSON_")
        assert conf >= 0.0


class TestReIDPersistence:
    """identify() must persist matches/new persons — see backend/ai/reid_engine.py
    module docstring for why this matters: without it, Re-ID, ghost detection,
    and repeat-sighting escalation don't work across incidents at all.
    """

    def _person_result(self):
        return {
            "gender": "male",
            "clothing": "red shirt, black jeans",
            "hand_objects": ["phone"],
            "carried_items": ["backpack"],
            "action": "walking",
            "anomaly_signals": [],
            "bbox": [0.2, 0.2, 0.5, 0.8],
        }

    @pytest.mark.asyncio
    async def test_identify_creates_new_person_and_sighting_when_no_match(self):
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        db = AsyncMock()

        with patch("backend.storage.crud.find_similar_persons", AsyncMock(return_value=[])), \
             patch("backend.storage.crud.create_person", AsyncMock()) as mock_create_person, \
             patch("backend.storage.crud.create_sighting", AsyncMock()) as mock_create_sighting:
            uid, conf = await engine.identify(
                db=db, frame=frame, person_result=self._person_result(),
                location_id="loc-001", user_id="user-001", camera_id="CAM_1",
            )

        assert uid.startswith("PERSON_")
        assert conf == 0.0
        mock_create_person.assert_awaited_once()
        person_data = mock_create_person.await_args.args[1]
        assert person_data["person_uid"] == uid
        assert person_data["location_id"] == "loc-001"
        assert person_data["sighting_count"] == 1

        mock_create_sighting.assert_awaited_once()
        sighting_data = mock_create_sighting.await_args.args[1]
        assert sighting_data["person_uid"] == uid
        assert sighting_data["camera_id"] == "CAM_1"
        assert sighting_data["clothing_top"] == "red shirt, black jeans"
        assert sighting_data["hand_objects"] == "phone"
        assert sighting_data["accessories"] == "backpack"

    @pytest.mark.asyncio
    async def test_identify_updates_existing_person_on_exact_match(self):
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        db = AsyncMock()
        existing_person = MagicMock(embedding=None, appearance_history=None)

        similar = [{
            "person_uid": "PERSON_EXISTING",
            "similarity": 0.95,
            "appearance_signature": "male|red shirt|phone|walking",
        }]

        with patch("backend.storage.crud.find_similar_persons", AsyncMock(return_value=similar)), \
             patch("backend.storage.crud.get_person", AsyncMock(return_value=existing_person)), \
             patch("backend.storage.crud.create_person", AsyncMock()) as mock_create_person, \
             patch("backend.storage.crud.update_person_sighting", AsyncMock()) as mock_update, \
             patch("backend.storage.crud.create_sighting", AsyncMock()) as mock_create_sighting:
            uid, conf = await engine.identify(
                db=db, frame=frame, person_result=self._person_result(),
                location_id="loc-001", user_id="user-001",
            )

        assert uid == "PERSON_EXISTING"
        assert conf == 0.95
        mock_create_person.assert_not_awaited()
        mock_update.assert_awaited_once_with(db, "PERSON_EXISTING", "user-001")
        assert existing_person.embedding is not None
        assert existing_person.appearance_history["last_signature"]
        mock_create_sighting.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_identify_skips_persistence_when_db_is_none(self):
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch("backend.storage.crud.create_person", AsyncMock()) as mock_create_person, \
             patch("backend.storage.crud.create_sighting", AsyncMock()) as mock_create_sighting:
            uid, conf = await engine.identify(
                db=None, frame=frame, person_result=self._person_result(),
                location_id="loc-001", user_id="user-001",
            )

        assert uid.startswith("PERSON_")
        mock_create_person.assert_not_awaited()
        mock_create_sighting.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_break_identify(self):
        """A DB error while persisting must not prevent identify() from
        returning a usable person_uid to the caller."""
        engine = ReIDEngine()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        db = AsyncMock()

        with patch("backend.storage.crud.find_similar_persons", AsyncMock(return_value=[])), \
             patch("backend.storage.crud.create_person", AsyncMock(side_effect=RuntimeError("db down"))):
            uid, conf = await engine.identify(
                db=db, frame=frame, person_result=self._person_result(),
                location_id="loc-001", user_id="user-001",
            )

        assert uid.startswith("PERSON_")
        assert conf == 0.0
