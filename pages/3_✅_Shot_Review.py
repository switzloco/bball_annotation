"""
Shot Review & Correction Page
Human-in-the-loop workflow: AI detects shots, human corrects misclassifications
"""
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import storage
from agent import create_coach_agent
import logging
import json
from datetime import datetime
import tempfile
import subprocess
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Shot Review & Correction",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #10B981;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4A5568;
        text-align: center;
        margin-bottom: 2rem;
    }
    .shot-card {
        border: 2px solid #E5E7EB;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        background-color: #F9FAFB;
    }
    .shot-card-correct {
        border-color: #10B981;
        background-color: #ECFDF5;
    }
    .shot-card-corrected {
        border-color: #F59E0B;
        background-color: #FFFBEB;
    }
    .shot-card-low-confidence {
        border-color: #EF4444;
        background-color: #FEF2F2;
    }
    .confidence-high {
        color: #10B981;
        font-weight: bold;
    }
    .confidence-medium {
        color: #F59E0B;
        font-weight: bold;
    }
    .confidence-low {
        color: #EF4444;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def extract_frame_thumbnail(video_uri: str, timestamp_sec: int) -> str:
    """
    Extract a frame thumbnail and return as base64 for display

    Args:
        video_uri: GCS URI
        timestamp_sec: Time in seconds

    Returns:
        Base64 encoded image string
    """
    try:
        # Parse GCS URI and create signed URL
        if video_uri.startswith("gs://"):
            path_parts = video_uri[5:].split("/", 1)
            bucket_name = path_parts[0]
            blob_path = path_parts[1]

            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=3600,
                method="GET"
            )
        else:
            signed_url = video_uri

        # Extract frame
        temp_frame = f"/tmp/thumb_{timestamp_sec}.jpg"
        cmd = [
            'ffmpeg',
            '-ss', str(timestamp_sec),
            '-i', signed_url,
            '-vframes', '1',
            '-vf', 'scale=320:-1',  # Smaller thumbnail
            '-q:v', '5',
            '-y',
            temp_frame
        ]

        subprocess.run(cmd, capture_output=True, timeout=30, check=True)

        # Read and encode as base64
        with open(temp_frame, 'rb') as f:
            img_data = f.read()
            img_base64 = base64.b64encode(img_data).decode()

        # Cleanup
        os.remove(temp_frame)

        return f"data:image/jpeg;base64,{img_base64}"

    except Exception as e:
        logger.error(f"Error extracting thumbnail: {e}")
        return None


def upload_to_gcs(local_file_path: str, bucket_name: str) -> str:
    """Upload local file to GCS"""
    try:
        import time
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)

        file_name = Path(local_file_path).name
        blob_name = f"review_uploads/{int(time.time())}_{file_name}"
        blob = bucket.blob(blob_name)

        blob.upload_from_filename(local_file_path)

        return f"gs://{bucket_name}/{blob_name}"
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return None


def get_signed_url(video_uri: str) -> str:
    """
    Convert GCS URI to signed URL for video playback

    Args:
        video_uri: GCS URI (gs://bucket/path) or regular URL

    Returns:
        Signed URL or original URL
    """
    try:
        if video_uri.startswith("gs://"):
            path_parts = video_uri[5:].split("/", 1)
            bucket_name = path_parts[0]
            blob_path = path_parts[1]

            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=7200,  # 2 hours for longer review sessions
                method="GET"
            )
            return signed_url
        else:
            return video_uri
    except Exception as e:
        logger.error(f"Error generating signed URL: {e}")
        return video_uri


