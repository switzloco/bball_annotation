"""
Basketball Video Analysis Streamlit App
"""
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import storage
from agent import create_coach_agent
import logging
import time
import json
from datetime import datetime

# Version
__version__ = "3.0.0"  # Feature: Hybrid Tiled-Vision Pipeline (Two-Pass Architecture)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Utility functions
def format_timestamp(seconds):
    """Convert seconds to MM:SS format for human-readable timestamps"""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"

def render_video_player_with_events(video_uri, result, selected_sport):
    """
    Render video player with clickable event timestamps (fault-tolerant)

    Args:
        video_uri: GCS URI for the video
        result: Analysis result dictionary with events
        selected_sport: Sport type (basketball/ultimate)
    """
    try:
        st.divider()
        with st.expander("🎥 Video Player with Event Navigation", expanded=False):
            st.caption("Click any timestamp below to jump to that moment in the video")

            # Try to render video player
            try:
                # Generate signed URL for playback (st.video doesn't support gs:// URIs)
                if video_uri.startswith("gs://"):
                    playback_url = generate_signed_playback_url(video_uri)
                    st.video(playback_url)
                else:
                    # Already an HTTPS URL
                    st.video(video_uri)
            except Exception as video_error:
                error_str = str(video_error)
                st.warning(f"⚠️ Could not load video player")

                # Provide helpful context for common errors
                if "private key" in error_str or "credentials" in error_str:
                    st.info("💡 **Note:** Video playback requires service account credentials with signing permissions. " +
                           "Compute Engine credentials don't support URL signing. The clickable event timestamps below still work!")
                else:
                    st.info(f"💡 Video playback unavailable: {error_str}")

                st.caption("You can still use the clickable timestamps below to navigate - just copy the time and jump manually in your video player.")

            # Collect all events from all segments
            all_events = []
            for segment in result.get("segment_analyses", []):
                events = segment.get("events", [])
                all_events.extend(events)

            # Sort events by timestamp
            all_events.sort(key=lambda e: e.get('timestamp', 0))

            if all_events:
                st.markdown("### 🎯 Quick Jump to Events")

                # Create unique ID for this video player
                player_id = "video_player_" + str(hash(video_uri))[:8]

                # Render clickable event list
                event_lines = []
                for event in all_events:
                    timestamp_sec = event.get('timestamp', 0)
                    timestamp_str = format_timestamp(timestamp_sec)

                    # Create event description based on sport
                    if selected_sport == "basketball":
                        if event.get('shot_type'):
                            result_icon = "✅" if event.get('made') else "❌"
                            desc = f"{result_icon} {event.get('player')} - {event.get('shot_type')} - {'MADE' if event.get('made') else 'MISSED'}"
                            event_lines.append(f'<a href="#" onclick="seekToTime({timestamp_sec}); return false;" style="text-decoration: none; color: inherit;">{timestamp_str} - {desc}</a>')
                    elif selected_sport == "ultimate":
                        event_type = event.get('type', '').upper()
                        player = event.get('player', 'Unknown')

                        if event_type == "GOAL":
                            desc = f"⚽ GOAL - {player}"
                        elif event_type == "CATCH":
                            catch_type = event.get('catch_type', 'catch')
                            success = "✅" if event.get('success') else "❌"
                            desc = f"🙌 CATCH - {player} - {catch_type} - {success}"
                        elif event_type == "LAYOUT":
                            success = "✅" if event.get('success') else "❌"
                            desc = f"🤸 LAYOUT - {player} - {success}"
                        elif event_type == "DEFLECTION":
                            desc = f"✋ DEFLECTION - {player}"
                        elif event_type == "BLOCK":
                            desc = f"🛡️ BLOCK - {player}"
                        elif event_type == "TURNOVER":
                            desc = f"🔄 TURNOVER - {event.get('turnover_type', '')}"
                        elif event_type == "HUCK":
                            desc = f"🎯 HUCK - {player}"
                        else:
                            desc = f"• {event_type} - {player}"

                        event_lines.append(f'<a href="#" onclick="seekToTime({timestamp_sec}); return false;" style="text-decoration: none; color: inherit;">{timestamp_str} - {desc}</a>')

                # JavaScript for video seeking
                js_code = """
                <script>
                function seekToTime(seconds) {
                    // Find the video element on the page
                    var videos = document.getElementsByTagName('video');
                    if (videos.length > 0) {
                        videos[0].currentTime = seconds;
                        videos[0].play();
                    }
                }
                </script>
                """

                # Render events with JavaScript
                st.components.v1.html(js_code + "<div style='line-height: 2.0;'>" + "<br>".join(event_lines) + "</div>", height=min(len(event_lines) * 40, 600), scrolling=True)
            else:
                st.info("No events detected in this analysis")

    except Exception as e:
        # Silently fail - don't break the main analysis display
        logger.warning(f"Video player component failed: {str(e)}")
        # Optionally show a minimal error message
        st.info("📹 Video player unavailable - analysis results shown below")

