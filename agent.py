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

    def _is_output_incomplete(self, text: str) -> bool:
        """
        Check if the output appears to be truncated or incomplete

        Args:
            text: The analysis text to check

        Returns:
            True if output appears incomplete
        """
        # Check for common signs of truncation
        truncation_indicators = [
            text.endswith('#'),  # Cut off mid-number reference
            text.endswith('*'),  # Cut off mid-markdown
            text.count('*') % 2 != 0,  # Odd number of asterisks (unclosed markdown)
            len(text) < 50,  # Suspiciously short
            text.strip().endswith(':'),  # Ends with colon (incomplete list)
            '**' in text and text.rfind('**') > len(text) - 20,  # Unclosed bold near end
        ]

        return any(truncation_indicators)

    def analyze_video_segment(
        self,
        video_uri: str,
        start_sec: float,
        end_sec: float,
        previous_context: Optional[str] = None
    ) -> str:
        """
        Analyze a specific segment of the basketball video

        Args:
            video_uri: GCS URI of the video (gs://bucket/path)
            start_sec: Start time in seconds
            end_sec: End time in seconds
            previous_context: Analysis from the previous segment (for continuity)

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

            # Build context section if we have previous segment
            context_section = ""
            if previous_context:
                # Truncate to avoid token bloat
                context_summary = previous_context[:500] + "..." if len(previous_context) > 500 else previous_context
                context_section = f"""
**Previous Segment Context:**
{context_summary}

Use this context to maintain continuity (e.g., if previous was warmup and you see tip-off, note "Game begins").
---

"""

            # Create the prompt - use POSITIVE indicators the model can actually see
            prompt = f"""{context_section}Analyze this basketball segment from {start_sec} to {end_sec} seconds.

CRITICAL: First determine if this is WARMUP or ACTUAL GAME PLAY.

**Step 1 - GAME vs WARMUP Classification:**

Look for these POSITIVE indicators:

**ACTUAL GAME PLAY** - Check for ANY of these:
✅ **Jump ball / tip-off happening**: Two players jumping for the ball at center court
✅ **Organized 5v5 action**: One team actively defending while other team has possession
✅ **Continuous competitive play**: Ball possession changing, players guarding opponents
✅ **Referee signals**: Refs making calls, pointing, signaling fouls/violations
✅ **Fast break action**: Team running coordinated offense after getting the ball

**WARMUP / SHOOTAROUND** - Check for ANY of these:
✅ **Layup lines**: Players in line taking turns shooting layups
✅ **Multiple simultaneous shooters**: Several players shooting at once from different spots
✅ **Solo shooting practice**: Individual players taking shots with nobody guarding them
✅ **Drill patterns**: Repetitive practice movements (passing drills, shooting drills)
✅ **Casual movement**: Players walking, standing around between shots

**Classification Decision:**
- If you see ANY "Actual Game" indicators → Tag as **[GAME]**
- If you see ANY "Warmup" indicators AND zero "Actual Game" indicators → Tag as **[WARMUP]**
- If unclear, default to **[WARMUP]** to be safe

**Step 2 - Analysis:**

**If [WARMUP]:**
- State clearly: "This segment shows warmup/practice activity."
- BUT still note spectacular moments:
  - Half-court shots made
  - Impressive dunks
  - Format: "WARMUP - [time]: [description]"

**If [GAME]:**
Provide factual play-by-play:

1. **Scoring Plays**: Shots made/missed (type: layup/dunk/jumper/3-pointer), which team
2. **Defensive Actions**: Blocks, steals, rebounds
3. **Game Flow**: Turnovers, fouls, fast breaks
4. **Key Moments**: Game-changing plays

