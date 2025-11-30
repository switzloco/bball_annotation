"""
Basketball Video Analysis Agent using Google ADK (google-genai)
"""
import os
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoAnalysisTool:
    """Custom tool for analyzing video segments using Gemini multimodal capabilities"""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """
        Initialize the video analysis tool

        Args:
            model_name: The Gemini model to use for analysis
        """
        self.model_name = model_name
        self.client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION", "us-central1")
        )

    def analyze_video_segment(
        self,
        video_uri: str,
        start_sec: float,
        end_sec: float
    ) -> str:
        """
        Analyze a specific segment of the basketball video

        Args:
            video_uri: GCS URI of the video (gs://bucket/path)
            start_sec: Start time in seconds
            end_sec: End time in seconds

        Returns:
            Analysis text from Gemini
        """
        logger.info(f"Analyzing segment {start_sec}-{end_sec}s of {video_uri}")

        try:
            # Create the video part with time offset
            video_part = types.Part.from_uri(
                file_uri=video_uri,
                mime_type="video/mp4"
            )

            # Create the prompt - focus on real game action only
            prompt = f"""Analyze this basketball game segment from {start_sec} to {end_sec} seconds.

IMPORTANT: Only analyze actual game play. Ignore warmups, shootarounds, dead ball situations, timeouts, and between-play activities.

Provide a factual, objective play-by-play description:

1. **Live Game Action Only**:
   - Scoring plays (shots, layups, dunks, free throws)
   - Defensive plays (blocks, steals, rebounds)
   - Turnovers and fouls during active play
   - Fast breaks and transitions

2. **What to SKIP**:
   - Pre-game warmups or shootarounds
   - Players standing around during stoppages
   - Timeouts or huddles
   - Between-quarter breaks
   - Ball out of bounds (unless part of active play)

3. **Format**:
   - Be concise and factual
   - Focus on what actually happened, not speculation
   - Use objective language
   - Timestamp key events when possible

If this segment contains no actual game play, simply state: "No active game play in this segment."

Format your response as a clear play-by-play log."""

            # Generate content with LOW temperature for factual accuracy
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, video_part],
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Low creativity - factual play-by-play
                    max_output_tokens=2048,
                )
            )

            result = response.text
            logger.info(f"Successfully analyzed segment {start_sec}-{end_sec}s")
            return result

        except Exception as e:
            error_msg = f"Error analyzing segment {start_sec}-{end_sec}s: {str(e)}"
            logger.error(error_msg)
            return error_msg


class CoachAI:
    """
    Basketball Analysis Agent using Google ADK

    This agent acts as an expert basketball analyst that can break down game footage
    into play-by-play analysis and identify highlight moments.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """
        Initialize the CoachAI agent

        Args:
            model_name: The Gemini model to use (default: gemini-2.5-flash-lite)
        """
        self.model_name = model_name
        self.video_tool = VideoAnalysisTool(model_name=model_name)
        self.client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION", "us-central1")
        )

        # Agent system instructions
        self.system_instruction = """You are CoachAI, an expert basketball analyst with deep knowledge of the game.

Your mission is to analyze basketball game videos systematically and provide comprehensive insights.

When analyzing a video:
1. Break down the video into 2-minute segments (120 seconds)
2. Use the analyze_video_segment tool to examine each segment
3. Create a play-by-play log of key events
4. Identify highlight-worthy moments (dunks, three-pointers, blocks, steals, etc.)
5. Provide strategic insights about team performance

