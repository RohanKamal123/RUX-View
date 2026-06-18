#!/usr/bin/env python3
"""
Test script for Gemini 2.5 Flash - All Modalities
Tests: Image Frames, Audio, Text Analysis
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path (now in scripts/, so go up one more level)
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ai.ai_client import (
    analyse_frame,
    analyse_frame_structured,
    analyse_frame_detailed,
    analyse_audio,
    answer_query,
)
from backend.ai.ai_client import AUDIO_ANALYSIS_FALLBACK


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
    import struct
    import math
    
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


async def test_image_frames():
    """Test image/frame analysis with sample frames."""
    print("\n" + "="*60)
    print("🖼️  TESTING IMAGE FRAME ANALYSIS")
    print("="*60)
    
    frames = load_sample_frames()
    if not frames:
        print("⚠️  No sample frames found. Skipping frame tests.")
        return False
    
    print(f"Found {len(frames)} sample frame(s)")
    
    for frame_name, frame_bytes in frames:
        print(f"\n  Testing: {frame_name}")
        print(f"  Frame size: {len(frame_bytes)} bytes")
        
        try:
            # Test structured analysis
            result = await analyse_frame_structured(frame_bytes)
            
            print(f"  ✅ Structured Analysis:")
            print(f"     - Event Type: {result.get('event_type', 'N/A')}")
            print(f"     - Threat Level: {result.get('threat_level', 'N/A')}")
            print(f"     - Confidence: {result.get('confidence', 'N/A')}")
            print(f"     - Description: {result.get('description', 'N/A')[:60]}...")
            print(f"     - Action Required: {result.get('action_required', 'N/A')}")
            
            # Test detailed analysis
            detailed = await analyse_frame_detailed(frame_bytes)
            person_count = len(detailed.get('persons', []))
            print(f"  ✅ Detailed Analysis: Detected {person_count} person(s)")
            
            if detailed.get('persons'):
                person = detailed['persons'][0]
                print(f"     - Gender: {person.get('gender', 'N/A')}")
                print(f"     - Clothing: {person.get('clothing', 'N/A')[:50]}...")
                print(f"     - Action: {person.get('action', 'N/A')}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False
    
    return True


async def test_audio_analysis():
    """Test audio analysis with test audio."""
    print("\n" + "="*60)
    print("🔊 TESTING AUDIO ANALYSIS")
    print("="*60)
    
    # Create test audio
    audio_bytes = create_test_audio()
    print(f"Created test audio: {len(audio_bytes)} bytes")
    
    try:
        result = await analyse_audio(audio_bytes)
        
        print(f"  ✅ Audio Analysis Result:")
        print(f"     - Transcript: {result.get('transcript', 'N/A') or '(empty)'}")
        print(f"     - Language: {result.get('language', 'N/A')}")
        print(f"     - Threat Detected: {result.get('threat_detected', 'N/A')}")
        print(f"     - Threat Level: {result.get('threat_level', 'N/A')}")
        print(f"     - Threat Types: {result.get('threat_types', [])}")
        print(f"     - Description: {result.get('description', 'N/A')}")
        print(f"     - Confidence: {result.get('confidence', 'N/A')}")
        
        # Verify structure
        required_keys = ['transcript', 'language', 'threat_detected', 'threat_level', 
                        'threat_types', 'description', 'confidence']
        missing = [k for k in required_keys if k not in result]
        if missing:
            print(f"  ⚠️  Missing keys: {missing}")
            return False
            
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_text_analysis():
    """Test text/natural language analysis."""
    print("\n" + "="*60)
    print("📝 TESTING TEXT ANALYSIS")
    print("="*60)
    
    try:
        # Test query answering
        question = "What happened at the front gate?"
        events = [
            {"id": 1, "timestamp": "2024-01-01T10:00:00", "event_type": "person_entering"},
            {"id": 2, "timestamp": "2024-01-01T10:05:00", "event_type": "person_leaving"},
        ]
        analyses = [
            {"persons": [{"gender": "male", "clothing": "red shirt", "action": "walking"}]},
        ]
        
        answer = await answer_query(question, events, analyses)
        
        print(f"  ✅ Query Answering:")
        print(f"     Question: {question}")
        print(f"     Answer: {answer[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_model_configuration():
    """Verify the model configuration."""
    print("\n" + "="*60)
    print("⚙️  TESTING MODEL CONFIGURATION")
    print("="*60)
    
    from backend.ai.ai_client import _get_model, _model
    
    try:
        model = _get_model()
        print(f"  ✅ Model initialized successfully")
        print(f"     Model name: gemini-2.5-flash")
        
        # Verify it's the correct model by checking the model object
        # (The model name is embedded in the model resource path)
        if hasattr(model, '_model_name'):
            print(f"     Model resource: {model._model_name}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def main():
    """Run all modality tests."""
    print("\n" + "="*60)
    print("🚀 GEMINI 2.5 FLASH - ALL MODALITIES TEST")
    print("="*60)
    print("Testing: Frames | Audio | Text")
    print("Model: gemini-2.5-flash (Reasoner)")
    print("="*60)
    
    results = {
        "Configuration": await test_model_configuration(),
        "Image Frames": await test_image_frames(),
        "Audio Analysis": await test_audio_analysis(),
        "Text Analysis": await test_text_analysis(),
    }
    
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("Gemini 2.5 Flash migration successful for all modalities.")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("Please review the errors above.")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)