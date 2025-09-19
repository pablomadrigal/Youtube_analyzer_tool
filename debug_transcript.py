#!/usr/bin/env python3
"""
Debug script to test transcript fetching directly.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from youtube_transcript_api import YouTubeTranscriptApi

def test_transcript_directly():
    """Test transcript fetching directly with youtube-transcript-api."""
    video_id = "iV5RZ_XKXBc"
    url = "https://www.youtube.com/watch?v=iV5RZ_XKXBc"
    
    print(f"Testing transcript fetching for video ID: {video_id}")
    print(f"URL: {url}")
    
    try:
        # Get transcript list
        print("\n1. Getting transcript list...")
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        print("Available transcripts:")
        for transcript in transcript_list:
            print(f"   - {transcript.language_code} ({'auto' if transcript.is_generated else 'manual'})")
        
        # Try to get English transcript
        print("\n2. Trying to fetch English transcript...")
        try:
            transcript = transcript_list.find_transcript(['en'])
            print(f"Found English transcript: {transcript.language_code} ({'auto' if transcript.is_generated else 'manual'})")
            
            # Fetch the actual transcript
            print("\n3. Fetching transcript data...")
            transcript_data = transcript.fetch()
            print(f"Successfully fetched {len(transcript_data)} segments")
            
            # Show first few segments
            print("\nFirst 3 segments:")
            for i, segment in enumerate(transcript_data[:3]):
                print(f"   {i+1}. [{segment['start']:.1f}s] {segment['text'][:100]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Error fetching English transcript: {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting transcript list: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔍 Debugging Transcript Fetching")
    print("=" * 50)
    
    success = test_transcript_directly()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Transcript fetching works!")
    else:
        print("❌ Transcript fetching failed.")
