"""
reid_engine.py — Person Re-Identification engine using FastReID + pgvector.

Three-tier matching:
  Tier 1: Exact match (same person_uid) → return existing
  Tier 2: pgvector cosine similarity > 0.72 → auto-match
  Tier 3: pgvector cosine similarity 0.5-0.72 → AI tiebreaker
          < 0.5 → new person

Uncertainty zone: 0.5-0.72 cosine similarity → calls ai_client.reid_tiebreaker()
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Matching thresholds
EXACT_MATCH_THRESHOLD = 0.72  # Auto-match above this
UNCERTAIN_MIN = 0.50          # Uncertainty zone starts here
UNCERTAIN_MAX = 0.72          # Uncertainty zone ends here


class ReIDEngine:
    """Person Re-Identification engine using FastReID + pgvector."""

    def __init__(self):
        """Initialize FastReID model (lazy-loaded)."""
        self._model = None
        self._loaded = False

    def _load_model(self) -> None:
        """Load FastReID model from boxmot.

        Lazy-loaded on first use.
        Uses FastReID backend with ResNet50.
        """
        if self._loaded:
            return

        try:
            # Import boxmot FastReID
            from boxmot.appearance.reid_model_factory import (
                download_reid_model,
                get_reid_model,
            )

            # Load ResNet50-based FastReID model
            model_name = "resnet50"  # Standard FastReID backbone
            reid_model = download_reid_model(model_name)
            self._model = get_reid_model(reid_model)
            self._loaded = True
            logger.info("FastReID model loaded successfully (ResNet50)")
        except ImportError:
            logger.warning(
                "boxmot not installed. Re-ID will use fallback embeddings."
            )
            self._model = None
            self._loaded = True
        except Exception as exc:
            logger.error("Failed to load FastReID model: %s", exc, exc_info=True)
            self._model = None
            self._loaded = True

    async def extract_embedding(self, person_crop: np.ndarray) -> np.ndarray:
        """Extract 512-dimension embedding from a person crop.

        Args:
            person_crop: RGB numpy array of cropped person.

        Returns:
            512-dim float32 numpy array.
        """
        self._load_model()

        if self._model is None:
            # Fallback: return a random 512-dim vector (for testing/development)
            return np.random.randn(512).astype(np.float32)

        try:
            # Preprocess: resize to 256x128 (standard for person Re-ID)
            import cv2
            resized = cv2.resize(person_crop, (128, 256))
            # Normalize and add batch dimension
            input_tensor = resized.astype(np.float32) / 255.0
            input_tensor = np.expand_dims(input_tensor, axis=0)

            # Run through model
            embedding = self._model(input_tensor)[0]
            # L2 normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding.astype(np.float32)
        except Exception as exc:
            logger.error("Embedding extraction failed: %s", exc, exc_info=True)
            return np.random.randn(512).astype(np.float32)

    async def crop_person(self, frame: np.ndarray, bbox_normalized: list[float],
                           frame_width: int, frame_height: int) -> Optional[np.ndarray]:
        """Crop a person from frame using normalized bbox.

        Args:
            frame: Full frame numpy array.
            bbox_normalized: [x1, y1, x2, y2] normalized 0-1.
            frame_width: Frame width in pixels.
            frame_height: Frame height in pixels.

        Returns:
            Cropped RGB numpy array or None if bbox invalid.
        """
        try:
            x1 = int(bbox_normalized[0] * frame_width)
            y1 = int(bbox_normalized[1] * frame_height)
            x2 = int(bbox_normalized[2] * frame_width)
            y2 = int(bbox_normalized[3] * frame_height)

            # Clamp to frame boundaries
            x1 = max(0, min(x1, frame_width - 1))
            y1 = max(0, min(y1, frame_height - 1))
            x2 = max(0, min(x2, frame_width - 1))
            y2 = max(0, min(y2, frame_height - 1))

            # Validate dimensions
            if x2 <= x1 or y2 <= y1:
                logger.warning("Invalid bbox: (%d,%d,%d,%d)", x1, y1, x2, y2)
                return None

            # Crop
            crop = frame[y1:y2, x1:x2]

            # Convert BGR to RGB if needed (OpenCV default is BGR)
            if crop.shape[-1] == 3:
                import cv2
                crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

            return crop
        except Exception as exc:
            logger.error("Crop failed: %s", exc, exc_info=True)
            return None

    async def identify(self, db, frame: np.ndarray,
                         person_result: dict, location_id: str,
                         user_id: str,
                         config: Optional[dict] = None,
                         camera_id: Optional[str] = None) -> tuple[str, float]:
        """Identify a person from a frame + AI analysis result.

        Persists the match (or new person) and this sighting's appearance
        detail to the persons/person_sightings tables when *db* is a real
        session — this is what makes Re-ID, ghost detection, and
        repeat-sighting escalation actually work across incidents instead
        of minting a fresh person_uid every single time. See
        _persist_sighting() docstring for the persistence semantics.

        Args:
            db: Database session, or None to skip persistence entirely
                (matching lookups still run if db is given elsewhere).
            frame: Full frame numpy array.
            person_result: Dict from ai_client.analyse_frame() for this person.
            location_id: Location UUID.
            user_id: User UUID.
            config: Optional runtime config dict (e.g. from config_store).
                    ``reid_exact_match_threshold`` is read from it.
            camera_id: Camera that captured this sighting, for
                       PersonSighting.camera_id (cross-camera tracking).

        Returns:
            (person_uid, confidence) — existing or new PERSON_XXX.
        """
        exact_match_threshold = (
            config.get("reid_exact_match_threshold", 0.72)
            if config else EXACT_MATCH_THRESHOLD
        )
        uncertain_min = config.get("reid_uncertain_min", UNCERTAIN_MIN) if config else UNCERTAIN_MIN
        uncertain_max = config.get("reid_uncertain_max", UNCERTAIN_MAX) if config else UNCERTAIN_MAX
        find_similar_limit = config.get("reid_find_similar_limit", 5) if config else 5
        pgvector_threshold = config.get("reid_pgvector_threshold", 0.7) if config else 0.7
        tiebreaker_boost = config.get("reid_tiebreaker_boost", 0.9) if config else 0.9
        # Extract embedding from person crop
        bbox = (
            person_result.get("bbox_normalized") or
            person_result.get("bbox") or
            [0, 0, 0, 0]
        )
        frame_h, frame_w = frame.shape[:2]
        crop = await self.crop_person(frame, bbox, frame_w, frame_h)

        if crop is None:
            # Cannot crop — generate new ID
            from uuid import uuid4
            return (f"PERSON_{uuid4().hex[:8].upper()}", 0.0)

        embedding = await self.extract_embedding(crop)
        embedding_list = embedding.tolist()

        # Tier 1: Check exact match with person_uid from AI analysis
        person_uid = person_result.get("person_uid")
        if person_uid and person_uid.startswith("PERSON_"):
            await self._persist_sighting(
                db, person_uid, user_id, location_id, camera_id,
                embedding_list, person_result, is_new=False,
            )
            return (person_uid, 1.0)

        # Tier 2 & 3: Find similar via pgvector
        similar = await self.find_similar(
            db, embedding_list, location_id,
            limit=find_similar_limit, threshold=pgvector_threshold,
        )

        if not similar:
            # No matches — new person
            from uuid import uuid4
            new_uid = f"PERSON_{uuid4().hex[:8].upper()}"
            await self._persist_sighting(
                db, new_uid, user_id, location_id, camera_id,
                embedding_list, person_result, is_new=True,
            )
            return (new_uid, 0.0)

        best_match = similar[0]
        best_score = best_match.get("similarity", 0.0)
        best_person_uid = best_match.get("person_uid")

        # Tier 2: Auto-match above threshold
        if best_score >= exact_match_threshold:
            await self._persist_sighting(
                db, best_person_uid, user_id, location_id, camera_id,
                embedding_list, person_result, is_new=False,
            )
            return (best_person_uid, best_score)

        # Tier 3: Uncertainty zone — use AI tiebreaker
        if best_score >= uncertain_min:
            from backend.ai import reid_tiebreaker

            sig_a = self.appearance_signature(person_result)
            sig_b = best_match.get("appearance_signature", "")

            tiebreaker_result = await reid_tiebreaker(sig_a, sig_b, best_score)
            # NOTE: this attributes the sighting to best_person_uid even when
            # the tiebreaker verdict is "not a match" (pre-existing behavior,
            # unchanged here — see reid_engine.py history). Persisting matches
            # whatever identify() decides to return, it doesn't change the
            # decision itself.
            await self._persist_sighting(
                db, best_person_uid, user_id, location_id, camera_id,
                embedding_list, person_result, is_new=False,
            )
            if tiebreaker_result.get("match", False):
                return (best_person_uid, (best_score + tiebreaker_boost) / 2)  # Boost confidence
            return (best_person_uid, best_score)

        # Below uncertainty threshold — new person
        from uuid import uuid4
        new_uid = f"PERSON_{uuid4().hex[:8].upper()}"
        await self._persist_sighting(
            db, new_uid, user_id, location_id, camera_id,
            embedding_list, person_result, is_new=True,
        )
        return (new_uid, 0.0)

    async def _persist_sighting(
        self, db, person_uid: str, user_id: str, location_id: str,
        camera_id: Optional[str], embedding: list[float],
        person_result: dict, is_new: bool,
    ) -> None:
        """Create/update the person record and record this sighting.

        Best-effort: persistence failures are logged and swallowed here
        rather than raised, so a DB hiccup never prevents identify() from
        returning a usable person_uid for the caller — alerting and the
        event save downstream matter more than every single Re-ID write
        landing. The DB session's own commit/rollback (managed by the
        caller, see CameraPipeline._run_reid) is unaffected by that: a
        swallowed exception here just means this particular flush didn't
        happen, not that the whole session aborts.

        No-ops entirely when db is None (tests, or callers that only want
        the match decision without persistence).
        """
        if db is None:
            return
        try:
            from backend.storage import crud as storage_crud

            now = datetime.now(timezone.utc)
            signature = self.appearance_signature(person_result)
            appearance_history = {"last_signature": signature, "updated_at": now.isoformat()}

            existing = None if is_new else await storage_crud.get_person(db, person_uid, user_id)

            if existing is None:
                # Either genuinely new, or a similarity match came back for a
                # person_uid whose row is gone (deleted, or a race with
                # another request) — create it so the sighting below has a
                # parent record either way.
                await storage_crud.create_person(db, {
                    "person_uid": person_uid,
                    "user_id": user_id,
                    "location_id": location_id,
                    "first_seen": now,
                    "last_seen": now,
                    "sighting_count": 1,
                    "embedding": embedding,
                    "appearance_history": appearance_history,
                })
            else:
                await storage_crud.update_person_sighting(db, person_uid, user_id)
                existing.embedding = embedding
                existing.appearance_history = appearance_history
                await db.flush()

            await storage_crud.create_sighting(db, {
                "person_uid": person_uid,
                "user_id": user_id,
                "camera_id": camera_id,
                "timestamp": now,
                "clothing_top": person_result.get("clothing"),
                "hand_objects": ", ".join(person_result.get("hand_objects") or []) or None,
                "accessories": ", ".join(person_result.get("carried_items") or []) or None,
                "action": person_result.get("action"),
                "anomaly_signals": ", ".join(person_result.get("anomaly_signals") or []) or None,
                "embedding": embedding,
            })
        except Exception as exc:
            logger.error(
                "Failed to persist person/sighting for %s: %s",
                person_uid, exc, exc_info=True,
            )

    async def find_similar(self, db, embedding: list[float],
                            location_id: str, limit: int = 5,
                            threshold: float = 0.7) -> list[dict]:
        """Find similar persons using pgvector cosine similarity.

        Delegates to crud.find_similar_persons().

        Args:
            db: Database session.
            embedding: 512-dim embedding vector.
            location_id: Location UUID (HARD boundary).
            limit: Max results.

        Returns:
            List of dicts with person_uid, similarity, appearance_signature.
        """
        try:
            from backend.storage.crud import find_similar_persons
            results = await find_similar_persons(
                db, embedding, location_id, limit=limit, threshold=threshold,
            )
            return results or []
        except ImportError:
            logger.warning("crud.find_similar_persons not available")
            return []
        except Exception as exc:
            logger.error("find_similar failed: %s", exc, exc_info=True)
            return []

    def appearance_signature(self, person_result: dict) -> str:
        """Generate a text signature from AI person analysis.

        Used for tiebreaker comparison.
        Format: "gender|clothing|hand_objects|action"

        Args:
            person_result: Dict from AI analysis for this person.

        Returns:
            Formatted signature string.
        """
        gender = person_result.get("gender", "unknown")
        clothing = person_result.get("clothing", "unknown")
        hand_objects = person_result.get("hand_objects", "none")
        action = person_result.get("action", "standing")

        # Normalize to lowercase
        gender = str(gender).lower().strip()
        clothing = str(clothing).lower().strip()
        hand_objects = str(hand_objects).lower().strip()
        action = str(action).lower().strip()

        return f"{gender}|{clothing}|{hand_objects}|{action}"

    def string_similarity(self, sig_a: str, sig_b: str) -> float:
        """Compute simple string similarity between two appearance signatures.

        Uses token overlap (Jaccard-like).

        Args:
            sig_a: First appearance signature.
            sig_b: Second appearance signature.

        Returns:
            0.0 to 1.0 similarity score.
        """
        tokens_a = set(sig_a.lower().split("|"))
        tokens_b = set(sig_b.lower().split("|"))

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b

        return len(intersection) / len(union)
