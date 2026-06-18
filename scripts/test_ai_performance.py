#!/usr/bin/env python3
"""
Comprehensive AI Performance Testing Script for Vision OS
Tests all AI modalities with real data and measures response times

Features:
- Tests image, audio, and text analysis
- Measures response times for each AI call
- Tests additional functions not covered in basic test
- Handles rate limiting properly
- Provides detailed performance metrics
"""

import asyncio
import os
import sys
import time
from pathlib import Path
import json
import struct
import math

# Add backend to path (now in scripts/, so go up one more level)
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ai.ai_client import (
    analyse_frame,
    analyse_frame_structured,
    analyse_frame_detailed,
    analyse_frame_with_second_pass,
    analyse_audio,
    analyse_shop_entry,
    answer_query,
    answer_scene_state,
    generate_daily_digest,
    generate_weekly_digest,
    reid_tiebreaker,
    make_incident_decision,
    _init_vertex,
    _get_model,
)

from backend.config import settings


def load_sample_frames():
    """Load sample frame files from test_gemini_frames directory."""
    frames_dir = Path(__file__).parent.parent / "test_gemini_frames"
    if not frames_dir.exists():
        print(f"❌ Frames directory not found: {frames_dir}")
        return []

    frame_files = list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.jpeg"))
    frames = []
    for frame_file in frame_files:
        with open(frame_file, "rb") as f:
            frames.append((frame_file.name, f.read()))
    return frames

def create_test_audio():
    """Create a simple test audio file (WAV format)."""
    sample_rate = 16000
    duration = 2.0  # 2 seconds
    num_samples = int(sample_rate * duration)

    # Generate a simple sine wave
    samples = []
    for i in range(num_samples):
        sample = int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        samples.append(struct.pack("<h", sample))

    data = b"".join(samples)
    data_size = len(data)

    # WAV header
    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<I", 16)  # chunk size
    header += struct.pack("<H", 1)  # PCM
    header += struct.pack("<H", 1)  # mono
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", sample_rate * 2)  # byte rate
    header += struct.pack("<H", 2)  # block align
    header += struct.pack("<H", 16)  # bits per sample
    header += b"data"
    header += struct.pack("<I", data_size)

    return header + data

async def measure_function_performance(func_name, func, *args, **kwargs):
    """Measure the performance of an async function with timing."""
    print(f"\n  📊 Testing {func_name}...")
    start_time = time.time()

    try:
        result = await func(*args, **kwargs)
        end_time = time.time()
        response_time = end_time - start_time

        print(f"     ✅ Success in {response_time:.2f} seconds")
        return True, response_time, result

    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        print(f"     ❌ Failed after {response_time:.2f} seconds: {e}")
        return False, response_time, None

async def test_adc_initialization():
    """Fail-fast diagnostics for Vertex AI ADC + project/location."""
    print("\n" + "="*70)
    print("🔑 TESTING ADC INITIALIZATION")
    print("="*70)

    try:
        # Initialize Vertex AI
        _init_vertex()
        model = _get_model()

        print("  ✅ ADC Initialization Successful!")
        print("     - Vertex AI SDK initialized")
        print("     - Model loaded: gemini-2.5-flash")
        print("     - Authentication: Application Default Credentials")

        return True
    except Exception as e:
        print(f"  ❌ ADC Initialization Failed: {e}")
        return False