Always be thorough, systematic, and professional in your analysis.
Focus on actionable insights that coaches and players can use to improve."""

    def analyze_full_video_stream(
        self,
        video_uri: str,
        duration_seconds: Optional[int] = None,
        chunk_size: int = 120
    ):
        """
        Analyze a full basketball game video with streaming progress updates

        Args:
            video_uri: GCS URI of the video
            duration_seconds: Total video duration (if None, assumes 10 minutes)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)

        Yields:
            Progress dictionaries with status updates and results
        """
        logger.info(f"Starting full video analysis of {video_uri}")

        # Default to 10 minutes if not specified
        if duration_seconds is None:
            duration_seconds = 600

        # Calculate number of chunks
        num_chunks = (duration_seconds + chunk_size - 1) // chunk_size

        yield {
            "status": "initialized",
            "message": f"Starting analysis of {num_chunks} segments",
            "num_chunks": num_chunks,
            "duration_seconds": duration_seconds
        }

        analyses = []
        highlights = []

        # Analyze each chunk
        for i in range(num_chunks):
            start_sec = i * chunk_size
            end_sec = min((i + 1) * chunk_size, duration_seconds)

            yield {
                "status": "processing",
                "message": f"Analyzing segment {i + 1}/{num_chunks} ({start_sec}-{end_sec}s)",
                "segment": i + 1,
                "total_segments": num_chunks,
                "progress": (i / num_chunks) * 100
            }

            chunk_analysis = self.video_tool.analyze_video_segment(
                video_uri=video_uri,
                start_sec=start_sec,
                end_sec=end_sec
            )

            analyses.append({
                "segment": i + 1,
                "start_time": start_sec,
                "end_time": end_sec,
                "analysis": chunk_analysis
            })

            # Extract highlights (simplified - could use LLM to identify)
            is_highlight = any(keyword in chunk_analysis.lower() for keyword in
                   ["dunk", "three-pointer", "block", "steal", "highlight"])

            if is_highlight:
                highlights.append({
                    "time": f"{start_sec}-{end_sec}s",
                    "description": chunk_analysis[:200] + "..."
                })

            yield {
                "status": "segment_complete",
                "message": f"Completed segment {i + 1}/{num_chunks}",
                "segment": i + 1,
                "total_segments": num_chunks,
                "progress": ((i + 1) / num_chunks) * 90,  # Save 10% for summary
                "segment_data": analyses[-1],
                "highlight_found": is_highlight
            }

        # Compile final report using LLM
        yield {
            "status": "compiling",
            "message": "Generating comprehensive game summary...",
            "progress": 95
        }

        compilation_prompt = f"""Based on these play-by-play segment analyses, provide a comprehensive strategic game summary with creative insights:

{chr(10).join([f"Segment {a['segment']} ({a['start_time']}-{a['end_time']}s): {a['analysis']}" for a in analyses])}

Your task is to provide HIGH-LEVEL STRATEGIC ANALYSIS with creativity and insight:

1. **Overall Game Narrative**:
   - What was the story of this game?
   - How did momentum shift?
   - What defined each team's approach?

2. **Strategic Insights** (be creative and analytical):
   - Offensive patterns and effectiveness
   - Defensive schemes and adjustments
   - Coaching decisions and their impact
   - Player matchups and advantages

3. **Key Turning Points**:
   - Identify 2-3 moments that changed the game
   - Explain WHY they mattered strategically

4. **Top 5 Highlights**:
   - Most impactful plays from a game perspective
   - Not just flashy, but game-changing

5. **Actionable Takeaways**:
   - What could coaches learn from this?
   - Areas for improvement
   - Successful strategies to replicate

Be insightful, creative, and provide depth beyond just describing what happened. Focus on the "why" and "how" of the game."""

        try:
            summary_response = self.client.models.generate_content(
                model=self.model_name,
                contents=compilation_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.8,  # High creativity - strategic insights
                    max_output_tokens=3072,
                )
            )
            game_summary = summary_response.text
        except Exception as e:
            game_summary = f"Error generating summary: {str(e)}"

        # Final result
        final_result = {
            "video_uri": video_uri,
            "duration_seconds": duration_seconds,
            "num_segments": num_chunks,
            "segment_analyses": analyses,
            "highlights": highlights,
            "game_summary": game_summary
        }

        yield {
            "status": "complete",
            "message": "Analysis complete!",
            "progress": 100,
            "result": final_result
        }

    def analyze_full_video(
        self,
        video_uri: str,
        duration_seconds: Optional[int] = None,
        chunk_size: int = 120
    ) -> Dict[str, Any]:
        """
        Analyze a full basketball game video (non-streaming version)

        Args:
            video_uri: GCS URI of the video
            duration_seconds: Total video duration (if None, assumes 10 minutes)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)

        Returns:
            Dictionary containing play-by-play analysis, highlights, and stats
        """
        # Use the streaming version and collect the final result
        result = None
        for update in self.analyze_full_video_stream(video_uri, duration_seconds, chunk_size):
            if update.get("status") == "complete":
                result = update.get("result")
        return result

    def chat(self, message: str, video_uri: Optional[str] = None) -> str:
        """
        Interactive chat with the CoachAI agent

        Args:
            message: User message
            video_uri: Optional video URI for context

        Returns:
            Agent response
        """
        contents = [message]

        if video_uri:
            video_part = types.Part.from_uri(
                file_uri=video_uri,
                mime_type="video/mp4"
            )
            contents.append(video_part)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.6,
                    max_output_tokens=2048,
                )
            )
            return response.text
        except Exception as e:
            return f"Error: {str(e)}"


def create_coach_agent(model_name: str = "gemini-2.5-flash-lite") -> CoachAI:
    """
    Factory function to create a CoachAI agent instance

    Args:
        model_name: The Gemini model to use

    Returns:
        Initialized CoachAI agent
    """
    return CoachAI(model_name=model_name)
