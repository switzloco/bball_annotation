"""
Basketball Video Analysis Agent using Google ADK (google-genai)
"""
import os
import re
import subprocess
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from google.cloud import storage
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

    def _parse_shots(self, analysis_text: str) -> List[Dict[str, Any]]:
        """
        Parse shot data from analysis text

        Args:
            analysis_text: The analysis text containing SHOT: entries

        Returns:
            List of shot dictionaries with timestamp, player, type, result
        """
        shots = []

        # Pattern: SHOT: 5s - Tall player white jersey #23 - layup - MADE
        pattern = r'SHOT:\s*(\d+)s\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*(MADE|MISSED)'

        for match in re.finditer(pattern, analysis_text, re.IGNORECASE):
            timestamp = int(match.group(1))
            player_desc = match.group(2).strip()
            shot_type = match.group(3).strip().lower()
            result = match.group(4).strip().upper()

            shots.append({
                "timestamp": timestamp,
                "player": player_desc,
                "shot_type": shot_type,
                "made": result == "MADE"
            })

        return shots

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

            # Create the prompt - focus on shot enumeration for shots/min analysis
            prompt = f"""{context_section}Analyze this basketball segment from {start_sec} to {end_sec} seconds.

**PRIMARY TASK: Enumerate EVERY shot attempt you observe.**

**SHOT FORMAT (use this exact format for EVERY shot):**
SHOT: [timestamp]s - [Player description] - [shot_type] - [MADE/MISSED]

Where:
- timestamp: Seconds into the video when shot was released
- Player description: Brief visual (jersey color, number if visible, height, identifying features)
- shot_type: One of: layup, dunk, floater, mid-range, three-pointer, free-throw
- MADE/MISSED: Whether the shot went in

**Examples:**
SHOT: 5s - Tall player white jersey #23 - layup - MADE
SHOT: 12s - Short player red jersey - three-pointer - MISSED
SHOT: 18s - Player blue jersey dark skin - mid-range - MADE

**CRITICAL: List ALL shots, even in warmups/shootarounds!**

After listing all shots, provide:

**GAME CONTEXT:**
Indicate if this is [GAME] or [WARMUP] based on these indicators:

**ACTUAL GAME PLAY** - Check for ANY of these:
✅ Jump ball / tip-off happening
✅ Organized 5v5 action with active defense
✅ Continuous competitive play, ball possession changing
✅ Referee signals and active officiating
✅ Fast break action
✅ Game clock running (visible clock counting down)

**WARMUP / SHOOTAROUND / DEAD BALL** - Check for ANY of these:
✅ Layup lines
✅ Multiple simultaneous shooters
✅ Solo shooting practice (no defenders)
✅ Drill patterns
✅ Casual movement between shots
✅ **Game clock stopped at 0:00 or not visible**
✅ **Clock visible but not running** (dead ball, timeout, halftime)

**OTHER NOTABLE EVENTS:**
- Defensive plays: blocks, steals, rebounds
- Turnovers, fouls
- Spectacular plays (dunks, half-court shots)

**OUTPUT FORMAT:**
1. Classification tag: [GAME] or [WARMUP]
2. List ALL shots using SHOT: format above
3. Brief context/notable events
4. Be factual, timestamp everything"""

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

    def get_video_duration(self, video_uri: str) -> Optional[int]:
        """
        Get video duration in seconds from GCS URI using ffprobe

        Args:
            video_uri: GCS URI (gs://bucket/path/to/video.mp4)

        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            # Parse GCS URI
            if not video_uri.startswith("gs://"):
                logger.error(f"Invalid GCS URI: {video_uri}")
                return None

            # Extract bucket and blob path
            uri_parts = video_uri[5:].split("/", 1)
            bucket_name = uri_parts[0]
            blob_path = uri_parts[1] if len(uri_parts) > 1 else ""

            # Create signed URL for temporary access
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            # Generate signed URL (valid for 5 minutes)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=300,  # 5 minutes
                method="GET"
            )

            # Use ffprobe to get duration
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                signed_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                duration = float(result.stdout.strip())
                logger.info(f"Detected video duration: {duration:.1f} seconds")
                return int(duration)
            else:
                logger.error(f"ffprobe error: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error getting video duration: {e}")
            return None

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
            duration_seconds: Total video duration to analyze (if None, auto-detects from video)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)
            start_offset: Start time in seconds (skip this much from beginning)

        Yields:
            Progress dictionaries with status updates and results
        """
        logger.info(f"Starting full video analysis of {video_uri} from {start_offset}s")

        # Auto-detect duration if not specified
        if duration_seconds is None:
            yield {
                "status": "detecting_duration",
                "message": "Detecting video duration..."
            }
            duration_seconds = self.get_video_duration(video_uri)

            if duration_seconds is None:
                # Fallback to 10 minutes if detection fails
                logger.warning("Could not detect video duration, defaulting to 600 seconds")
                duration_seconds = 600
            else:
                logger.info(f"Auto-detected video duration: {duration_seconds}s")

        # Calculate number of chunks
        # If video is shorter than chunk_size, use video length as chunk size
        effective_chunk_size = min(chunk_size, duration_seconds)
        num_chunks = (duration_seconds + effective_chunk_size - 1) // effective_chunk_size

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
            start_sec = start_offset + (i * effective_chunk_size)
            end_sec = start_offset + min((i + 1) * effective_chunk_size, duration_seconds)

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

            # Parse shots from the analysis
            shots = self.video_tool._parse_shots(chunk_analysis)

            # Calculate shots per minute
            segment_duration_min = (end_sec - start_sec) / 60.0
            shots_per_minute = len(shots) / segment_duration_min if segment_duration_min > 0 else 0

            # Extract initial classification from analysis
            initial_classification = "WARMUP"  # default
            if "[GAME]" in chunk_analysis.upper():
                initial_classification = "GAME"
            elif "[WARMUP]" in chunk_analysis.upper():
                initial_classification = "WARMUP"

            analyses.append({
                "segment": i + 1,
                "start_time": start_sec,
                "end_time": end_sec,
                "analysis": chunk_analysis,
                "shots": shots,
                "shots_per_minute": round(shots_per_minute, 1),
                "initial_classification": initial_classification,
                "final_classification": initial_classification  # Will be updated later
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

        # Apply retroactive classification based on shots/minute heuristic
        logger.info("Applying retroactive classification based on shots per minute...")
        for analysis in analyses:
            spm = analysis["shots_per_minute"]
            initial = analysis["initial_classification"]

            # Heuristic thresholds
            # Warmup: High shot frequency (10+ shots/min) - everyone shooting casually
            # Game: Lower shot frequency (2-8 shots/min) - possession-based play
            if spm >= 10:
                # Very high shot rate = definitely warmup
                analysis["final_classification"] = "WARMUP"
                if initial != "WARMUP":
                    logger.info(f"Segment {analysis['segment']}: Overriding {initial} → WARMUP (shots/min={spm})")
            elif spm <= 2 and spm > 0:
                # Very low shot rate = likely game (slow, defensive play)
                analysis["final_classification"] = "GAME"
                if initial != "GAME":
                    logger.info(f"Segment {analysis['segment']}: Overriding {initial} → GAME (shots/min={spm})")
            elif 2 < spm < 6:
                # Moderate-low rate = likely game (normal game pace)
                analysis["final_classification"] = "GAME"
                if initial != "GAME":
                    logger.info(f"Segment {analysis['segment']}: Overriding {initial} → GAME (shots/min={spm})")
            elif 6 <= spm < 10:
                # Moderate-high rate = could be either, trust model
                analysis["final_classification"] = initial
                logger.info(f"Segment {analysis['segment']}: Keeping {initial} (shots/min={spm} - ambiguous)")
            else:
                # Keep original classification
                analysis["final_classification"] = initial

            # Update the analysis text with classification override if changed
            if analysis["final_classification"] != analysis["initial_classification"]:
                override_note = f"\n\n**[RETROACTIVE CLASSIFICATION: {analysis['final_classification']} based on {spm} shots/min]**"
                analysis["analysis"] = analysis["analysis"] + override_note

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