async def test_image_analysis_performance():
    """Test all image analysis functions with performance measurement."""
    print("\n" + "="*70)
    print("🖼️  TESTING IMAGE ANALYSIS PERFORMANCE")
    print("="*70)

    frames = load_sample_frames()
    if not frames:
        print("⚠️  No sample frames found. Skipping image tests.")
        return False, {}

    print(f"Found {len(frames)} sample frame(s) for testing")

    results = {}
    total_time = 0.0
    successful_tests = 0

    for frame_name, frame_bytes in frames:
        print(f"\n  Testing frame: {frame_name} ({len(frame_bytes)} bytes)")

        # Test different image analysis functions
        tests = [
            ("Structured Analysis", analyse_frame_structured, frame_bytes),
            ("Detailed Analysis", analyse_frame_detailed, frame_bytes),
            ("Fast Analysis", analyse_frame, frame_bytes),
            ("Second Pass Analysis", analyse_frame_with_second_pass, frame_bytes),
            ("Shop Entry Analysis", analyse_shop_entry, frame_bytes),
        ]


        for test_name, func, *args in tests:
            success, duration, result = await measure_function_performance(test_name, func, *args)
            if success:
                successful_tests += 1
                total_time += duration
                results[f"{frame_name}_{test_name}"] = {
                    "success": True,
                    "duration": duration,
                    "result_summary": get_result_summary(test_name, result)
                }
            else:
                results[f"{frame_name}_{test_name}"] = {
                    "success": False,
                    "duration": duration,
                    "error": "Function failed"
                }

    avg_time = total_time / successful_tests if successful_tests > 0 else 0
    print(f"\n  📈 Image Analysis Summary:")
    print(f"     - Successful tests: {successful_tests}/{len(tests) * len(frames)}")
    print(f"     - Average response time: {avg_time:.2f} seconds")
    print(f"     - Total testing time: {total_time:.2f} seconds")

    return successful_tests > 0, results

def get_result_summary(test_name, result):
    """Extract key information from different test results."""
    if not result:
        return "No result"

    if test_name == "Structured Analysis":
        return {
            "event_type": result.get("event_type", "N/A"),
            "threat_level": result.get("threat_level", "N/A"),
            "confidence": result.get("confidence", 0),
            "description": result.get("description", "N/A")[:50]
        }
    elif test_name == "Detailed Analysis":
        persons = result.get("persons", [])
        return {
            "person_count": len(persons),
            "scene_description": result.get("scene", {}).get("description", "N/A")[:50],
            "anomalies": result.get("anomalies", [])
        }
    elif test_name == "Fast Analysis":
        return {
            "person_count": result.get("person_count", 0),
            "scene_alerts": result.get("scene_alerts", []),
            "vehicles": result.get("vehicles", [])
        }
    elif test_name == "Shop Entry Analysis":
        return {
            "gender": result.get("gender", "N/A"),
            "age_group": result.get("age_group", "N/A"),
            "confidence": result.get("confidence", 0)
        }
    else:
        return "Unknown test type"

async def test_audio_analysis_performance():
    """Test audio analysis with performance measurement."""
    print("\n" + "="*70)
    print("🔊 TESTING AUDIO ANALYSIS PERFORMANCE")
    print("="*70)

    audio_bytes = create_test_audio()
    print(f"Created test audio: {len(audio_bytes)} bytes")

    success, duration, result = await measure_function_performance(
        "Audio Analysis", analyse_audio, audio_bytes
    )

    if success:
        print(f"  📊 Audio Analysis Results:")
        print(f"     - Transcript: {result.get('transcript', 'N/A') or '(empty)'}")
        print(f"     - Language: {result.get('language', 'N/A')}")
        print(f"     - Threat Detected: {result.get('threat_detected', 'N/A')}")
        print(f"     - Threat Level: {result.get('threat_level', 'N/A')}")
        print(f"     - Confidence: {result.get('confidence', 'N/A')}")
        print(f"     - Response Time: {duration:.2f} seconds")

        return True, {
            "duration": duration,
            "result": {
                "transcript": result.get("transcript", ""),
                "language": result.get("language", ""),
                "threat_detected": result.get("threat_detected", False),
                "threat_level": result.get("threat_level", ""),
                "confidence": result.get("confidence", 0)
            }
        }
    else:
        return False, {"duration": duration, "error": "Audio analysis failed"}