def main():
    """Main Shot Review application"""

    # Header
    st.markdown('<div class="main-header">✅ Shot Review & Correction</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">AI detects shots → You confirm or correct → Export accurate data</div>', unsafe_allow_html=True)

    # Sidebar configuration
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
            format_func=lambda x: sport_options[x]
        )

        st.divider()

        # Model selector
        model_options = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-3-pro-preview",
            "gemini-3-pro-image-preview",
        ]

        selected_model = st.selectbox(
            "Select Model",
            options=model_options,
            index=0,
            help="Pro models are better for shot classification"
        )

        st.divider()

        # Review options
        st.subheader("📋 Review Options")

        show_only_uncertain = st.checkbox(
            "Show only low confidence (<70%)",
            value=False,
            help="Focus on shots that need review"
        )

        extract_thumbnails = st.checkbox(
            "Extract thumbnails",
            value=True,
            help="Show frame at each shot (slower but helpful)"
        )

        st.divider()

        st.info(f"""
        **GCP Project:** {os.getenv('GCP_PROJECT_ID', 'Not set')}
        **GCP Bucket:** {os.getenv('GCP_BUCKET_NAME', 'Not set')}
        """)

    # Main content
    st.subheader("📹 Video Input")

    # Input mode
    input_mode = st.radio(
        "Select input mode:",
        options=["GCS URI", "Upload File"],
        horizontal=True
    )

    video_uri = None

    if input_mode == "GCS URI":
        gcs_input = st.text_input(
            "GCS Video URI",
            value="",
            placeholder="gs://bucket-name/path/to/video.mp4"
        )

        if gcs_input:
            if not gcs_input.startswith("gs://"):
                gcs_input = "gs://" + gcs_input
            video_uri = gcs_input
            st.success(f"✅ Video loaded: {video_uri}")

    else:
        uploaded_file = st.file_uploader(
            "Select video file",
            type=["mp4", "mov", "avi"]
        )

        if uploaded_file:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.info(f"📊 Selected: {uploaded_file.name} ({file_size_mb:.1f}MB)")

            if st.button("📤 Upload to GCS", type="primary"):
                bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")

                temp_path = f"/tmp/{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.read())

                with st.spinner("Uploading..."):
                    video_uri = upload_to_gcs(temp_path, bucket_name)

                if video_uri:
                    st.success(f"✅ Uploaded: {video_uri}")
                    st.session_state.review_video_uri = video_uri

                os.remove(temp_path)

    # Check session state
    if 'review_video_uri' in st.session_state:
        video_uri = st.session_state.review_video_uri

    # Analysis & Review Interface
    if video_uri:
        st.divider()

        # Check if we have existing analysis
        has_analysis = 'shot_list' in st.session_state and st.session_state.shot_list

        if not has_analysis:
            st.subheader("🎬 Step 1: Analyze Video")
            st.info("Click 'Analyze' to detect shots using AI. This will create an initial shot list that you can then review and correct.")

            if st.button("🚀 Analyze Video & Detect Shots", type="primary", use_container_width=True):
                # Initialize agent
                with st.spinner("Initializing AI agent..."):
                    agent = create_coach_agent(model_name=selected_model, sport=selected_sport)

                # Run analysis
                progress_bar = st.progress(0)
                status_text = st.empty()

                status_text.text("🔄 Analyzing video for shot detection...")

                try:
                    # Get duration
                    duration = agent.get_video_duration(video_uri)
                    if duration is None:
                        duration = 60  # Default

                    # Analyze video
                    result = agent.analyze_full_video(
                        video_uri=video_uri,
                        duration_seconds=duration,
                        chunk_size=min(duration, 60),
                        start_offset=0
                    )

                    # Extract all shots from segments
                    shot_list = []
                    shot_id = 0

                    for segment in result.get("segment_analyses", []):
                        events = segment.get("events", [])

                        for event in events:
                            # Calculate confidence based on events per minute and classification
                            events_pm = segment.get("events_per_minute", 0)

                            # Heuristic confidence scoring
                            if events_pm > 10:
                                # Likely warmup - lower confidence
                                confidence = 60
                            elif 2 < events_pm < 6:
                                # Likely game - higher confidence
                                confidence = 85
                            else:
                                confidence = 70

                            # Extract audio cues from analysis text
                            analysis_lower = segment.get("analysis", "").lower()
                            audio_cues = []
                            if "swish" in analysis_lower or "swoosh" in analysis_lower:
                                audio_cues.append("Swish")
                                confidence += 15
                            if "clang" in analysis_lower or "clunk" in analysis_lower:
                                audio_cues.append("Clang")
                                confidence += 15

                            confidence = min(confidence, 95)  # Cap at 95%

                            shot_list.append({
                                "id": shot_id,
                                "timestamp": event.get("timestamp", 0),
                                "player": event.get("player", "Unknown"),
                                "shot_type": event.get("shot_type", "shot"),
                                "ai_classification": "MADE" if event.get("made", False) else "MISSED",
                                "user_classification": None,  # User hasn't reviewed yet
                                "confidence": confidence,
                                "audio_cues": audio_cues,
                                "segment_analysis": segment.get("analysis", ""),
                                "thumbnail": None,  # Will be extracted on demand
                                "corrected": False
                            })
                            shot_id += 1

                    # Store in session state
                    st.session_state.shot_list = shot_list
                    st.session_state.review_video_uri = video_uri

                    progress_bar.progress(100)
                    status_text.success(f"✅ Detected {len(shot_list)} shots!")

                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Analysis failed: {str(e)}")
                    logger.error(f"Analysis error: {e}")

        else:
            # Show review interface
            shot_list = st.session_state.shot_list

            st.subheader(f"📋 Step 2: Review & Correct ({len(shot_list)} shots)")

            # Summary stats
            col1, col2, col3, col4 = st.columns(4)

            num_corrected = sum(1 for s in shot_list if s["corrected"])
            num_low_conf = sum(1 for s in shot_list if s["confidence"] < 70)
            num_pending = len(shot_list) - num_corrected

            with col1:
                st.metric("Total Shots", len(shot_list))
            with col2:
                st.metric("Reviewed", num_corrected)
            with col3:
                st.metric("Pending", num_pending)
            with col4:
                st.metric("Low Confidence", num_low_conf, delta="⚠️ Review these")

            st.divider()

            # Video Player Section
            st.subheader("📺 Video Player")

            # Initialize current timestamp in session state
            if 'current_timestamp' not in st.session_state:
                st.session_state.current_timestamp = 0

            # Get signed URL for video playback
            try:
                signed_url = get_signed_url(video_uri)

                # Add timestamp fragment to URL if specified
                if st.session_state.current_timestamp > 0:
                    video_url = f"{signed_url}#t={st.session_state.current_timestamp}"
                else:
                    video_url = signed_url

                # Display video player
                st.video(video_url)

                # Show current timestamp
                current_time = st.session_state.current_timestamp
                minutes = current_time // 60
                seconds = current_time % 60
                if current_time > 0:
                    st.caption(f"⏱️ Currently at: {minutes}:{seconds:02d}")

            except Exception as e:
                st.error(f"Error loading video: {str(e)}")
                logger.error(f"Video player error: {e}")

            st.divider()

            # Bulk actions
            st.markdown("**🛠️ Bulk Actions:**")
            col_bulk1, col_bulk2, col_bulk3 = st.columns(3)

            with col_bulk1:
                if st.button("✓ Mark All as Correct", use_container_width=True):
                    for shot in shot_list:
                        shot["user_classification"] = shot["ai_classification"]
                        shot["corrected"] = True
                    st.session_state.shot_list = shot_list
                    st.success("✅ All shots marked as correct!")
                    st.rerun()

            with col_bulk2:
                if st.button("🔄 Reset All Reviews", use_container_width=True):
                    for shot in shot_list:
                        shot["user_classification"] = None
                        shot["corrected"] = False
                    st.session_state.shot_list = shot_list
                    st.success("🔄 All reviews reset!")
                    st.rerun()

            with col_bulk3:
                if st.button("🗑️ Start Over", use_container_width=True):
                    del st.session_state.shot_list
                    del st.session_state.review_video_uri
                    st.rerun()

            st.divider()

            # Filter shots if needed
            display_shots = shot_list
            if show_only_uncertain:
                display_shots = [s for s in shot_list if s["confidence"] < 70]
                st.info(f"Showing {len(display_shots)} low confidence shots (< 70%)")

            # Display shots for review
            for shot in display_shots:
                shot_id = shot["id"]
                timestamp = shot["timestamp"]
                minutes = timestamp // 60
                seconds = timestamp % 60
                time_str = f"{minutes}:{seconds:02d}"

                # Determine card class
                card_class = "shot-card"
                if shot["corrected"]:
                    if shot["user_classification"] != shot["ai_classification"]:
                        card_class = "shot-card-corrected"
                    else:
                        card_class = "shot-card-correct"
                elif shot["confidence"] < 70:
                    card_class = "shot-card-low-confidence"

                # Confidence color
                conf = shot["confidence"]
                if conf >= 80:
                    conf_class = "confidence-high"
                elif conf >= 60:
                    conf_class = "confidence-medium"
                else:
                    conf_class = "confidence-low"

                with st.container():
                    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

                    # Header row
                    col_header1, col_header2, col_header3, col_header4, col_header5 = st.columns([2, 2, 2, 2, 1])

                    with col_header1:
                        st.markdown(f"**Shot #{shot_id + 1}** | ⏱️ {time_str}")
                    with col_header2:
                        st.markdown(f"**{shot['shot_type'].title()}**")
                    with col_header3:
                        ai_class = shot["ai_classification"]
                        icon = "✅" if ai_class == "MADE" else "❌"
                        st.markdown(f"AI says: **{icon} {ai_class}**")
                    with col_header4:
                        st.markdown(f"<span class='{conf_class}'>Confidence: {conf}%</span>", unsafe_allow_html=True)
                    with col_header5:
                        # Watch button to jump to timestamp
                        if st.button("▶️ Watch", key=f"watch_{shot_id}", use_container_width=True):
                            # Update session state to jump to this timestamp
                            # Go back 3 seconds for context
                            st.session_state.current_timestamp = max(0, timestamp - 3)
                            st.rerun()

                    # Thumbnail (if enabled)
                    if extract_thumbnails and shot["thumbnail"] is None:
                        with st.spinner("Loading thumbnail..."):
                            shot["thumbnail"] = extract_frame_thumbnail(video_uri, timestamp)

                    if shot["thumbnail"]:
                        col_img, col_details = st.columns([1, 2])

                        with col_img:
                            st.markdown(f'<img src="{shot["thumbnail"]}" width="100%">', unsafe_allow_html=True)

                        with col_details:
                            st.caption(f"**Player:** {shot['player']}")
                            if shot["audio_cues"]:
                                st.caption(f"🔊 Audio: {', '.join(shot['audio_cues'])}")
                            else:
                                st.caption("🔊 Audio: No clear cues detected")
                    else:
                        st.caption(f"**Player:** {shot['player']}")

                    # Review buttons
                    st.markdown("**Your Review:**")
                    col_btn1, col_btn2, col_btn3 = st.columns(3)

                    with col_btn1:
                        if st.button("✅ Correct (MADE)", key=f"made_{shot_id}", use_container_width=True):
                            shot["user_classification"] = "MADE"
                            shot["corrected"] = True
                            st.session_state.shot_list = shot_list
                            st.rerun()

                    with col_btn2:
                        if st.button("❌ Correct (MISSED)", key=f"missed_{shot_id}", use_container_width=True):
                            shot["user_classification"] = "MISSED"
                            shot["corrected"] = True
                            st.session_state.shot_list = shot_list
                            st.rerun()

                    with col_btn3:
                        if st.button("✓ AI is Correct", key=f"confirm_{shot_id}", use_container_width=True):
                            shot["user_classification"] = shot["ai_classification"]
                            shot["corrected"] = True
                            st.session_state.shot_list = shot_list
                            st.rerun()

                    # Show if corrected
                    if shot["corrected"]:
                        user_class = shot["user_classification"]
                        if user_class != shot["ai_classification"]:
                            st.success(f"✅ Corrected: AI said {shot['ai_classification']} → You said {user_class}")
                        else:
                            st.success(f"✅ Confirmed: {user_class}")

                    st.markdown('</div>', unsafe_allow_html=True)

            st.divider()

            # Export section
            if num_corrected > 0:
                st.subheader("💾 Step 3: Export Corrected Data")

                # Prepare export data
                export_data = []
                for shot in shot_list:
                    if shot["corrected"]:
                        minutes = shot["timestamp"] // 60
                        seconds = shot["timestamp"] % 60
                        time_str = f"{minutes}:{seconds:02d}"

                        export_data.append({
                            "Timestamp": time_str,
                            "Timestamp (seconds)": shot["timestamp"],
                            "Player": shot["player"],
                            "Shot Type": shot["shot_type"],
                            "Outcome": shot["user_classification"],
                            "AI Classification": shot["ai_classification"],
                            "Corrected": "Yes" if shot["user_classification"] != shot["ai_classification"] else "No",
                            "Confidence": f"{shot['confidence']}%",
                            "Audio Cues": ", ".join(shot["audio_cues"]) if shot["audio_cues"] else "None"
                        })

                df_export = pd.DataFrame(export_data)

                col_exp1, col_exp2, col_exp3 = st.columns(3)

                with col_exp1:
                    csv_data = df_export.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv_data,
                        file_name=f"shot_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                with col_exp2:
                    json_data = json.dumps([s for s in shot_list if s["corrected"]], indent=2)
                    st.download_button(
                        label="📥 Download JSON",
                        data=json_data,
                        file_name=f"shot_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )

                with col_exp3:
                    st.metric("Ready to Export", f"{num_corrected} shots")

                # Preview
                with st.expander("📊 Preview Export Data"):
                    st.dataframe(df_export, use_container_width=True)

                # Accuracy stats
                num_changed = sum(1 for s in shot_list if s["corrected"] and s["user_classification"] != s["ai_classification"])
                if num_corrected > 0:
                    ai_accuracy = ((num_corrected - num_changed) / num_corrected) * 100
                    st.info(f"📊 **AI Accuracy:** {ai_accuracy:.1f}% ({num_corrected - num_changed}/{num_corrected} correct)")

    else:
        st.info("👈 Load a video to begin shot review")

    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #718096; padding: 1rem;'>
        Shot Review & Correction - Human-in-the-Loop AI Workflow
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    required_vars = ["GCP_PROJECT_ID", "GCP_BUCKET_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        st.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
    else:
        main()
