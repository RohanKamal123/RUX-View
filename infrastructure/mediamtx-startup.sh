#!/bin/bash
# mediamtx-startup.sh — GCE instance startup script for the RTMP ingest host.
#
# Installs and runs MediaMTX (https://github.com/bluenviron/mediamtx, MIT
# license) as a systemd service. This is the media server
# backend/core/ingest/rtmp_ingest.py samples frames from and
# connection_type="rtmp_push" cameras (backend/api/cameras.py) push their
# RTMP stream to -- see CLAUDE.md's "Camera connection types" section for
# the full architecture.
#
# Verified in dev (a real ffmpeg RTMP push -> this same MediaMTX binary ->
# a real frame pulled back via OpenCV), but this specific script has not
# yet been run against a real GCE instance -- the project it targets
# (visionos-platform) had no billing account linked at the time this was
# written. Review before relying on it in production: no auth on the RTMP
# push port (relies on the per-camera stream key being unguessable, same
# security model as an unlisted webhook URL -- MediaMTX supports adding
# real auth if that's not sufficient for your threat model), no TLS on
# the RTSP port backend samples from (fine if backend-to-VM traffic stays
# on GCP's internal network; not fine if the backend ever runs somewhere
# else).
#
# Usage (once a billing account is linked to the project):
#   gcloud compute instances create visionos-mediamtx \
#     --project=visionos-platform \
#     --zone=us-central1-a \
#     --machine-type=e2-micro \
#     --image-family=debian-12 \
#     --image-project=debian-cloud \
#     --tags=mediamtx \
#     --metadata-from-file=startup-script=infrastructure/mediamtx-startup.sh
#
#   gcloud compute firewall-rules create allow-mediamtx-rtmp \
#     --project=visionos-platform \
#     --network=default \
#     --allow=tcp:1935 \
#     --target-tags=mediamtx \
#     --description="RTMP push from DVRs (connection_type=rtmp_push cameras)"
#
#   gcloud compute firewall-rules create allow-mediamtx-rtsp-internal \
#     --project=visionos-platform \
#     --network=default \
#     --allow=tcp:8554 \
#     --source-ranges=10.0.0.0/8 \
#     --target-tags=mediamtx \
#     --description="RTSP sampling from the backend only, not public"
#
# After creation, set backend/config.py's rtmp_ingest_push_host /
# rtmp_ingest_rtsp_base (or the equivalent env vars) to this instance's
# external IP.

set -euo pipefail

MEDIAMTX_VERSION="v1.9.3"
INSTALL_DIR="/opt/mediamtx"

apt-get update -qq
apt-get install -y -qq curl tar

mkdir -p "$INSTALL_DIR"
curl -sS -L -o /tmp/mediamtx.tar.gz \
  "https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_amd64.tar.gz"
tar -xzf /tmp/mediamtx.tar.gz -C "$INSTALL_DIR"
rm /tmp/mediamtx.tar.gz

cat > /etc/systemd/system/mediamtx.service <<'EOF'
[Unit]
Description=MediaMTX RTMP/RTSP ingest server (VisionOS)
After=network.target

[Service]
Type=simple
ExecStart=/opt/mediamtx/mediamtx /opt/mediamtx/mediamtx.yml
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mediamtx
systemctl start mediamtx
