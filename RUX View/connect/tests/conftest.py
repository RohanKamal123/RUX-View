"""Pytest configuration — mock heavy dependencies at import level.

Mocks pyaudio, tensorflow, tensorflow_hub, httpx, websockets, and
aiosqlite in sys.modules so that all module tests can run without
these large packages installed.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# Mock pyaudio
# ═══════════════════════════════════════════════════════════════════════════════

class MockPyAudio:
    """Mock for pyaudio.PyAudio."""

    paFloat32 = 1  # type: ignore

    def __init__(self, *args, **kwargs) -> None:
        self._mock_stream: MagicMock = MagicMock()

    def open(self, *args, **kwargs) -> MagicMock:
        return self._mock_stream

    def terminate(self) -> None:
        pass


class MockStream:
    """Mock for pyaudio.Stream."""

    def __init__(self) -> None:
        self._active = True

    def read(self, frame_count: int, exception_on_overflow: bool = True) -> bytes:
        return np.zeros(frame_count, dtype=np.float32).tobytes()

    def is_active(self) -> bool:
        return self._active

    def stop_stream(self) -> None:
        self._active = False

    def close(self) -> None:
        self._active = False


# Register mock pyaudio module
mock_pyaudio = MagicMock()
mock_pyaudio.PyAudio = MockPyAudio
mock_pyaudio.Stream = MockStream
mock_pyaudio.paFloat32 = 1
sys.modules["pyaudio"] = mock_pyaudio


# ═══════════════════════════════════════════════════════════════════════════════
# Mock tensorflow
# ═══════════════════════════════════════════════════════════════════════════════

class MockTensor:
    """Mock for tf.Tensor with .numpy() support."""

    def __init__(self, data: np.ndarray) -> None:
        self._data = data

    def numpy(self) -> np.ndarray:
        return self._data


class MockKerasLayer:
    """Mock for hub.KerasLayer (YAMNet model)."""

    def __call__(self, audio_chunk: np.ndarray) -> tuple:
        """Return dummy (scores, embeddings, spectrogram)."""
        num_frames = 64
        scores = np.zeros((num_frames, 521), dtype=np.float32)
        scores[:, 0] = 0.5  # default: speech
        return (
            MockTensor(scores),
            MockTensor(np.zeros((num_frames, 1024), dtype=np.float32)),
            MockTensor(np.zeros((num_frames, 64), dtype=np.float32)),
        )


mock_tf = MagicMock()
mock_tf.Tensor = MockTensor
mock_tf.keras = MagicMock()
mock_tf.keras.layers = MagicMock()
sys.modules["tensorflow"] = mock_tf


# ═══════════════════════════════════════════════════════════════════════════════
# Mock tensorflow_hub
# ═══════════════════════════════════════════════════════════════════════════════

def mock_hub_load(model_url: str) -> MockKerasLayer:
    """Mock for hub.load — returns a MockKerasLayer."""
    return MockKerasLayer()


mock_hub = MagicMock()
mock_hub.load = mock_hub_load
mock_hub.KerasLayer = MockKerasLayer
sys.modules["tensorflow_hub"] = mock_hub


# ═══════════════════════════════════════════════════════════════════════════════
# Mock httpx
# ═══════════════════════════════════════════════════════════════════════════════

class MockAsyncClient:
    """Mock for httpx.AsyncClient."""

    def __init__(self) -> None:
        self.is_closed = False

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, *args) -> None:
        pass

    async def get(self, url: str, **kwargs) -> MagicMock:
        response = MagicMock()
        response.status_code = 200
        return response

    async def post(self, url: str, **kwargs) -> MagicMock:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"status": "success", "incident_id": "inc_001"}
        response.raise_for_status = MagicMock()
        return response

    async def aclose(self) -> None:
        self.is_closed = True


mock_httpx = MagicMock()
mock_httpx.AsyncClient = MockAsyncClient
mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
mock_httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
sys.modules["httpx"] = mock_httpx


# ═══════════════════════════════════════════════════════════════════════════════
# Mock websockets
# ═══════════════════════════════════════════════════════════════════════════════

class MockWebSocketProtocol:
    """Mock for websockets.WebSocketClientProtocol."""

    def __init__(self) -> None:
        self._closed = False

    async def send(self, message: str) -> None:
        pass

    async def recv(self) -> str:
        return '{"type": "pong"}'

    async def close(self) -> None:
        self._closed = True


class MockWebSocketConnect:
    """Mock for websockets.connect context manager."""

    def __init__(self, url: str, **kwargs) -> None:
        self._url = url

    async def __aenter__(self) -> MockWebSocketProtocol:
        return MockWebSocketProtocol()

    async def __aexit__(self, *args) -> None:
        pass


async def _mock_websockets_connect(url: str, **kwargs) -> MockWebSocketProtocol:
    """Mock for websockets.connect — returns a MockWebSocketProtocol directly."""
    return MockWebSocketProtocol()


mock_websockets = MagicMock()
mock_websockets.connect = _mock_websockets_connect
mock_websockets.WebSocketClientProtocol = MockWebSocketProtocol
mock_websockets.exceptions = MagicMock()
mock_websockets.exceptions.ConnectionClosed = type("ConnectionClosed", (Exception,), {})
sys.modules["websockets"] = mock_websockets


# ═══════════════════════════════════════════════════════════════════════════════
# Mock aiosqlite (used by some tests for async SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

mock_aiosqlite = MagicMock()
sys.modules["aiosqlite"] = mock_aiosqlite