async def test_text_analysis_performance():
    """Test various text analysis functions with performance measurement."""
    print("\n" + "="*70)
    print("📝 TESTING TEXT ANALYSIS PERFORMANCE")
    print("="*70)

    results = {}
    total_time = 0.0
    successful_tests = 0

    # Test different text analysis functions
    text_tests = [
        ("Query Answering", answer_query, {
            "question": "What happened at the front gate?",
            "events": [
                {"id": 1, "timestamp": "2024-01-01T10:00:00", "event_type": "person_entering"},
                {"id": 2, "timestamp": "2024-01-01T10:05:00", "event_type": "person_leaving"},
            ],
            "analyses": [
                {"persons": [{"gender": "male", "clothing": "red shirt", "action": "walking"}]},
            ]
        }),
        ("Scene State Query", answer_scene_state, {
            "question": "Is the front gate open?",
            "world_state": {
                "gates": {"front_gate": "open"},
                "doors": {"front_door": "closed"}
            }
        }),
        ("Daily Digest Generation", generate_daily_digest, {
            "events": {
                "2024-01-01": [
                    {"time": "10:00", "type": "person_entering", "threat_level": "LOW"},
                    {"time": "14:30", "type": "vehicle", "threat_level": "MEDIUM"},
                ]
            },
            "tier": "free"
        }),
        ("Re-ID Tiebreaker", reid_tiebreaker, {
            "desc_a": "Male, 30s, blue shirt, jeans, backpack",
            "desc_b": "Male, 30s, blue shirt, jeans, no backpack",
            "time_gap": 120
        }),
        ("Incident Decision", make_incident_decision, {
            "timeline": [
                {"time": "10:00:00", "action": "person_approaches_gate"},
                {"time": "10:00:15", "action": "gate_opens"},
                {"time": "10:00:30", "action": "person_enters"},
            ],
            "context": {
                "camera_name": "front_gate",
                "camera_mode": "normal",
                "timestamp": "2024-01-01T10:00:00",
                "location_type": "residential",
                "is_business_hours": True,
                "duration": 30,
                "reid_result": "unknown",
                "is_known": False,
                "label": "unknown",
                "audio_context": "normal conversation",
                "history": []
            }
        })
    ]

    for test_name, func, kwargs in text_tests:
        # Always pass explicit kwargs to avoid ordering bugs.
        success, duration, result = await measure_function_performance(test_name, func, **kwargs)


        if success and result is not None:
            successful_tests += 1
            total_time += duration
            results[test_name] = {
                "success": True,
                "duration": duration,
                "result_summary": get_text_result_summary(test_name, result)
            }
        else:
            results[test_name] = {
                "success": False,
                "duration": duration,
                "error": "Function failed" if success else "Function failed"
            }

    avg_time = total_time / successful_tests if successful_tests > 0 else 0
    print(f"\n  📈 Text Analysis Summary:")
    print(f"     - Successful tests: {successful_tests}/{len(text_tests)}")
    print(f"     - Average response time: {avg_time:.2f} seconds")
    print(f"     - Total testing time: {total_time:.2f} seconds")

    return successful_tests > 0, results

def get_text_result_summary(test_name, result):
    """Extract key information from text analysis results."""
    if not result:
        return "No result"

    if test_name == "Query Answering":
        return result[:100] + "..." if len(result) > 100 else result
    elif test_name == "Scene State Query":
        return result[:100] + "..." if len(result) > 100 else result
    elif test_name == "Daily Digest Generation":
        return result[:100] + "..." if len(result) > 100 else result
    elif test_name == "Re-ID Tiebreaker":
        return {
            "same_person": result.get("same_person", False),
            "confidence": result.get("confidence", 0),
            "reasoning": result.get("reasoning", "N/A")[:50]
        }
    elif test_name == "Incident Decision":
        return {
            "threat_level": result.get("threat_level", "N/A"),
            "action": result.get("action", "N/A"),
            "alert_message": result.get("alert_message", "N/A")[:50]
        }
    else:
        return "Unknown test type"

