#!/usr/bin/env python3
"""
Example script demonstrating the enhanced summarization service with comprehensive prompts.
"""

import asyncio
from services.summarization_service import SummarizationService, SummarizationConfig
from services.transcript_chunker import TranscriptChunker, ChunkingConfig
from models import TranscriptChunk, TranscriptSegment

async def main():
    """Example usage of the enhanced summarization service."""
    
    # Create a sample transcript chunk for demonstration
    sample_transcript = """
    Welcome to this comprehensive video about productivity and time management. Today we're going to explore 
    the most effective frameworks for maximizing your daily output while maintaining work-life balance.
    
    The first framework I want to introduce is the Eisenhower Matrix. This is a powerful tool that helps you 
    categorize tasks based on their urgency and importance. Here's how it works:
    
    Step 1: List all your current tasks and responsibilities.
    Step 2: Categorize each task into one of four quadrants: Urgent and Important, Important but Not Urgent, 
    Urgent but Not Important, and Neither Urgent nor Important.
    Step 3: Focus your energy on Important but Not Urgent tasks to prevent them from becoming urgent.
    
    The second framework is the Pomodoro Technique. This method involves working in focused 25-minute intervals 
    followed by short breaks. The key insight here is that our brains work best in short bursts of intense focus.
    
    Another crucial concept is the 80/20 rule, also known as the Pareto Principle. This states that 80% of 
    your results come from 20% of your efforts. Identifying and focusing on that critical 20% can dramatically 
    increase your productivity.
    
    Time blocking is another essential strategy. This involves scheduling specific time slots for different 
    activities throughout your day. By treating time as a finite resource that needs to be allocated, you 
    can ensure that important tasks get the attention they deserve.
    
    The key to successful productivity is not just about working harder, but working smarter. This means 
    understanding your energy levels, eliminating distractions, and creating systems that support your goals.
    """
    
    # Create transcript segments
    segments = [
        TranscriptSegment(text=sample_transcript.strip(), start=0.0, duration=300.0)
    ]
    
    # Create a transcript chunk
    chunk = TranscriptChunk(
        text=sample_transcript.strip(),
        segments=segments,
        start_time=0.0,
        end_time=300.0,
        token_count=500,
        char_count=2000,
        chunk_index=0,
        language="en"
    )
    
    # Configure the summarization service for comprehensive analysis
    config = SummarizationConfig(
        provider="openai/gpt-4o-mini",
        temperature=0.2,
        max_tokens=2000,
        timeout=60
    )
    
    summarizer = SummarizationService(config)
    
    print("🔍 Analyzing transcript with enhanced prompts...")
    print("=" * 60)
    
    # Generate summary
    summary_data, error = await summarizer.summarize_transcript([chunk], "en")
    
    if error:
        print(f"❌ Error: {error.message}")
        return
    
    print("✅ Summary generated successfully!")
    print("\n" + "=" * 60)
    print("📊 SUMMARY DATA")
    print("=" * 60)
    
    print(f"\n📝 Executive Summary:")
    print(summary_data.summary)
    
    print(f"\n💡 Key Insights ({len(summary_data.key_insights)}):")
    for i, insight in enumerate(summary_data.key_insights, 1):
        print(f"\n{i}. {insight}")
    
    print(f"\n🔧 Frameworks ({len(summary_data.frameworks)}):")
    for framework in summary_data.frameworks:
        print(f"\n• {framework.name}")
        print(f"  Description: {framework.description}")
        print(f"  Steps: {len(framework.steps)} steps")
        for j, step in enumerate(framework.steps, 1):
            print(f"    {j}. {step}")
    
    print(f"\n⏰ Key Moments ({len(summary_data.key_moments)}):")
    for i, moment in enumerate(summary_data.key_moments, 1):
        print(f"{i}. {moment}")
    
    # Generate markdown
    print("\n" + "=" * 60)
    print("📄 MARKDOWN OUTPUT")
    print("=" * 60)
    
    markdown = summarizer.generate_markdown_summary(
        summary_data, 
        language="en",
        video_title="Productivity and Time Management Masterclass",
        video_url="https://youtube.com/watch?v=example"
    )
    
    print(markdown)
    
    # Save markdown to file
    with open("example_summary.md", "w", encoding="utf-8") as f:
        f.write(markdown)
    
    print(f"\n💾 Markdown saved to 'example_summary.md'")

if __name__ == "__main__":
    asyncio.run(main())
