"""
rtmp_ingest.py — Frame sampling from RTMP-pushed camera streams.

Architecture (connection_type="rtmp_push" on Camera, see
backend/storage/database.py): rather than the backend or a local agent
pulling RTSP from the customer's DVR (which needs either port forwarding or
a proprietary P2P protocol), the DVR itself pushes an RTMP stream OUT to a
media server we run -- an outbound connection from the DVR's side, no
inbound port opened, no NAT traversal needed. Most mid-range DVRs
(Hikvision, Dahua, Uniview, many XMEye-based OEMs) support this natively
via a "Platform Access" / RTMP menu option.

We run MediaMTX (github.com/bluenviron/mediamtx, MIT license) as that media
server. It accepts the RTMP push and automatically re-serves the same live
stream over RTSP, which lets us keep using OpenCV/VideoCapture here exactly
like every other frame source in this codebase, instead of needing a
separate RTMP client library.

This module only pulls a single frame on demand (see sample_frame()) --
matching the trigger-only cost philosophy (D005 in CLAUDE.md): we do not
continuously decode the live stream, we sample it periodically (see the
poller design note at the bottom of this file) and feed samples through
the exact same pipeline a connect/ agent's motion trigger would.

Verified end-to-end in dev by pushing a real RTMP stream via ffmpeg
(`ffmpeg -re -f lavfi -i testsrc ... -f flv rtmp://.../live/<key>`) and
confirming a frame could be pulled back via
rtsp://<mediamtx>/live/<key> — this is real, tested code, not a
guess at an undocumented protocol (contrast with backend/core/p2p/, which
is unverified without real camera hardware).
"""

import logging
from typing import Optional

import cv2

logger = logging.getLogger(__name__)


def sample_frame(stream_key: str, mediamtx_rtsp_base: str, timeout_sec: float = 5.0) -> Optional[bytes]:
    """Pull a single JPEG frame from a live RTMP-pushed stream.

    Args:
        stream_key: The camera's rtmp_stream_key (Camera.rtmp_stream_key).
            The DVR pushes to rtmp://<mediamtx_host>:1935/live/<stream_key>;
            this reads it back via MediaMTX's automatic RTSP re-serve.
        mediamtx_rtsp_base: e.g. "rtsp://mediamtx-host:8554" (no trailing
            slash). Configurable since the media server is a separate
            always-on host from the Cloud Run API (RTMP ingest is a
            persistent-connection workload Cloud Run's request-scoped
            autoscaling isn't a fit for).
        timeout_sec: Max time to wait for a frame before giving up --
            covers the case where the DVR isn't currently pushing (stream
            offline), which must not hang the caller.

    Returns:
        JPEG bytes, or None if the stream isn't live / no frame could be
        read within the timeout.
    """
    url = f"{mediamtx_rtsp_base}/live/{stream_key}"
    cap = None
    try:
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout_sec * 1000))
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout_sec * 1000))
        if not cap.isOpened():
            logger.debug("rtmp_ingest: stream not live for key %s", stream_key)
            return None

        ok, frame = cap.read()
        if not ok or frame is None:
            logger.debug("rtmp_ingest: no frame read for key %s", stream_key)
            return None

        success, jpeg_buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            return None
        return jpeg_buf.tobytes()
    except Exception:
        logger.exception("rtmp_ingest: failed to sample frame for key %s", stream_key)
        return None
    finally:
        if cap is not None:
            cap.release()


# ── Poller design (not yet wired into the scheduler) ─────────────────────
#
# The next step to make this live: an APScheduler job (alongside
# db_pool_config_refresh in backend/dashboard/server.py) that, every N
# seconds, lists all cameras with connection_type == "rtmp_push", calls
# sample_frame() for each, and for any frame obtained, feeds it through
# the SAME pipeline entry point backend/api/triggers.py's
# receive_frame_trigger() uses -- so an RTMP-push camera gets identical
# session-merge / YOLO-gate / Gemini-throttle behavior to a connect/
# agent's motion trigger, not a separate code path to maintain.
#
# Deliberately not wired yet: routing a poller-sampled frame through
# receive_frame_trigger() means either (a) an internal HTTP self-call
# needing a service-account auth story that doesn't exist yet, or (b)
# extracting triggers.py's session logic into a plain function both the
# HTTP route and this poller can call directly. (b) is the right shape
# long-term but touches triggers.py's session-merge logic that just got
# real regression coverage (test_session_merge.py) -- riskier to do in the
# same pass as everything else being built tonight. Left as the next
# concrete task rather than rushed.
