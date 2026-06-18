"""
Tests for Sprint 3.3 — Re-ID Engine.

Tests person re-identification, embedding extraction, and matching.
"""

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