**Format Requirements:**
- Start with classification tag: [GAME] or [WARMUP]
- Be concise and factual
- Timestamp key events
- Focus on observable actions, not inferences"""

            # Generate content with LOW temperature for factual accuracy
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, video_part],
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Low creativity - factual play-by-play
                    max_output_tokens=4096,  # Increased from 2048 for complete coverage
                )
            )

            result = response.text

            # Log token usage for debugging
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                logger.info(f"Segment {start_sec}-{end_sec}s token usage:")
                logger.info(f"  - Prompt tokens: {usage.prompt_token_count if hasattr(usage, 'prompt_token_count') else 'N/A'}")
                logger.info(f"  - Video tokens: Included in prompt tokens")
                logger.info(f"  - Output tokens: {usage.candidates_token_count if hasattr(usage, 'candidates_token_count') else 'N/A'}")
                logger.info(f"  - Total tokens: {usage.total_token_count if hasattr(usage, 'total_token_count') else 'N/A'}")
            else:
                logger.warning(f"No usage metadata available for segment {start_sec}-{end_sec}s")

            # Validate output quality
            if self._is_output_incomplete(result):
                logger.warning(f"Segment {start_sec}-{end_sec}s appears to have incomplete output")
                # Add warning to result
                result = f"{result}\n\n⚠️ [Note: This segment analysis may be incomplete. Consider using shorter chunk sizes.]"

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
1. Break down the video into manageable segments (typically 60 seconds for optimal quality)
2. Use the analyze_video_segment tool to examine each segment thoroughly
3. Create a detailed play-by-play log of key events
4. Identify highlight-worthy moments (dunks, three-pointers, blocks, steals, spectacular plays)
5. Provide strategic insights about team performance

IMPORTANT: Provide complete, thorough analysis for each segment. Don't cut off mid-sentence or leave analysis incomplete.

Always be thorough, systematic, and professional in your analysis.
Focus on actionable insights that coaches and players can use to improve."""

    def analyze_full_video_stream(
        self,
        video_uri: str,
        duration_seconds: Optional[int] = None,
        chunk_size: int = 120,
        start_offset: int = 0
    ):
        """
        Analyze a full basketball game video with streaming progress updates

        Args:
            video_uri: GCS URI of the video
            duration_seconds: Total video duration to analyze (if None, assumes 10 minutes)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)
            start_offset: Start time in seconds (skip this much from beginning)

        Yields:
            Progress dictionaries with status updates and results
        """
        logger.info(f"Starting full video analysis of {video_uri} from {start_offset}s")

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
            # Add start_offset to all times
            start_sec = start_offset + (i * chunk_size)
            end_sec = start_offset + min((i + 1) * chunk_size, duration_seconds)

            yield {
                "status": "processing",
                "message": f"Analyzing segment {i + 1}/{num_chunks} ({start_sec}-{end_sec}s)",
                "segment": i + 1,
                "total_segments": num_chunks,
                "progress": (i / num_chunks) * 100
            }

            # Get previous segment analysis for context (if exists)
            previous_context = analyses[-1]["analysis"] if analyses else None

            chunk_analysis = self.video_tool.analyze_video_segment(
                video_uri=video_uri,
                start_sec=start_sec,
                end_sec=end_sec,
                previous_context=previous_context
            )

            # Note: Token usage is logged in the segment analysis method

            analyses.append({
                "segment": i + 1,
                "start_time": start_sec,
                "end_time": end_sec,
                "analysis": chunk_analysis
            })

            # Extract highlights (including warmup spectacular moments)
            is_highlight = any(keyword in chunk_analysis.lower() for keyword in
                   ["dunk", "three-pointer", "block", "steal", "highlight",
                    "half-court", "warmup -", "spectacular", "impressive", "[game]"])

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
                    max_output_tokens=6144,  # Increased from 3072 for comprehensive summaries
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
        chunk_size: int = 120,
        start_offset: int = 0
    ) -> Dict[str, Any]:
        """
        Analyze a full basketball game video (non-streaming version)

        Args:
            video_uri: GCS URI of the video
            duration_seconds: Total video duration (if None, assumes 10 minutes)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)
            start_offset: Start time in seconds (skip this much from beginning)

        Returns:
            Dictionary containing play-by-play analysis, highlights, and stats
        """
        # Use the streaming version and collect the final result
        result = None
        for update in self.analyze_full_video_stream(video_uri, duration_seconds, chunk_size, start_offset):
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
