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

    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
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

            # Create the prompt
            prompt = f"""Analyze this basketball game segment from {start_sec} to {end_sec} seconds.

Provide a detailed play-by-play analysis including:
1. Key plays and scoring moments
2. Player movements and positioning
3. Defensive and offensive strategies
4. Notable events (fouls, turnovers, substitutions)
5. Highlight-worthy moments

Format your response as a structured breakdown."""

            # Generate content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, video_part],
                config=types.GenerateContentConfig(
                    temperature=0.4,
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

    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize the CoachAI agent

        Args:
            model_name: The Gemini model to use (default: gemini-2.0-flash-exp)
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

    def analyze_full_video(
        self,
        video_uri: str,
        duration_seconds: Optional[int] = None,
        chunk_size: int = 120
    ) -> Dict[str, Any]:
        """
        Analyze a full basketball game video

        Args:
            video_uri: GCS URI of the video
            duration_seconds: Total video duration (if None, assumes 10 minutes)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)

        Returns:
            Dictionary containing play-by-play analysis, highlights, and stats
        """
        logger.info(f"Starting full video analysis of {video_uri}")

        # Default to 10 minutes if not specified
        if duration_seconds is None:
            duration_seconds = 600

        # Calculate number of chunks
        num_chunks = (duration_seconds + chunk_size - 1) // chunk_size

        analyses = []
        highlights = []

        # Analyze each chunk
        for i in range(num_chunks):
            start_sec = i * chunk_size
            end_sec = min((i + 1) * chunk_size, duration_seconds)

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
            if any(keyword in chunk_analysis.lower() for keyword in
                   ["dunk", "three-pointer", "block", "steal", "highlight"]):
                highlights.append({
                    "time": f"{start_sec}-{end_sec}s",
                    "description": chunk_analysis[:200] + "..."
                })

        # Compile final report using LLM
        compilation_prompt = f"""Based on these segment analyses, create a comprehensive game summary:

{chr(10).join([f"Segment {a['segment']} ({a['start_time']}-{a['end_time']}s): {a['analysis']}" for a in analyses])}

Provide:
1. Overall game summary
2. Key turning points
3. Top 5 highlights
4. Performance insights"""

        try:
            summary_response = self.client.models.generate_content(
                model=self.model_name,
                contents=compilation_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.5,
                    max_output_tokens=3072,
                )
            )
            game_summary = summary_response.text
        except Exception as e:
            game_summary = f"Error generating summary: {str(e)}"

        return {
            "video_uri": video_uri,
            "duration_seconds": duration_seconds,
            "num_segments": num_chunks,
            "segment_analyses": analyses,
            "highlights": highlights,
            "game_summary": game_summary
        }

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


def create_coach_agent(model_name: str = "gemini-2.0-flash-exp") -> CoachAI:
    """
    Factory function to create a CoachAI agent instance

    Args:
        model_name: The Gemini model to use

    Returns:
        Initialized CoachAI agent
    """
    return CoachAI(model_name=model_name)