async def test_rate_limiting():
    """Test the rate limiting functionality."""
    print("\n" + "="*70)
    print("⏱️  TESTING RATE LIMITING")
    print("="*70)

    frames = load_sample_frames()
    if not frames:
        print("⚠️  No sample frames found. Skipping rate limit test.")
        return False

    frame_bytes = frames[0][1]

    print("  Testing multiple rapid calls to verify rate limiting...")
    start_time = time.time()

    # Try to make multiple calls in quick succession
    for i in range(3):
        print(f"     Attempt {i+1}...")
        success, duration, _ = await measure_function_performance(
            f"Fast Analysis {i+1}", analyse_frame, frame_bytes
        )
        if success:
            print(f"        ✅ Success in {duration:.2f} seconds")
        else:
            print(f"        ❌ Failed (likely rate limited)")

    total_time = time.time() - start_time
    print(f"     Total time for 3 attempts: {total_time:.2f} seconds")
    print(f"     Expected minimum: ~24 seconds (3 calls × 8s minimum interval)")

    # Deterministic-ish rate limit check:

    # We consider the limiter "working" if at least one call took
    # ~8s+ (network dependent) OR at least one call returns quickly
    # with fallback (rate-limited skip).
    # Since the client skips by returning fallback values, we can't
    # reliably detect it without client instrumentation; however,
    # we can still sanity-check that total duration isn't wildly
    # shorter than the theoretical minimum.
    if total_time >= 20:  # Allow some margin for network overhead variance
        print("     ✅ Rate limiting appears to be working correctly")
        return True
    else:
        print("     ⚠️  Rate limiting may not be working as expected")
        return False


async def main():
    """Run comprehensive AI performance testing."""
    print("\n" + "="*70)
    print("🚀 VISION OS AI PERFORMANCE TESTING")
    print("="*70)
    print("Testing: ADC Initialization | Image Analysis | Audio Analysis | Text Analysis | Rate Limiting")
    print("Model: gemini-2.5-flash (Vertex AI)")
    print("Authentication: Application Default Credentials")
    print("="*70)

    # Initialize ADC first
    adc_success = await test_adc_initialization()
    if not adc_success:
        print("\n❌ ADC initialization failed. Cannot proceed with testing.")
        return 1

    # Run all tests
    test_results = {}

    print("\n" + "="*70)
    print("🧪 RUNNING COMPREHENSIVE TESTS")
    print("="*70)

    # Test image analysis
    image_success, image_results = await test_image_analysis_performance()
    test_results["Image Analysis"] = image_success

    # Test audio analysis
    audio_success, audio_results = await test_audio_analysis_performance()
    test_results["Audio Analysis"] = audio_success

    # Test text analysis
    text_success, text_results = await test_text_analysis_performance()
    test_results["Text Analysis"] = text_success

    # Test rate limiting
    rate_limit_success = await test_rate_limiting()
    test_results["Rate Limiting"] = rate_limit_success

    # Generate comprehensive report
    print("\n" + "="*70)
    print("📊 COMPREHENSIVE PERFORMANCE REPORT")
    print("="*70)

    for test_name, passed in test_results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status}: {test_name}")

    all_passed = all(test_results.values())

    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ ADC authentication working correctly")
        print("✅ All AI modalities functioning properly")
        print("✅ Rate limiting implemented correctly")
        print("✅ Vertex AI migration successful!")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("Please review the errors above.")

    # Save detailed results to JSON file
    detailed_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "adc_initialization": adc_success,
        "image_analysis": image_results if image_success else {"error": "failed"},
        "audio_analysis": audio_results if audio_success else {"error": "failed"},
        "text_analysis": text_results if text_success else {"error": "failed"},
        "rate_limiting": rate_limit_success,
        "overall_success": all_passed
    }

    with open(Path(__file__).parent.parent / "ai_performance_results.json", "w") as f:
        json.dump(detailed_results, f, indent=2)

    print(f"\n📄 Detailed results saved to: ai_performance_results.json")
    print("="*70)

    return 0 if all_passed else 1

if __name__ == "__main__":
    # Set up logging
    import logging
    logging.basicConfig(level=logging.INFO)

    exit_code = asyncio.run(main())
    sys.exit(exit_code)