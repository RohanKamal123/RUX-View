#!/usr/bin/env python3
"""
RTSP Discovery & Connection Demo for Vision OS.

Demonstrates the RTSP discovery and connection functionality.
Scans local network for RTSP cameras and tests connections.

Usage:
    python demo_rtsp_discovery.py
    python demo_rtsp_discovery.py --subnet 192.168.0.0/24
    python demo_rtsp_discovery.py --test rtsp://192.168.1.100:554/stream1
"""

import asyncio
import argparse
import logging
from typing import List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Add the connect module to path (now in scripts/, so go up one level then into connect)
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "connect"))

from connect.camera.rtsp_discovery import RTSPDiscovery, DiscoveredCamera
from connect.camera.rtsp_tester import RTSPTester, RTSPStreamInfo

async def demo_discovery(subnet: str = "192.168.1.0/24") -> None:
    """Demonstrate RTSP camera discovery on the local network."""
    print(f"🔍 Starting RTSP camera discovery on subnet: {subnet}")
    print("This may take a few minutes depending on your network size...\n")

    # Create discovery instance
    discovery = RTSPDiscovery(timeout=1.5, max_workers=50)

    # Scan network for RTSP cameras
    discovered_cameras = await discovery.scan_network(subnet)

    if not discovered_cameras:
        print("❌ No RTSP cameras found on the network.")
        return

    print(f"📷 Found {len(discovered_cameras)} potential RTSP cameras:")
    for i, camera in enumerate(discovered_cameras, 1):
        print(f"  {i}. {camera.ip_address}:{camera.port} - {camera.rtsp_url}")

    # Test connections to discovered cameras
    print(f"\n🔌 Testing connections to {len(discovered_cameras)} cameras...")
    tested_cameras = await discovery.test_rtsp_connections(discovered_cameras)

    # Display results
    accessible_cameras = [cam for cam in tested_cameras if cam.is_accessible]
    inaccessible_cameras = [cam for cam in tested_cameras if not cam.is_accessible]

    print(f"\n📊 Discovery Results:")
    print(f"  ✅ Accessible cameras: {len(accessible_cameras)}")
    print(f"  ❌ Inaccessible cameras: {len(inaccessible_cameras)}")

    if accessible_cameras:
        print(f"\n🎥 Accessible RTSP Streams:")
        for i, camera in enumerate(accessible_cameras, 1):
            info = camera.stream_info or {}
            print(f"  {i}. {camera.rtsp_url}")
            print(f"     Resolution: {info.get('width', '?')}x{info.get('height', '?')}")
            print(f"     FPS: {info.get('fps', '?')}")
            print(f"     Codec: {info.get('codec', '?')}")
            print(f"     Status: {info.get('status', 'unknown')}")
            print()

    if inaccessible_cameras:
        print(f"\n🚫 Inaccessible RTSP Ports:")
        for i, camera in enumerate(inaccessible_cameras, 1):
            print(f"  {i}. {camera.rtsp_url}")
            if camera.error:
                print(f"     Error: {camera.error}")
            print()

async def demo_single_test(rtsp_url: str, username: str = "", password: str = "") -> None:
    """Test a single RTSP stream."""
    print(f"🔍 Testing RTSP stream: {rtsp_url}")

    tester = RTSPTester(connection_timeout=5.0, test_duration=2.0)
    stream_info = await tester.test_stream(rtsp_url, username, password)

    print(f"\n📊 Test Results for {rtsp_url}:")
    if stream_info.is_connected:
        print("  ✅ Connection: SUCCESS")
        print(f"  📐 Resolution: {stream_info.width}x{stream_info.height}")
        print(f"  🎞️  FPS: {stream_info.fps:.1f}")
        print(f"  🎥 Codec: {stream_info.codec}")
        print(f"  📶 Bitrate: ~{stream_info.bitrate // 1000} kbps")
        print(f"  ⏱️  Connection time: {stream_info.connection_time:.2f}s")
        print(f"  🖼️  Frames received: {stream_info.frame_count}")
    else:
        print("  ❌ Connection: FAILED")
        if stream_info.error:
            print(f"  💥 Error: {stream_info.error}")

    # Try to get a snapshot
    print(f"\n📸 Attempting to capture snapshot...")
    snapshot = await tester.get_stream_snapshot(rtsp_url, username, password)
    if snapshot is not None:
        print(f"  ✅ Snapshot captured: {snapshot.shape[1]}x{snapshot.shape[0]} pixels")
    else:
        print(f"  ❌ Failed to capture snapshot")

async def demo_snapshot(rtsp_url: str, output_file: str = "snapshot.jpg") -> None:
    """Capture a snapshot from an RTSP stream and save it."""
    print(f"📸 Capturing snapshot from {rtsp_url}...")

    tester = RTSPTester(connection_timeout=5.0)
    snapshot = await tester.get_stream_snapshot(rtsp_url)

    if snapshot is None:
        print("❌ Failed to capture snapshot")
        return

    print(f"✅ Captured snapshot: {snapshot.shape[1]}x{snapshot.shape[0]} pixels")

    # Save the snapshot
    try:
        import cv2
        success = cv2.imwrite(output_file, snapshot)
        if success:
            print(f"💾 Saved snapshot to {output_file}")
        else:
            print("❌ Failed to save snapshot")
    except Exception as e:
        print(f"❌ Error saving snapshot: {e}")

async def main() -> None:
    """Main demo function."""
    parser = argparse.ArgumentParser(
        description="RTSP Discovery & Connection Demo",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--subnet",
        default="192.168.1.0/24",
        help="Network subnet to scan (default: 192.168.1.0/24)"
    )
    parser.add_argument(
        "--test",
        help="Test a specific RTSP URL instead of scanning"
    )
    parser.add_argument(
        "--snapshot",
        help="Capture snapshot from RTSP URL and save to file"
    )
    parser.add_argument(
        "--username",
        help="Username for RTSP authentication"
    )
    parser.add_argument(
        "--password",
        help="Password for RTSP authentication"
    )

    args = parser.parse_args()

    print("🚀 RTSP Discovery & Connection Demo")
    print("=" * 50)

    if args.snapshot:
        await demo_snapshot(args.snapshot, "snapshot.jpg")
    elif args.test:
        await demo_single_test(args.test, args.username, args.password)
    else:
        await demo_discovery(args.subnet)

    print("\n🎉 Demo completed!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n💥 Demo failed with error: {e}")
        import traceback
        traceback.print_exc()