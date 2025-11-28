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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Basketball Video Agent",
    page_icon="🏀",
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
""", unsafe_allow_html=True)


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


def main():
    """Main Streamlit application"""

    # Header
    st.markdown('<div class="main-header">🏀 Basketball Video Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Powered by Gemini 2.5 Flash Lite & Google ADK</div>', unsafe_allow_html=True)

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Model selector
        model_options = [
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]
        selected_model = st.selectbox(
            "Select Model",
            options=model_options,
            index=0,
            help="Choose the Gemini model for video analysis"
        )

        st.divider()

        # Video duration input
        video_duration = st.number_input(
            "Video Duration (seconds)",
            min_value=60,
            max_value=3600,
            value=600,
            step=60,
            help="Estimated total duration of the video"
        )

        # Chunk size input
        chunk_size = st.number_input(
            "Analysis Chunk Size (seconds)",
            min_value=30,
            max_value=300,
            value=120,
            step=30,
            help="Size of each video segment to analyze (default: 2 minutes)"
        )

        st.divider()

        # Environment info
        st.info(f"""
        **GCP Project:** {os.getenv('GCP_PROJECT_ID', 'Not set')}
        **GCP Bucket:** {os.getenv('GCP_BUCKET_NAME', 'Not set')}
        **Location:** {os.getenv('GCP_LOCATION', 'us-central1')}
        """)

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📹 Video Input")

        # File input mode selector
        input_mode = st.radio(
            "Select input mode:",
            options=["GCS URI", "Upload File"],
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
                # Verify GCS file
                with st.spinner("Verifying GCS file..."):
                    if verify_gcs_file(gcs_input):
                        st.success("✅ GCS file verified")
                        video_uri = gcs_input
                    else:
                        st.warning("⚠️ Could not verify GCS file. Proceeding anyway...")
                        video_uri = gcs_input

        else:
            # File upload
            uploaded_file = st.file_uploader(
                "Upload a video file",
                type=["mp4", "mov", "avi"],
                help="Upload a local video file (will be uploaded to GCS)"
            )

            if uploaded_file:
                # Save uploaded file temporarily
                temp_dir = Path("/tmp/bball_uploads")
                temp_dir.mkdir(exist_ok=True)
                temp_file_path = temp_dir / uploaded_file.name

                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Upload to GCS
                bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")
                video_uri = upload_to_gcs(str(temp_file_path), bucket_name)

                # Clean up temp file
                temp_file_path.unlink()

    with col2:
        st.subheader("📊 Quick Stats")
        st.metric("Model", selected_model.replace("gemini-", ""))
        st.metric("Duration", f"{video_duration // 60} min")
        st.metric("Chunks", f"{(video_duration + chunk_size - 1) // chunk_size}")

    st.divider()

    # Analysis section
    if video_uri:
        st.subheader("🎬 Video Analysis")

        analyze_button = st.button("🚀 Start Analysis", type="primary", use_container_width=True)

        if analyze_button:
            # Initialize the agent
            with st.spinner("Initializing CoachAI agent..."):
                try:
                    agent = create_coach_agent(model_name=selected_model)
                    st.success("✅ Agent initialized successfully")
                except Exception as e:
                    st.error(f"❌ Error initializing agent: {str(e)}")
                    logger.error(f"Agent initialization error: {str(e)}")
                    return

            # Create progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            current_segment_text = st.empty()

            # Container for real-time logs
            log_container = st.expander("📋 Real-Time Analysis Logs", expanded=True)

            # Container for completed segments
            segments_container = st.container()

            try:
                # Run the streaming analysis
                result = None
                completed_segments = []

                with log_container:
                    log_placeholder = st.empty()
                    logs = []

                # Stream the analysis
                for update in agent.analyze_full_video_stream(
                    video_uri=video_uri,
                    duration_seconds=video_duration,
                    chunk_size=chunk_size
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

                    if status == "processing":
                        # Show which segment is being analyzed
                        seg_num = update.get("segment", 0)
                        total_segs = update.get("total_segments", 0)
                        current_segment_text.info(f"🎥 Currently analyzing: Segment {seg_num}/{total_segs}")

                    elif status == "segment_complete":
                        # Add completed segment to display
                        segment_data = update.get("segment_data", {})
                        completed_segments.append(segment_data)

                        # Show real-time segment completion
                        with segments_container:
                            st.success(f"✅ Segment {segment_data.get('segment')} complete ({segment_data.get('start_time')}-{segment_data.get('end_time')}s)")
                            if update.get("highlight_found"):
                                st.warning(f"⭐ Highlight detected in this segment!")

                    elif status == "compiling":
                        current_segment_text.info("🔄 Compiling final game summary...")

                    elif status == "complete":
                        result = update.get("result")
                        current_segment_text.success("✅ Analysis complete!")

                progress_bar.progress(100)
                status_text.text("✅ Analysis complete!")

                # Check if we got a result
                if result is None:
                    st.error("❌ Analysis completed but no result was returned")
                    return

                # Display results
                st.success("🎉 Analysis completed successfully!")

                st.divider()

                # Game Summary
                st.subheader("📝 Game Summary")
                st.markdown(result.get("game_summary", "No summary available"))

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
                        with st.expander(f"Segment {segment['segment']} ({segment['start_time']}-{segment['end_time']}s)"):
                            st.write(segment["analysis"])

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
                stats_data = {
                    "Metric": [
                        "Video URI",
                        "Total Duration",
                        "Number of Segments",
                        "Chunk Size",
                        "Model Used",
                        "Highlights Found"
                    ],
                    "Value": [
                        result.get("video_uri", "N/A"),
                        f"{result.get('duration_seconds', 0)} seconds ({result.get('duration_seconds', 0) // 60} minutes)",
                        result.get("num_segments", 0),
                        f"{chunk_size} seconds",
                        selected_model,
                        len(highlights)
                    ]
                }
                df_stats = pd.DataFrame(stats_data)
                st.dataframe(df_stats, use_container_width=True, hide_index=True)

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

        Please create a `.env` file with:
        ```
        GCP_PROJECT_ID=qwiklabs-gcp-04-b5171aa68bec
        GCP_BUCKET_NAME=bball_project
        ```
        """)
    else:
        main()
