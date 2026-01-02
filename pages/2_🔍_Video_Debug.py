"""
Video Debug & Q&A Page - Interactive video analysis debugging
Ask the model questions about specific moments to understand what it sees
"""
import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import storage
from agent import create_coach_agent
from google.genai import types
import logging
import subprocess
import tempfile
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Video Debug & Q&A",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #E74C3C;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4A5568;
        text-align: center;
        margin-bottom: 2rem;
    }
    .question-box {
        background-color: #EBF8FF;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3182CE;
        margin: 1rem 0;
    }
    .answer-box {
        background-color: #F0FFF4;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #38A169;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def extract_frame_at_timestamp(video_uri: str, timestamp_sec: int, output_path: str) -> bool:
    """
    Extract a single frame from video at specified timestamp

    Args:
        video_uri: GCS URI or signed URL
        timestamp_sec: Time in seconds
        output_path: Where to save the frame

    Returns:
        True if successful
    """
    try:
        # If GCS URI, generate signed URL
        if video_uri.startswith("gs://"):
            path_parts = video_uri[5:].split("/", 1)
            bucket_name = path_parts[0]
            blob_path = path_parts[1] if len(path_parts) > 1 else ""

            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=3600,
                method="GET"
            )
            video_source = signed_url
        else:
            video_source = video_uri

        # Extract frame using ffmpeg
        cmd = [
            'ffmpeg',
            '-ss', str(timestamp_sec),
            '-i', video_source,
            '-frames:v', '1',
            '-q:v', '2',
            '-y',
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
            check=True
        )

        return os.path.exists(output_path)

    except Exception as e:
        logger.error(f"Error extracting frame: {e}")
        return False


def upload_to_gcs(local_file_path: str, bucket_name: str) -> str:
    """Upload a local file to GCS and return URI"""
    try:
        import time
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)

        file_name = Path(local_file_path).name
        blob_name = f"debug_uploads/{int(time.time())}_{file_name}"
        blob = bucket.blob(blob_name)

        blob.upload_from_filename(local_file_path)

        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        return gcs_uri

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return None