# Page configuration
st.set_page_config(
    page_title="Video Analysis - Deep Dive",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF6B35;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4A5568;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
</style>

<script>
// Request notification permission on page load
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

// Function to show browser notification
window.showAnalysisCompleteNotification = function() {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Analysis Complete', {
            body: 'Video analysis finished. Return to see results.',
            icon: '🏀',
            requireInteraction: false,
            tag: 'analysis-complete'
        });
    }
};
</script>
""", unsafe_allow_html=True)


def generate_signed_playback_url(gcs_uri: str, expiration_hours: int = 168) -> str:
    """
    Generate a signed URL for video playback from GCS

    Args:
        gcs_uri: GCS URI (gs://bucket/path/to/file.mp4)
        expiration_hours: Hours until URL expires (default: 168 = 7 days)

    Returns:
        Signed HTTPS URL for playback
    """
    try:
        # Parse GCS URI
        if not gcs_uri.startswith("gs://"):
            raise ValueError("Invalid GCS URI - must start with gs://")

        # Remove gs:// prefix and split bucket/blob
        path = gcs_uri[5:]  # Remove "gs://"
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValueError("Invalid GCS URI format")

        bucket_name = parts[0]
        blob_name = parts[1]

        # Create storage client and get blob
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Generate signed URL valid for specified hours
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=expiration_hours * 3600,  # Convert hours to seconds
            method="GET"
        )

        return signed_url

    except Exception as e:
        logger.error(f"Error generating playback URL for {gcs_uri}: {str(e)}")
        raise e


def generate_signed_upload_url(file_name: str, bucket_name: str, content_type: str = "video/mp4") -> dict:
    """
    Generate a signed URL for direct browser upload to GCS

    Args:
        file_name: Name of the file to upload
        bucket_name: GCS bucket name
        content_type: MIME type of the file

    Returns:
        Dictionary with signed_url and gcs_uri
    """
    try:
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)

        # Generate unique blob name
        blob_name = f"uploads/{int(time.time())}_{file_name}"
        blob = bucket.blob(blob_name)

        # Generate signed URL valid for 1 hour
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=3600,  # 1 hour
            method="PUT",
            content_type=content_type
        )

        gcs_uri = f"gs://{bucket_name}/{blob_name}"

        return {
            "signed_url": signed_url,
            "gcs_uri": gcs_uri,
            "blob_name": blob_name
        }

    except Exception as e:
        logger.error(f"Error generating signed URL: {str(e)}")
        raise e


def download_youtube_video(youtube_url: str, bucket_name: str) -> tuple[str, str]:
    """
    Download a YouTube video and upload to GCS

    Args:
        youtube_url: YouTube video URL
        bucket_name: GCS bucket name

    Returns:
        Tuple of (GCS URI, video title)
    """
    try:
        import yt_dlp

        # Create temp directory
        temp_dir = Path("/tmp/youtube_downloads")
        temp_dir.mkdir(exist_ok=True)

        # Configure yt-dlp options
        ydl_opts = {
            'format': 'best[ext=mp4]',  # Get best quality MP4
            'outtmpl': str(temp_dir / '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }

        st.info("📥 Downloading video from YouTube...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get video info
            info = ydl.extract_info(youtube_url, download=True)
            video_title = info.get('title', 'youtube_video')
            video_id = info.get('id', 'unknown')
            downloaded_file = temp_dir / f"{video_id}.mp4"

            st.success(f"✅ Downloaded: {video_title}")

            # Upload to GCS
            st.info("☁️ Uploading to Cloud Storage...")
            storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
            bucket = storage_client.bucket(bucket_name)

            # Generate unique blob name
            blob_name = f"youtube/{int(time.time())}_{video_id}.mp4"
            blob = bucket.blob(blob_name)

            # Upload the file
            blob.upload_from_filename(str(downloaded_file))

            gcs_uri = f"gs://{bucket_name}/{blob_name}"

            # Clean up temp file
            downloaded_file.unlink()

            st.success(f"✅ Uploaded to GCS!")
            return gcs_uri, video_title

    except Exception as e:
        st.error(f"❌ Error processing YouTube video: {str(e)}")
        logger.error(f"YouTube download error: {str(e)}")
        raise e


def upload_to_gcs(local_file_path: str, bucket_name: str) -> str:
    """
    Upload a local file to Google Cloud Storage

    Args:
        local_file_path: Path to the local file
        bucket_name: GCS bucket name

    Returns:
        GCS URI of the uploaded file
    """
    try:
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)

        # Generate a unique blob name
        file_name = Path(local_file_path).name
        blob_name = f"uploads/{int(time.time())}_{file_name}"
        blob = bucket.blob(blob_name)

        # Upload the file
        st.info(f"Uploading {file_name} to GCS...")
        blob.upload_from_filename(local_file_path)

        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        st.success(f"Successfully uploaded to {gcs_uri}")
        return gcs_uri

    except Exception as e:
        st.error(f"Error uploading file: {str(e)}")
        logger.error(f"Upload error: {str(e)}")
        return None


def verify_gcs_file(gcs_uri: str) -> bool:
    """
    Verify that a GCS file exists

    Args:
        gcs_uri: GCS URI (gs://bucket/path)

    Returns:
        True if file exists, False otherwise
    """
    try:
        # Parse GCS URI
        if not gcs_uri.startswith("gs://"):
            return False

        path_parts = gcs_uri[5:].split("/", 1)
        bucket_name = path_parts[0]
        blob_name = path_parts[1] if len(path_parts) > 1 else ""

        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        return blob.exists()

    except Exception as e:
        logger.error(f"Error verifying GCS file: {str(e)}")
        return False


def save_analysis_to_gcs(result: dict, bucket_name: str, video_name: str) -> str:
    """
    Save analysis results to Google Cloud Storage

    Args:
        result: Analysis result dictionary
        bucket_name: GCS bucket name
        video_name: Name of the analyzed video (for filename)

    Returns:
        GCS URI of the saved file
    """
    try:
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        blob_name = f"analysis/{video_name}_{timestamp}.json"
        blob = bucket.blob(blob_name)

        # Upload JSON data
        blob.upload_from_string(
            json.dumps(result, indent=2),
            content_type="application/json"
        )

        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        logger.info(f"Analysis saved to {gcs_uri}")
        return gcs_uri

    except Exception as e:
        logger.error(f"Error saving to GCS: {str(e)}")
        raise e


def format_analysis_as_text(result: dict) -> str:
    """
    Format analysis results as human-readable text

    Args:
        result: Analysis result dictionary

    Returns:
        Formatted text string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("BASKETBALL VIDEO ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Video: {result.get('video_uri', 'Unknown')}")
    lines.append(f"Duration: {result.get('duration_seconds', 0)} seconds")
    lines.append(f"Segments Analyzed: {result.get('num_segments', 0)}")
    lines.append("\n" + "=" * 80)
    lines.append("GAME SUMMARY")
    lines.append("=" * 80)
    lines.append(result.get('game_summary', 'No summary available'))

    lines.append("\n" + "=" * 80)
    lines.append("SEGMENT-BY-SEGMENT ANALYSIS")
    lines.append("=" * 80)

    for segment in result.get('segment_analyses', []):
        lines.append(f"\n--- Segment {segment['segment']} ({segment['start_time']}-{segment['end_time']}s) ---")
        lines.append(segment['analysis'])

    lines.append("\n" + "=" * 80)
    lines.append("HIGHLIGHTS")
    lines.append("=" * 80)

    highlights = result.get('highlights', [])
    if highlights:
        for i, hl in enumerate(highlights, 1):
            lines.append(f"\n{i}. {hl['time']}")
            lines.append(f"   {hl['description']}")
    else:
        lines.append("\nNo highlights identified")

    lines.append("\n" + "=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)

    return "\n".join(lines)


def main():
    """Main Streamlit application"""

    # Sidebar configuration (render first to get sport selection)
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Sport selector
        sport_options = {
            "basketball": "🏀 Basketball",
            "ultimate": "🥏 Ultimate Frisbee"
        }

        selected_sport = st.selectbox(
            "Select Sport",
            options=list(sport_options.keys()),
            index=0,
            format_func=lambda x: sport_options[x],
            help="Choose which sport you're analyzing"
        )

    # Dynamic header based on selected sport
    sport_emoji = "🏀" if selected_sport == "basketball" else "🥏"
    sport_name = "Basketball" if selected_sport == "basketball" else "Ultimate Frisbee"

    st.markdown(f'<div class="main-header">{sport_emoji} {sport_name} Video Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Powered by Gemini 2.5 Flash Lite & Google ADK</div>', unsafe_allow_html=True)

    # Continue sidebar configuration
    with st.sidebar:

        st.divider()

        # Model selector
        model_options = [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-2.5-pro",
            "gemini-3-pro-preview",
            "gemini-3-pro-image-preview",
        ]

        # Model descriptions for help text
        model_descriptions = {
            "gemini-2.5-flash-lite": "Fast & cost-effective",
            "gemini-2.5-flash": "Better accuracy than lite, good balance",
            "gemini-2.0-flash-exp": "Experimental, higher accuracy",
            "gemini-2.5-pro": "Best accuracy & reasoning (default)",
            "gemini-3-pro-preview": "Gemini 3 - Nov 18 preview",
            "gemini-3-pro-image-preview": "Gemini 3 - Nov 20, optimized for video/images",
        }

        selected_model = st.selectbox(
            "Select Model",
            options=model_options,
            index=3,  # Default to gemini-2.5-pro
            format_func=lambda x: f"{x.replace('gemini-', '')} - {model_descriptions[x]}",
            help="Higher-tier models (2.0-flash-exp, 2.5-pro) are better at distinguishing warmups from game play"
        )

        st.divider()

        # Video duration - auto-detect by default
        manual_duration = st.checkbox(
            "Manually specify video duration",
            value=False,
            help="By default, duration is auto-detected from the video. Enable to override."
        )

        video_duration = None
        if manual_duration:
            video_duration = st.number_input(
                "Video Duration (seconds)",
                min_value=10,
                max_value=3600,
                value=600,
                step=10,
                help="Manually specify video duration (will override auto-detection)"
            )
        else:
            st.info("📏 Video duration will be auto-detected from the uploaded file")

        # Start time / skip option
        start_time = st.number_input(
            "Start Analysis At (seconds)",
            min_value=0,
            max_value=3600,
            value=0,
            step=10,
            help="Skip to this time in the video (useful for skipping warmups or jumping to specific quarters)"
        )

        # Show info if skipping
        if start_time > 0:
            skip_minutes = start_time // 60
            skip_seconds = start_time % 60
            st.info(f"⏩ Will skip first {skip_minutes}m {skip_seconds}s")

        # Chunk size input
        chunk_size = st.number_input(
            "Analysis Chunk Size (seconds)",
            min_value=10,
            max_value=180,
            value=60,
            step=10,
            help="Shorter chunks (30-60s) produce better quality analysis. Longer chunks may cause incomplete output."
        )

        # Segment limit option
        limit_segments = st.checkbox(
            "Limit number of segments",
            value=False,
            help="Analyze only the first N segments (useful for testing)"
        )

        max_segments = None
        if limit_segments:
            max_segments = st.number_input(
                "Max segments to analyze",
                min_value=1,
                max_value=50,
                value=3,
                step=1,
                help="Only analyze this many segments from the beginning"
            )
            st.info(f"Will analyze first {max_segments} segment(s) = {max_segments * chunk_size} seconds")

        st.divider()

        # High Fidelity Mode controls
        st.subheader("🎨 Analysis Quality")

        high_fidelity = st.checkbox(
            "High Fidelity Mode (Tiled Vision)",
            value=False,
            help="Enable for 4K/wide-angle footage. Uses Two-Pass Architecture: (1) Temporal Filter (fast), (2) Tiled Vision (slow but prevents Visual Erasure of small players)."
        )

        hf_threshold = 2.0
        hf_fps = 3

        if high_fidelity:
            st.info("""
            🔬 **High Fidelity Mode Enabled**

            **Pass 1:** Temporal filtering (Native Video)
            - Fast analysis to find active play

            **Pass 2:** Tiled vision on active segments
            - 3 FPS frame extraction
            - 3 vertical tiles per frame (20% overlap)
            - ~3,360 tokens per timestamp
            - Biomechanical fidelity for small players

            ⚠️ **~10x slower, ~4x more accurate**
            """)

            hf_threshold = st.slider(
                "Activity Threshold (events/min)",
                min_value=1.0,
                max_value=10.0,
                value=2.0,
                step=0.5,
                help="Only apply Tiled Vision to segments with events/min above this threshold. Lower = more segments analyzed with high fidelity."
            )

            hf_fps = st.slider(
                "Tiled Vision FPS",
                min_value=1,
                max_value=5,
                value=3,
                step=1,
                help="Frame extraction rate for Tiled Vision. Higher = more frames but slower. 3 FPS is recommended."
            )

            st.caption(f"💡 Tip: Lower threshold ({hf_threshold}) = more segments analyzed with Tiled Vision")

        st.divider()

        # Environment info
        st.info(f"""
        **GCP Project:** {os.getenv('GCP_PROJECT_ID', 'Not set')}
        **GCP Bucket:** {os.getenv('GCP_BUCKET_NAME', 'Not set')}
        **Location:** {os.getenv('GCP_LOCATION', 'us-central1')}
        """)

        # Version info
        st.caption(f"v{__version__}")

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📹 Video Input")

        # File input mode selector
        input_mode = st.radio(
            "Select input mode:",
            options=["GCS URI", "YouTube URL", "Upload File"],
            horizontal=True
        )

        video_uri = None

        if input_mode == "GCS URI":
            # GCS URI input
            gcs_input = st.text_input(
                "GCS Video URI",
                value="gs://bball_project/vids/GX010043.mp4",
                placeholder="gs://bucket-name/path/to/video.mp4",
                help="Enter the Google Cloud Storage URI of your video"
            )

            if gcs_input:
                # Auto-add gs:// prefix if missing
                if not gcs_input.startswith("gs://"):
                    gcs_input = "gs://" + gcs_input
                    st.info(f"ℹ️ Auto-added gs:// prefix: {gcs_input}")

                # Verify GCS file
                with st.spinner("Verifying GCS file..."):
                    if verify_gcs_file(gcs_input):
                        st.success("✅ GCS file verified")
                        video_uri = gcs_input
                    else:
                        st.warning("⚠️ Could not verify GCS file. Proceeding anyway...")
                        video_uri = gcs_input

        elif input_mode == "YouTube URL":
            # YouTube URL input
            st.info("💡 **YouTube Support:** Enter any YouTube URL to download and analyze")

            youtube_input = st.text_input(
                "YouTube Video URL",
                value="",
                placeholder="https://www.youtube.com/watch?v=...",
                help="Enter a YouTube video URL - it will be downloaded and uploaded to GCS automatically"
            )

            if youtube_input:
                # Validate basic YouTube URL format
                if "youtube.com" in youtube_input or "youtu.be" in youtube_input:
                    if st.button("📥 Download from YouTube", type="primary", key="youtube_download_btn"):
                        try:
                            bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")

                            with st.spinner("Processing YouTube video..."):
                                gcs_uri, video_title = download_youtube_video(youtube_input, bucket_name)

                            video_uri = gcs_uri
                            st.success(f"✅ Ready to analyze: {video_title}")
                            st.code(gcs_uri, language="text")

                            # Store in session state
                            st.session_state.youtube_video_uri = gcs_uri
                            st.session_state.youtube_video_title = video_title

                        except Exception as e:
                            st.error(f"❌ Failed to process YouTube video: {str(e)}")
                            logger.error(f"YouTube processing error: {str(e)}")

                    # Check if we have a completed YouTube download in session state
                    if 'youtube_video_uri' in st.session_state:
                        video_uri = st.session_state.youtube_video_uri
                        video_title = st.session_state.get('youtube_video_title', 'YouTube video')
                        st.success(f"✅ Video ready for analysis: {video_title}")
                        st.code(video_uri, language="text")
                else:
                    st.warning("⚠️ Please enter a valid YouTube URL")

        else:
            # Direct-to-GCS file upload with signed URLs
            st.info("💡 **Direct Upload to GCS:** Files are uploaded directly to Cloud Storage (no size limit!)")

            uploaded_file = st.file_uploader(
                "Select a video file to upload",
                type=["mp4", "mov", "avi"],
                help="Files are uploaded directly to GCS - no size limits!"
            )

            if uploaded_file:
                file_size_mb = uploaded_file.size / (1024 * 1024)
                st.info(f"📊 Selected file: {uploaded_file.name} ({file_size_mb:.1f}MB)")

                # Button to initiate direct upload
                if st.button("📤 Upload to GCS", type="primary", key="direct_upload_btn"):
                    try:
                        bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")

                        # Determine content type
                        content_type = "video/mp4"
                        if uploaded_file.name.endswith(".mov"):
                            content_type = "video/quicktime"
                        elif uploaded_file.name.endswith(".avi"):
                            content_type = "video/x-msvideo"

                        with st.spinner("Generating signed URL..."):
                            # Generate signed URL
                            url_data = generate_signed_upload_url(
                                uploaded_file.name,
                                bucket_name,
                                content_type
                            )

                        st.success("✅ Upload URL generated! Uploading to GCS...")

                        # Create progress bar
                        upload_progress = st.progress(0)
                        upload_status = st.empty()

                        # Upload directly using signed URL
                        import requests

                        # Read file in chunks and upload
                        headers = {'Content-Type': content_type}
                        file_data = uploaded_file.read()

                        upload_status.text(f"Uploading {file_size_mb:.1f}MB to Cloud Storage...")

                        response = requests.put(
                            url_data["signed_url"],
                            data=file_data,
                            headers=headers
                        )

                        if response.status_code == 200:
                            video_uri = url_data["gcs_uri"]
                            upload_progress.progress(100)
                            upload_status.success(f"✅ Upload complete!")
                            st.success(f"Video uploaded successfully!")
                            st.code(video_uri, language="text")

                            # Store in session state for analysis
                            st.session_state.uploaded_video_uri = video_uri
                        else:
                            upload_status.error(f"❌ Upload failed: {response.status_code}")
                            st.error(f"Upload error: {response.text}")

                    except Exception as e:
                        st.error(f"❌ Error during upload: {str(e)}")
                        logger.error(f"Direct upload error: {str(e)}")

                # Check if we have a completed upload in session state
                if 'uploaded_video_uri' in st.session_state:
                    video_uri = st.session_state.uploaded_video_uri
                    st.success("✅ Video ready for analysis!")
                    st.code(video_uri, language="text")

    with col2:
        st.subheader("📊 Quick Stats")
        st.metric("Model", selected_model.replace("gemini-", ""))

        # Show actual duration/chunks to be analyzed
        if max_segments is not None:
            actual_duration = max_segments * chunk_size
            st.metric("Duration", f"{actual_duration // 60} min", delta=f"Limited to {max_segments} segments")
            if video_duration is not None:
                st.metric("Chunks", f"{max_segments}", delta=f"of {(video_duration + chunk_size - 1) // chunk_size} total")
            else:
                st.metric("Chunks", f"{max_segments}", delta="Auto-detecting total")
        elif video_duration is not None:
            st.metric("Duration", f"{video_duration // 60} min")
            st.metric("Chunks", f"{(video_duration + chunk_size - 1) // chunk_size}")
        else:
            st.info("📏 Duration will be auto-detected from video")

    st.divider()

    # Analysis section
    if video_uri:
        st.subheader("🎬 Video Analysis")

        # Check if we have existing results in session state
        has_existing_results = 'analysis_result' in st.session_state and st.session_state.analysis_result is not None

        # Show different buttons based on state
        if has_existing_results:
            col_action1, col_action2 = st.columns([1, 1])
            with col_action1:
                analyze_button = st.button("🔄 Run New Analysis", type="secondary", use_container_width=True)
            with col_action2:
                clear_button = st.button("🗑️ Clear Results", type="secondary", use_container_width=True)

            # Handle clear button
            if clear_button:
                st.session_state.analysis_result = None
                st.session_state.video_uri = None
                st.rerun()
        else:
            analyze_button = st.button("🚀 Start Analysis", type="primary", use_container_width=True)

        if analyze_button:
            # Clear any existing results when starting new analysis
            st.session_state.analysis_result = None
            st.session_state.video_uri = None

            # Initialize the agent
            agent_name = "CoachAI" if selected_sport == "basketball" else "UltimateAI"
            with st.spinner(f"Initializing {agent_name} agent..."):
                try:
                    agent = create_coach_agent(model_name=selected_model, sport=selected_sport)
                    st.success(f"✅ {agent_name} agent initialized successfully")
                except Exception as e:
                    st.error(f"❌ Error initializing agent: {str(e)}")
                    logger.error(f"Agent initialization error: {str(e)}")
                    return

            # Create progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            current_segment_text = st.empty()

            # Container for real-time logs
            log_container = st.expander("📋 Analysis Logs (Technical)", expanded=False)

            # Container for live play-by-play
            st.subheader("🏀 Live Play-by-Play Analysis")
            playbyplay_container = st.container()

            # Container for live highlights
            highlights_header = st.empty()
            highlights_container = st.container()

            try:
                # Run the streaming analysis
                result = None
                completed_segments = []
                live_highlights = []

                with log_container:
                    log_placeholder = st.empty()
                    logs = []

                # Calculate effective duration based on segment limit and start time
                effective_duration = None  # Will auto-detect if None

                if max_segments is not None:
                    # If limiting segments, calculate duration from segment count
                    effective_duration = max_segments * chunk_size
                    st.info(f"🎯 Analyzing first {max_segments} segments ({effective_duration} seconds) starting from {start_time}s")
                elif video_duration is not None:
                    # If manual duration specified, adjust for start time
                    effective_duration = video_duration - start_time
                    if start_time > 0:
                        st.info(f"⏩ Starting analysis at {start_time}s, analyzing {effective_duration}s of video")
                else:
                    # Auto-detect mode
                    if start_time > 0:
                        st.info(f"⏩ Starting analysis at {start_time}s (duration will be auto-detected)")
                    else:
                        st.info(f"🎬 Full video will be analyzed (duration will be auto-detected)")

                # Stream the analysis
                for update in agent.analyze_full_video_stream(
                    video_uri=video_uri,
                    duration_seconds=effective_duration,
                    chunk_size=chunk_size,
                    start_offset=start_time,
                    high_fidelity=high_fidelity,
                    hf_threshold=hf_threshold,
                    hf_fps=hf_fps
                ):
                    status = update.get("status")
                    message = update.get("message", "")
                    progress = update.get("progress", 0)

                    # Update progress bar
                    progress_bar.progress(int(progress))

                    # Update status text
                    status_text.text(f"🔄 {message}")

                    # Log the update
                    logs.append(f"[{status.upper()}] {message}")
                    with log_container:
                        log_placeholder.text("\n".join(logs[-20:]))  # Show last 20 logs

                    if status == "detecting_duration":
                        current_segment_text.info(f"📏 {message}")

                    elif status == "processing":
                        # Show which segment is being analyzed
                        seg_num = update.get("segment", 0)
                        total_segs = update.get("total_segments", 0)
                        current_segment_text.info(f"🎥 Currently analyzing: Segment {seg_num}/{total_segs}")

                    elif status == "segment_complete":
                        # Add completed segment to display
                        segment_data = update.get("segment_data", {})
                        completed_segments.append(segment_data)

                        # Show live play-by-play analysis
                        with playbyplay_container:
                            seg_num = segment_data.get('segment')
                            start_time = segment_data.get('start_time')
                            end_time = segment_data.get('end_time')
                            analysis_text = segment_data.get('analysis', '')

                            # Format time range
                            start_min = start_time // 60
                            start_sec = start_time % 60
                            end_min = end_time // 60
                            end_sec = end_time % 60
                            time_range = f"{start_min}:{start_sec:02d} - {end_min}:{end_sec:02d}"

                            # Display as an expandable card
                            # Support both old (shots) and new (events) data structures
                            events = segment_data.get('events', segment_data.get('shots', []))
                            events_per_min = segment_data.get('events_per_minute', segment_data.get('shots_per_minute', 0))
                            final_class = segment_data.get('final_classification', 'UNKNOWN')
                            initial_class = segment_data.get('initial_classification', 'UNKNOWN')

                            # Sport-specific labels
                            if selected_sport == "basketball":
                                events_label = "Shots/Minute"
                                events_total_label = "Total Shots"
                                events_log_label = "Shot Log"
                            else:  # ultimate
                                events_label = "Events/Minute"
                                events_total_label = "Total Events"
                                events_log_label = "Event Log"

                            # Determine emoji based on classification
                            class_emoji = "🏀" if final_class == "GAME" else "🔥" if final_class == "WARMUP" else "❓"

                            # Check if Pass 2 was applied
                            pass2_badge = " 🎨" if segment_data.get("pass2_applied", False) else ""

                            with st.expander(f"{class_emoji} Segment {seg_num} ({time_range}) - {final_class}{pass2_badge}", expanded=True):
                                # Show classification and event stats
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Classification", final_class)
                                with col2:
                                    st.metric(events_label, f"{events_per_min}")
                                with col3:
                                    st.metric(events_total_label, len(events))
                                with col4:
                                    # Token usage
                                    token_usage = segment_data.get('token_usage', {})
                                    total_tokens = token_usage.get('total_tokens', 0)
                                    if total_tokens > 0:
                                        st.metric("Tokens", f"{total_tokens:,}")
                                    else:
                                        st.metric("Tokens", "N/A")

                                # Show classification override if applicable
                                if initial_class != final_class:
                                    st.warning(f"⚠️ Classification overridden: {initial_class} → {final_class} (based on event frequency)")

                                # Show Pass 2 indicator if applicable
                                if segment_data.get("pass2_applied", False):
                                    pass1_events_count = len(segment_data.get("pass1_events", []))
                                    pass2_events_count = len(events)
                                    st.success(f"🎨 **High Fidelity Mode Applied** - Tiled Vision used for this segment (Pass 1: {pass1_events_count} events → Pass 2: {pass2_events_count} events)")

                                # Show detailed token breakdown
                                token_usage = segment_data.get('token_usage', {})
                                if token_usage.get('total_tokens', 0) > 0:
                                    st.caption(f"📊 Token breakdown: {token_usage.get('prompt_tokens', 0):,} prompt (inc. video) + {token_usage.get('output_tokens', 0):,} output = {token_usage.get('total_tokens', 0):,} total")

                                st.markdown("---")

                                # Show detailed event log if events exist
                                if events:
                                    with st.expander(f"📊 {events_log_label} ({len(events)} events)", expanded=False):
                                        event_lines = []
                                        for event in events:
                                            # Basketball-specific shot display
                                            if selected_sport == "basketball" and event.get('shot_type'):
                                                result_icon = "✅" if event.get('made') else "❌"
                                                timestamp = format_timestamp(event.get('timestamp', 0))
                                                event_lines.append(f"{result_icon} {timestamp} - {event.get('player')} - {event.get('shot_type')} - {'MADE' if event.get('made') else 'MISSED'}")
                                            # Ultimate-specific event display
                                            elif selected_sport == "ultimate":
                                                event_type = event.get('type', 'event').upper()
                                                timestamp = format_timestamp(event.get('timestamp', 0))
                                                player = event.get('player', 'Unknown')

                                                if event_type == "GOAL":
                                                    event_lines.append(f"⚽ {timestamp} - GOAL - {player}")
                                                elif event_type == "CATCH":
                                                    catch_type = event.get('catch_type', 'catch')
                                                    success = "✅" if event.get('success') else "❌"
                                                    event_lines.append(f"🙌 {timestamp} - CATCH - {player} - {catch_type} - {success}")
                                                elif event_type == "LAYOUT":
                                                    success = "✅" if event.get('success') else "❌"
                                                    event_lines.append(f"🤸 {timestamp} - LAYOUT - {player} - {event.get('action', '')} - {success}")
                                                elif event_type == "DEFLECTION":
                                                    deflection_type = event.get('deflection_type', 'deflection')
                                                    event_lines.append(f"✋ {timestamp} - DEFLECTION - {player} - {deflection_type}")
                                                elif event_type == "BLOCK":
                                                    event_lines.append(f"🛡️ {timestamp} - BLOCK - {player} - {event.get('block_type', '')}")
                                                elif event_type == "TURNOVER":
                                                    turnover_type = event.get('turnover_type', 'unknown')
                                                    event_lines.append(f"🔄 {timestamp} - TURNOVER - {turnover_type} - {event.get('team', '')}")
                                                elif event_type == "HUCK":
                                                    event_lines.append(f"🎯 {timestamp} - HUCK - {player} - {event.get('result', '')} - {event.get('distance', '')}")
                                                else:
                                                    event_lines.append(f"• {timestamp} - {event_type} - {player}")
                                            # Generic display
                                            else:
                                                timestamp = format_timestamp(event.get('timestamp', 0))
                                                event_lines.append(f"• {timestamp} - {event.get('type', 'event')}")

                                        # Display all events with line breaks for readability
                                        st.markdown("\n\n".join(event_lines))

                                st.markdown("**Analysis:**")
                                st.markdown(analysis_text)

                        # Handle highlights
                        if update.get("highlight_found"):
                            live_highlights.append({
                                'segment': seg_num,
                                'time_range': time_range,
                                'description': analysis_text
                            })

                            # Update highlights section - only display the new highlight
                            highlights_header.subheader(f"⭐ Highlights Found ({len(live_highlights)})")
                            with highlights_container:
                                # Display only the newly added highlight (the last one)
                                hl = live_highlights[-1]
                                idx = len(live_highlights)
                                st.warning(f"**Highlight #{idx}** - Segment {hl['segment']} ({hl['time_range']})\n\n{hl['description']}")

                    elif status == "tiling_frames":
                        # High Fidelity Mode: Pass 2 - Tiled Vision
                        pass2_current = update.get("pass2_current", 0)
                        pass2_total = update.get("pass2_total", 0)
                        seg_num = update.get("segment", 0)
                        current_segment_text.warning(f"🎬 High Fidelity Pass 2: Extracting & Tiling Frames (Segment {seg_num}, {pass2_current}/{pass2_total})")

                    elif status == "compiling":
                        current_segment_text.info("🔄 Compiling final game summary...")

                    elif status == "complete":
                        result = update.get("result")
                        # Store in session state to persist across reruns
                        st.session_state.analysis_result = result
                        st.session_state.video_uri = video_uri
                        current_segment_text.success("✅ Analysis complete!")

                        # Trigger browser notification
                        st.components.v1.html("""
                            <script>
                            if (window.showAnalysisCompleteNotification) {
                                window.showAnalysisCompleteNotification();
                            }
                            </script>
                        """, height=0)

                progress_bar.progress(100)
                status_text.text("✅ Analysis complete!")

                # Check if we got a result
                if result is None:
                    st.error("❌ Analysis completed but no result was returned")
                    return

                # Display results
                st.success("🎉 Analysis completed successfully!")

                st.divider()

                # Video Player with Event Navigation (fault-tolerant) - FIRST for easy navigation
                render_video_player_with_events(video_uri, result, selected_sport)

                st.divider()

                # Game Summary
                st.subheader("📝 Game Summary")
                st.markdown(result.get("game_summary", "No summary available"))

                # Player Roster (if available)
                roster = result.get("roster", [])
                if roster and len(roster) > 0:
                    st.divider()
                    st.subheader("👥 Player Roster")
                    st.caption(f"Identified {len(roster)} players during warmup segments")

                    # Display roster as cards
                    cols = st.columns(3)
                    for idx, player in enumerate(roster):
                        with cols[idx % 3]:
                            with st.container():
                                st.markdown(f"**{player.get('jersey_number', 'Unknown')}** - {player.get('team_color', '')}")
                                st.text(f"Height: {player.get('height', 'N/A')}")
                                st.text(f"Build: {player.get('build', 'N/A')}")
                                st.text(f"Skin: {player.get('skin_tone', 'N/A')}")
                                st.text(f"Hair: {player.get('hair', 'N/A')}")
                                st.text(f"Shoes: {player.get('shoes', 'N/A')}")
                                if player.get('other'):
                                    st.text(f"Notes: {player.get('other')}")
                                st.markdown("---")

                st.divider()

                # Segment Analysis
                st.subheader("🔍 Detailed Segment Analysis")

                segments_data = []
                for segment in result.get("segment_analyses", []):
                    segments_data.append({
                        "Segment": segment["segment"],
                        "Time Range": f"{segment['start_time']}-{segment['end_time']}s",
                        "Analysis": segment["analysis"][:150] + "..."
                    })

                if segments_data:
                    df_segments = pd.DataFrame(segments_data)
                    st.dataframe(df_segments, use_container_width=True)

                    # Display full analyses in expandable sections
                    for segment in result.get("segment_analyses", []):
                        seg_num = segment['segment']
                        with st.expander(f"Segment {seg_num} ({segment['start_time']}-{segment['end_time']}s)"):
                            st.write(segment["analysis"])

                            # Retry section
                            st.markdown("---")
                            st.caption("🔄 Not satisfied with this segment? Re-analyze with a better model:")
                            retry_col1, retry_col2 = st.columns([3, 1])
                            with retry_col1:
                                retry_model = st.selectbox(
                                    "Model:",
                                    options=model_options,
                                    index=5,  # Default to gemini-3-pro-image-preview (best for video)
                                    format_func=lambda x: model_descriptions[x],
                                    key=f"retry_model_live_{seg_num}"
                                )
                            with retry_col2:
                                if st.button("Re-analyze", key=f"retry_live_{seg_num}", use_container_width=True):
                                    # Re-analyze this segment
                                    with st.spinner(f"Re-analyzing segment {seg_num} with {retry_model}..."):
                                        try:
                                            # Create agent with new model
                                            if selected_sport == "basketball":
                                                from agent import BasketballAgent
                                                retry_agent = BasketballAgent(model_name=retry_model)
                                            else:
                                                from agent import UltimateAgent
                                                retry_agent = UltimateAgent(model_name=retry_model)

                                            # Get the analysis prompt
                                            prompt = retry_agent.get_analysis_prompt(
                                                segment['start_time'],
                                                segment['end_time'],
                                                None  # No previous context for retry
                                            )

                                            # Re-analyze the segment
                                            new_analysis, new_tokens = retry_agent.video_tool.analyze_video_segment(
                                                video_uri=video_uri,
                                                start_sec=segment['start_time'],
                                                end_sec=segment['end_time'],
                                                prompt=prompt
                                            )

                                            # Parse events from new analysis
                                            new_events = retry_agent.parse_events(new_analysis)

                                            # Update segment in result
                                            segment['analysis'] = new_analysis
                                            segment['events'] = new_events
                                            segment['token_usage'] = new_tokens

                                            # Update session state
                                            st.session_state.analysis_result = result

                                            st.success(f"✅ Segment {seg_num} re-analyzed with {retry_model}!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Retry failed: {str(e)}")

                # Highlights
                st.subheader("⭐ Highlight Moments")
                highlights = result.get("highlights", [])

                if highlights:
                    for i, highlight in enumerate(highlights, 1):
                        st.info(f"**{highlight['time']}**: {highlight['description']}")
                else:
                    st.info("No specific highlights identified in this analysis")

                # Statistics DataFrame
                st.subheader("📊 Analysis Statistics")

                # Get token usage
                token_usage = result.get("total_token_usage", {})
                total_tokens = token_usage.get("total_tokens", 0)
                token_display = f"{total_tokens:,}" if total_tokens > 0 else "N/A"

                stats_data = {
                    "Metric": [
                        "Video URI",
                        "Total Duration",
                        "Number of Segments",
                        "Chunk Size",
                        "Model Used",
                        "Highlights Found",
                        "Total Tokens Used"
                    ],
                    "Value": [
                        result.get("video_uri", "N/A"),
                        f"{result.get('duration_seconds', 0)} seconds ({result.get('duration_seconds', 0) // 60} minutes)",
                        result.get("num_segments", 0),
                        f"{chunk_size} seconds",
                        selected_model,
                        len(highlights),
                        token_display
                    ]
                }
                df_stats = pd.DataFrame(stats_data)
                st.dataframe(df_stats, use_container_width=True, hide_index=True)

                # Show detailed token breakdown if available
                if total_tokens > 0:
                    st.caption(f"💰 Token breakdown: {token_usage.get('prompt_tokens', 0):,} prompt + {token_usage.get('output_tokens', 0):,} output = {total_tokens:,} total")

                # Player Name Chat Interface
                st.divider()
                st.subheader("💬 Update Player Names with AI")
                st.caption("Tell the AI which player is which (e.g., 'White #23 is LeBron James') and it will rewrite the entire analysis with real names")

                # Initialize chat history in session state
                if 'player_name_chat_history' not in st.session_state:
                    st.session_state.player_name_chat_history = []

                # Display chat history
                if st.session_state.player_name_chat_history:
                    with st.expander("📜 Chat History", expanded=False):
                        for msg in st.session_state.player_name_chat_history:
                            if msg['role'] == 'user':
                                st.markdown(f"**You:** {msg['content']}")
                            else:
                                st.markdown(f"**AI:** {msg['content']}")

                # Chat input
                chat_col1, chat_col2 = st.columns([5, 1])
                with chat_col1:
                    player_input = st.text_input(
                        "Tell me about a player:",
                        placeholder="e.g., 'Tall player white #23 is LeBron James' or 'Update blue #7 to Stephen Curry'",
                        key="player_name_input_live"
                    )
                with chat_col2:
                    update_names = st.button("Update", use_container_width=True, key="update_names_live")

                if update_names and player_input:
                    with st.spinner("AI is updating player names throughout the analysis..."):
                        try:
                            # Create agent for name replacement
                            if selected_sport == "basketball":
                                from agent import BasketballAgent
                                chat_agent = BasketballAgent(model_name=selected_model)
                            else:
                                from agent import UltimateAgent
                                chat_agent = UltimateAgent(model_name=selected_model)

                            # Build prompt for Gemini to update names
                            update_prompt = f"""You are helping update a sports video analysis by replacing player descriptions with actual names.

User instruction: {player_input}

Current analysis data (JSON):
{json.dumps(result, indent=2)}

Task:
1. Identify which player description the user is referring to (jersey number, team color, physical description)
2. Replace ALL occurrences of that player description with the actual name throughout:
   - segment_analyses (all analysis text and events)
   - roster (player profiles)
   - game_summary
   - highlights
3. Be consistent - replace the description everywhere it appears
4. Preserve all other data (timestamps, token counts, classifications, etc.)
5. Return ONLY the updated JSON data, nothing else

Return the complete updated result JSON."""

                            # Call Gemini to update names
                            response = chat_agent.client.models.generate_content(
                                model=selected_model,
                                contents=update_prompt,
                                config=types.GenerateContentConfig(
                                    temperature=0.1,  # Low temperature for accuracy
                                    max_output_tokens=8192
                                )
                            )

                            # Parse the updated JSON
                            updated_result_text = response.text.strip()
                            # Remove markdown code blocks if present
                            if updated_result_text.startswith("```"):
                                updated_result_text = updated_result_text.split("```")[1]
                                if updated_result_text.startswith("json"):
                                    updated_result_text = updated_result_text[4:]

                            updated_result = json.loads(updated_result_text)

                            # Update session state with new result
                            st.session_state.analysis_result = updated_result
                            result = updated_result  # Update local variable

                            # Add to chat history
                            st.session_state.player_name_chat_history.append({
                                'role': 'user',
                                'content': player_input
                            })
                            st.session_state.player_name_chat_history.append({
                                'role': 'assistant',
                                'content': f"✅ Updated! I've replaced that player description with the name throughout the entire analysis."
                            })

                            st.success("✅ Player names updated throughout the analysis!")
                            st.rerun()

                        except json.JSONDecodeError as e:
                            st.error(f"❌ Failed to parse AI response: {str(e)}")
                            st.code(response.text[:500])
                        except Exception as e:
                            st.error(f"❌ Error updating names: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())

                # Export Results Section
                st.divider()
                st.subheader("💾 Export Results")

                col_export1, col_export2, col_export3 = st.columns(3)

                with col_export1:
                    # Download as JSON
                    json_data = json.dumps(result, indent=2)
                    st.download_button(
                        label="📥 Download JSON",
                        data=json_data,
                        file_name=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )

                with col_export2:
                    # Download as Text
                    text_data = format_analysis_as_text(result)
                    st.download_button(
                        label="📄 Download Report (TXT)",
                        data=text_data,
                        file_name=f"analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

                with col_export3:
                    # Save to GCS
                    if st.button("☁️ Save to GCS", use_container_width=True):
                        try:
                            # Extract video name from URI
                            video_name = video_uri.split("/")[-1].replace(".mp4", "")
                            bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")

                            with st.spinner("Saving to GCS..."):
                                gcs_uri = save_analysis_to_gcs(result, bucket_name, video_name)

                            st.success(f"✅ Saved to GCS!")
                            st.code(gcs_uri, language="text")

                        except Exception as e:
                            st.error(f"❌ Error saving to GCS: {str(e)}")

                # Logs
                with log_container:
                    st.text("Analysis completed successfully")
                    st.json(result)

            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                logger.error(f"Analysis error: {str(e)}")
                progress_bar.progress(0)
                status_text.text("❌ Analysis failed")

                with log_container:
                    st.error(str(e))

        # Display results from session state if they exist (and we didn't just run a new analysis)
        if not analyze_button and has_existing_results:
            result = st.session_state.analysis_result
            saved_video_uri = st.session_state.get('video_uri', video_uri)

            st.success("🎉 Showing saved analysis results")
            st.divider()

            # Video Player with Event Navigation (fault-tolerant) - FIRST for easy navigation
            render_video_player_with_events(saved_video_uri, result, selected_sport)

            st.divider()

            # Game Summary
            st.subheader("📝 Game Summary")
            st.markdown(result.get("game_summary", "No summary available"))

            # Player Roster (if available)
            roster = result.get("roster", [])
            if roster and len(roster) > 0:
                st.divider()
                st.subheader("👥 Player Roster")
                st.caption(f"Identified {len(roster)} players during warmup segments")

                # Display roster as cards
                cols = st.columns(3)
                for idx, player in enumerate(roster):
                    with cols[idx % 3]:
                        with st.container():
                            st.markdown(f"**{player.get('jersey_number', 'Unknown')}** - {player.get('team_color', '')}")
                            st.text(f"Height: {player.get('height', 'N/A')}")
                            st.text(f"Build: {player.get('build', 'N/A')}")
                            st.text(f"Skin: {player.get('skin_tone', 'N/A')}")
                            st.text(f"Hair: {player.get('hair', 'N/A')}")
                            st.text(f"Shoes: {player.get('shoes', 'N/A')}")
                            if player.get('other'):
                                st.text(f"Notes: {player.get('other')}")
                            st.markdown("---")

            st.divider()

            # Segment Analysis
            st.subheader("🔍 Detailed Segment Analysis")

            segments_data = []
            for segment in result.get("segment_analyses", []):
                segments_data.append({
                    "Segment": segment["segment"],
                    "Time Range": f"{segment['start_time']}-{segment['end_time']}s",
                    "Analysis": segment["analysis"][:150] + "..."
                })

            if segments_data:
                df_segments = pd.DataFrame(segments_data)
                st.dataframe(df_segments, use_container_width=True)

                # Display full analyses in expandable sections
                for segment in result.get("segment_analyses", []):
                    seg_num = segment['segment']
                    with st.expander(f"Segment {seg_num} ({segment['start_time']}-{segment['end_time']}s)"):
                        st.write(segment["analysis"])

                        # Retry section
                        st.markdown("---")
                        st.caption("🔄 Not satisfied with this segment? Re-analyze with a better model:")
                        retry_col1, retry_col2 = st.columns([3, 1])
                        with retry_col1:
                            retry_model = st.selectbox(
                                "Model:",
                                options=model_options,
                                index=5,  # Default to gemini-3-pro-image-preview (best for video)
                                format_func=lambda x: model_descriptions[x],
                                key=f"retry_model_saved_{seg_num}"
                            )
                        with retry_col2:
                            if st.button("Re-analyze", key=f"retry_saved_{seg_num}", use_container_width=True):
                                # Re-analyze this segment
                                with st.spinner(f"Re-analyzing segment {seg_num} with {retry_model}..."):
                                    try:
                                        # Create agent with new model
                                        if selected_sport == "basketball":
                                            from agent import BasketballAgent
                                            retry_agent = BasketballAgent(model_name=retry_model)
                                        else:
                                            from agent import UltimateAgent
                                            retry_agent = UltimateAgent(model_name=retry_model)

                                        # Get the analysis prompt
                                        prompt = retry_agent.get_analysis_prompt(
                                            segment['start_time'],
                                            segment['end_time'],
                                            None  # No previous context for retry
                                        )

                                        # Re-analyze the segment
                                        new_analysis, new_tokens = retry_agent.video_tool.analyze_video_segment(
                                            video_uri=saved_video_uri,
                                            start_sec=segment['start_time'],
                                            end_sec=segment['end_time'],
                                            prompt=prompt
                                        )

                                        # Parse events from new analysis
                                        new_events = retry_agent.parse_events(new_analysis)

                                        # Update segment in result
                                        segment['analysis'] = new_analysis
                                        segment['events'] = new_events
                                        segment['token_usage'] = new_tokens

                                        # Update session state
                                        st.session_state.analysis_result = result

                                        st.success(f"✅ Segment {seg_num} re-analyzed with {retry_model}!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Retry failed: {str(e)}")

            # Highlights
            st.subheader("⭐ Highlight Moments")
            highlights = result.get("highlights", [])

            if highlights:
                for i, highlight in enumerate(highlights, 1):
                    st.info(f"**{highlight['time']}**: {highlight['description']}")
            else:
                st.info("No specific highlights identified in this analysis")

            # Statistics DataFrame
            st.subheader("📊 Analysis Statistics")

            # Get token usage
            token_usage = result.get("total_token_usage", {})
            total_tokens = token_usage.get("total_tokens", 0)
            token_display = f"{total_tokens:,}" if total_tokens > 0 else "N/A"

            stats_data = {
                "Metric": [
                    "Video URI",
                    "Total Duration",
                    "Number of Segments",
                    "Chunk Size",
                    "Model Used",
                    "Highlights Found",
                    "Total Tokens Used"
                ],
                "Value": [
                    result.get("video_uri", "N/A"),
                    f"{result.get('duration_seconds', 0)} seconds ({result.get('duration_seconds', 0) // 60} minutes)",
                    result.get("num_segments", 0),
                    f"{chunk_size} seconds",
                    selected_model,
                    len(highlights),
                    token_display
                ]
            }
            df_stats = pd.DataFrame(stats_data)
            st.dataframe(df_stats, use_container_width=True, hide_index=True)

            # Show detailed token breakdown if available
            if total_tokens > 0:
                st.caption(f"💰 Token breakdown: {token_usage.get('prompt_tokens', 0):,} prompt + {token_usage.get('output_tokens', 0):,} output = {total_tokens:,} total")

            # Player Name Chat Interface
            st.divider()
            st.subheader("💬 Update Player Names with AI")
            st.caption("Tell the AI which player is which (e.g., 'White #23 is LeBron James') and it will rewrite the entire analysis with real names")

            # Initialize chat history in session state
            if 'player_name_chat_history' not in st.session_state:
                st.session_state.player_name_chat_history = []

            # Display chat history
            if st.session_state.player_name_chat_history:
                with st.expander("📜 Chat History", expanded=False):
                    for msg in st.session_state.player_name_chat_history:
                        if msg['role'] == 'user':
                            st.markdown(f"**You:** {msg['content']}")
                        else:
                            st.markdown(f"**AI:** {msg['content']}")

            # Chat input
            chat_col1, chat_col2 = st.columns([5, 1])
            with chat_col1:
                player_input = st.text_input(
                    "Tell me about a player:",
                    placeholder="e.g., 'Tall player white #23 is LeBron James' or 'Update blue #7 to Stephen Curry'",
                    key="player_name_input_saved"
                )
            with chat_col2:
                update_names = st.button("Update", use_container_width=True, key="update_names_saved")

            if update_names and player_input:
                with st.spinner("AI is updating player names throughout the analysis..."):
                    try:
                        # Create agent for name replacement
                        if selected_sport == "basketball":
                            from agent import BasketballAgent
                            chat_agent = BasketballAgent(model_name=selected_model)
                        else:
                            from agent import UltimateAgent
                            chat_agent = UltimateAgent(model_name=selected_model)

                        # Build prompt for Gemini to update names
                        update_prompt = f"""You are helping update a sports video analysis by replacing player descriptions with actual names.

User instruction: {player_input}

Current analysis data (JSON):
{json.dumps(result, indent=2)}

Task:
1. Identify which player description the user is referring to (jersey number, team color, physical description)
2. Replace ALL occurrences of that player description with the actual name throughout:
   - segment_analyses (all analysis text and events)
   - roster (player profiles)
   - game_summary
   - highlights
3. Be consistent - replace the description everywhere it appears
4. Preserve all other data (timestamps, token counts, classifications, etc.)
5. Return ONLY the updated JSON data, nothing else

Return the complete updated result JSON."""

                        # Call Gemini to update names
                        response = chat_agent.client.models.generate_content(
                            model=selected_model,
                            contents=update_prompt,
                            config=types.GenerateContentConfig(
                                temperature=0.1,  # Low temperature for accuracy
                                max_output_tokens=8192
                            )
                        )

                        # Parse the updated JSON
                        updated_result_text = response.text.strip()
                        # Remove markdown code blocks if present
                        if updated_result_text.startswith("```"):
                            updated_result_text = updated_result_text.split("```")[1]
                            if updated_result_text.startswith("json"):
                                updated_result_text = updated_result_text[4:]

                        updated_result = json.loads(updated_result_text)

                        # Update session state with new result
                        st.session_state.analysis_result = updated_result
                        result = updated_result  # Update local variable

                        # Add to chat history
                        st.session_state.player_name_chat_history.append({
                            'role': 'user',
                            'content': player_input
                        })
                        st.session_state.player_name_chat_history.append({
                            'role': 'assistant',
                            'content': f"✅ Updated! I've replaced that player description with the name throughout the entire analysis."
                        })

                        st.success("✅ Player names updated throughout the analysis!")
                        st.rerun()

                    except json.JSONDecodeError as e:
                        st.error(f"❌ Failed to parse AI response: {str(e)}")
                        st.code(response.text[:500])
                    except Exception as e:
                        st.error(f"❌ Error updating names: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())

            # Export Results Section
            st.divider()
            st.subheader("💾 Export Results")

            col_export1, col_export2, col_export3 = st.columns(3)

            with col_export1:
                # Download as JSON
                json_data = json.dumps(result, indent=2)
                st.download_button(
                    label="📥 Download JSON",
                    data=json_data,
                    file_name=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

            with col_export2:
                # Download as Text
                text_data = format_analysis_as_text(result)
                st.download_button(
                    label="📄 Download Report (TXT)",
                    data=text_data,
                    file_name=f"analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

            with col_export3:
                # Save to GCS
                if st.button("☁️ Save to GCS", use_container_width=True, key="save_to_gcs_persisted"):
                    try:
                        # Extract video name from URI
                        video_name = saved_video_uri.split("/")[-1].replace(".mp4", "")
                        bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")

                        with st.spinner("Saving to GCS..."):
                            gcs_uri = save_analysis_to_gcs(result, bucket_name, video_name)

                        st.success(f"✅ Saved to GCS!")
                        st.code(gcs_uri, language="text")

                    except Exception as e:
                        st.error(f"❌ Error saving to GCS: {str(e)}")

    else:
        st.info("👈 Please provide a video URI or upload a file to begin analysis")

    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #718096; padding: 1rem;'>
        Built with ❤️ using Streamlit, Google ADK, and Gemini 2.5 Flash Lite
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    # Verify environment variables
    required_vars = ["GCP_PROJECT_ID", "GCP_BUCKET_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        st.error(f"""
        ❌ Missing required environment variables: {', '.join(missing_vars)}

        ## Quick Fix:

        The `.env` file is missing or incomplete. Follow these steps:

        ### Option 1: Copy from example (Recommended)
        ```bash
        cp .env.example .env
        ```

        ### Option 2: Create manually
        Create a file named `.env` in the project root with:
        ```
        GCP_PROJECT_ID=qwiklabs-gcp-04-b5171aa68bec
        GCP_BUCKET_NAME=bball_project
        GCP_LOCATION=us-central1
        ```

        ### Option 3: Quick command
        ```bash
        cat > .env << 'EOF'
GCP_PROJECT_ID=qwiklabs-gcp-04-b5171aa68bec
GCP_BUCKET_NAME=bball_project
GCP_LOCATION=us-central1
EOF
        ```

        After creating the `.env` file, restart the Streamlit app:
        ```bash
        streamlit run app.py
        ```
        """)

        # Show helpful debug info
        st.info(f"""
        📁 **Current Directory:** `{os.getcwd()}`

        Looking for `.env` file at: `{os.path.join(os.getcwd(), '.env')}`

        **File exists?** {os.path.exists('.env')}
        """)
    else:
        main()