def main():
    """Main Streamlit application for video debugging"""

    # Header
    st.markdown('<div class="main-header">🔍 Video Debug & Q&A</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Ask questions about specific moments to understand what the model sees</div>', unsafe_allow_html=True)

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
            format_func=lambda x: sport_options[x],
            help="Choose which sport context to use"
        )

        st.divider()

        # Model selector
        model_options = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-3-pro-preview",
            "gemini-3-pro-image-preview",
        ]

        selected_model = st.selectbox(
            "Select Model",
            options=model_options,
            index=0,
            help="Try different models to compare results"
        )

        st.divider()

        # Debug options
        st.subheader("🔬 Debug Options")

        show_reasoning = st.checkbox(
            "Request Reasoning",
            value=True,
            help="Ask model to explain its thinking"
        )

        extract_frames = st.checkbox(
            "Extract Frames",
            value=False,
            help="Extract and show frames at specific timestamps"
        )

        st.divider()

        # Environment info
        st.info(f"""
        **GCP Project:** {os.getenv('GCP_PROJECT_ID', 'Not set')}
        **GCP Bucket:** {os.getenv('GCP_BUCKET_NAME', 'Not set')}
        """)

    # Main content
    st.subheader("📹 Video Input")

    # Input mode selector
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
            placeholder="gs://bucket-name/path/to/video.mp4",
            help="Enter the GCS URI of the video to debug"
        )

        if gcs_input:
            if not gcs_input.startswith("gs://"):
                gcs_input = "gs://" + gcs_input
            video_uri = gcs_input
            st.success(f"✅ Video loaded: {video_uri}")
    else:
        uploaded_file = st.file_uploader(
            "Select a video file",
            type=["mp4", "mov", "avi"],
            help="Upload a short video clip to debug"
        )

        if uploaded_file:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.info(f"📊 Selected: {uploaded_file.name} ({file_size_mb:.1f}MB)")

            if st.button("📤 Upload to GCS", type="primary"):
                bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")

                # Save to temp file
                temp_path = f"/tmp/{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.read())

                # Upload
                with st.spinner("Uploading..."):
                    video_uri = upload_to_gcs(temp_path, bucket_name)

                if video_uri:
                    st.success(f"✅ Uploaded: {video_uri}")
                    st.session_state.debug_video_uri = video_uri

                # Clean up
                os.remove(temp_path)

    # Check session state for video
    if 'debug_video_uri' in st.session_state:
        video_uri = st.session_state.debug_video_uri

    # Q&A Interface
    if video_uri:
        st.divider()
        st.subheader("💬 Ask Questions About This Video")

        # Initialize chat history
        if 'debug_chat_history' not in st.session_state:
            st.session_state.debug_chat_history = []

        # Common question templates
        st.markdown("**Quick Questions:**")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📊 What happens in this video?"):
                st.session_state.quick_question = "Describe everything that happens in this video in detail."

        with col2:
            if st.button("🏀 List all shots"):
                st.session_state.quick_question = "List every shot attempt you see, with timestamps and outcomes (made/missed)."

        with col3:
            if st.button("❓ Describe at 0:05"):
                st.session_state.quick_question = "What exactly happens at the 5 second mark? Describe in detail."

        # Custom question input
        question_col1, question_col2 = st.columns([5, 1])

        with question_col1:
            default_question = st.session_state.get('quick_question', '')
            user_question = st.text_area(
                "Your Question:",
                value=default_question,
                placeholder="e.g., 'What happens at 0:23? Did that shot go in? Explain your reasoning.'",
                height=100,
                key="user_question_input"
            )

        with question_col2:
            st.write("")  # Spacing
            st.write("")  # Spacing
            ask_button = st.button("🚀 Ask", type="primary", use_container_width=True)

        # Clear quick question after use
        if 'quick_question' in st.session_state:
            del st.session_state.quick_question

        # Process question
        if ask_button and user_question:
            # Initialize agent
            with st.spinner(f"Initializing {selected_sport} agent..."):
                agent = create_coach_agent(model_name=selected_model, sport=selected_sport)

            # Build prompt
            reasoning_instruction = ""
            if show_reasoning:
                reasoning_instruction = """

**IMPORTANT: Explain your reasoning step by step.
For any classification (made/missed, game/warmup, etc.), describe:
1. What visual cues you see
2. How you interpreted them
3. Why you reached your conclusion**
"""

            prompt = f"""{user_question}

{reasoning_instruction}

Analyze the video carefully and provide a detailed, accurate answer."""

            # Analyze the video
            with st.spinner("Analyzing video..."):
                try:
                    # Get video duration
                    duration = agent.get_video_duration(video_uri)
                    if duration is None:
                        duration = 30

                    # Analyze full video or specific segment
                    analysis, tokens = agent.video_tool.analyze_video_segment(
                        video_uri=video_uri,
                        start_sec=0,
                        end_sec=min(duration, 60),  # Max 60 seconds for debug
                        prompt=prompt
                    )

                    # Add to chat history
                    st.session_state.debug_chat_history.append({
                        'question': user_question,
                        'answer': analysis,
                        'model': selected_model,
                        'tokens': tokens,
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    })

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    logger.error(f"Analysis error: {e}")

        # Display chat history
        if st.session_state.debug_chat_history:
            st.divider()
            st.subheader("📝 Conversation History")

            for idx, item in enumerate(reversed(st.session_state.debug_chat_history)):
                with st.expander(f"Q{len(st.session_state.debug_chat_history) - idx}: {item['question'][:60]}... ({item['timestamp']})", expanded=(idx==0)):
                    st.markdown(f"**🤔 Question:**")
                    st.markdown(f'<div class="question-box">{item["question"]}</div>', unsafe_allow_html=True)

                    st.markdown(f"**🤖 Answer ({item['model']}):**")
                    st.markdown(f'<div class="answer-box">{item["answer"]}</div>', unsafe_allow_html=True)

                    # Token usage
                    tokens = item.get('tokens', {})
                    if tokens.get('total_tokens', 0) > 0:
                        st.caption(f"📊 Tokens: {tokens.get('total_tokens', 0):,} total ({tokens.get('prompt_tokens', 0):,} prompt + {tokens.get('output_tokens', 0):,} output)")

            # Clear history button
            if st.button("🗑️ Clear History"):
                st.session_state.debug_chat_history = []
                st.rerun()

        # Frame extraction tool
        if extract_frames:
            st.divider()
            st.subheader("🎞️ Frame Extraction")

            timestamp_input = st.number_input(
                "Extract frame at timestamp (seconds):",
                min_value=0,
                max_value=600,
                value=5,
                step=1
            )

            if st.button("📸 Extract Frame"):
                with st.spinner(f"Extracting frame at {timestamp_input}s..."):
                    temp_frame = f"/tmp/frame_{timestamp_input}.jpg"
                    success = extract_frame_at_timestamp(video_uri, timestamp_input, temp_frame)

                    if success:
                        st.success(f"✅ Extracted frame at {timestamp_input}s")
                        st.image(temp_frame, caption=f"Frame at {timestamp_input}s", use_container_width=True)

                        # Analyze this specific frame
                        if st.button("🔍 Analyze This Frame"):
                            with st.spinner("Analyzing frame..."):
                                agent = create_coach_agent(model_name=selected_model, sport=selected_sport)

                                # Read frame as bytes
                                with open(temp_frame, 'rb') as f:
                                    frame_data = f.read()

                                # Analyze frame
                                frame_part = types.Part.from_bytes(data=frame_data, mime_type="image/jpeg")

                                response = agent.client.models.generate_content(
                                    model=selected_model,
                                    contents=[
                                        f"Describe this frame from a {selected_sport} video in detail. What's happening? Where is the ball? What are the players doing?",
                                        frame_part
                                    ],
                                    config=types.GenerateContentConfig(temperature=0.2)
                                )

                                st.markdown("**Frame Analysis:**")
                                st.info(response.text)
                    else:
                        st.error("❌ Failed to extract frame")

    else:
        st.info("👈 Load a video to start debugging")

    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #718096; padding: 1rem;'>
        Video Debug & Q&A - Understanding what the model sees
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    required_vars = ["GCP_PROJECT_ID", "GCP_BUCKET_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        st.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
    else:
        main()
