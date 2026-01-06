"""
Batch Video Rename Page - Streamlit Multi-page App
Analyze multiple short videos and generate descriptive filenames
"""
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import storage
from agent import create_coach_agent
import logging
from datetime import datetime
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Batch Video Rename",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #4A90E2;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4A5568;
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)


def list_gcs_videos(bucket_name: str, folder_path: str = "") -> list:
    """
    List all video files in a GCS bucket/folder

    Args:
        bucket_name: GCS bucket name
        folder_path: Optional folder path within bucket

    Returns:
        List of GCS URIs for video files
    """
    try:
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)

        # List blobs with prefix
        blobs = bucket.list_blobs(prefix=folder_path)

        # Filter for video files
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        video_uris = []

        for blob in blobs:
            if any(blob.name.lower().endswith(ext) for ext in video_extensions):
                video_uris.append(f"gs://{bucket_name}/{blob.name}")

        return video_uris

    except Exception as e:
        logger.error(f"Error listing GCS videos: {e}")
        st.error(f"Error listing videos: {str(e)}")
        return []


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
        blob_name = f"batch_uploads/{int(time.time())}_{file_name}"
        blob = bucket.blob(blob_name)

        # Upload the file
        blob.upload_from_filename(local_file_path)

        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        return gcs_uri

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return None


def rename_gcs_file(old_uri: str, new_filename: str) -> tuple[bool, str]:
    """
    Rename a file in GCS by copying to new name and optionally deleting old

    Args:
        old_uri: Original GCS URI
        new_filename: New filename (without extension - will preserve original extension)

    Returns:
        Tuple of (success, new_uri or error_message)
    """
    try:
        # Parse old URI
        if not old_uri.startswith("gs://"):
            return False, "Invalid GCS URI"

        path_parts = old_uri[5:].split("/", 1)
        bucket_name = path_parts[0]
        old_blob_name = path_parts[1] if len(path_parts) > 1 else ""

        # Get file extension from old name
        old_path = Path(old_blob_name)
        extension = old_path.suffix

        # Generate new blob name (keep same directory, change filename)
        new_blob_name = str(old_path.parent / f"{new_filename}{extension}")

        # Copy to new name
        storage_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
        bucket = storage_client.bucket(bucket_name)
        old_blob = bucket.blob(old_blob_name)
        new_blob = bucket.blob(new_blob_name)

        # Copy
        bucket.copy_blob(old_blob, bucket, new_blob_name)

        new_uri = f"gs://{bucket_name}/{new_blob_name}"

        return True, new_uri

    except Exception as e:
        logger.error(f"Rename error: {str(e)}")
        return False, str(e)


def main():
    """Main Streamlit application for batch video rename"""

    # Header
    st.markdown('<div class="main-header">📦 Batch Video Rename</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Analyze multiple videos and generate descriptive filenames</div>', unsafe_allow_html=True)

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
            help="Choose which sport to analyze"
        )

        st.divider()

        # Model selector
        model_options = [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-2.5-pro",
            "gemini-3-pro-preview",
        ]

        selected_model = st.selectbox(
            "Select Model",
            options=model_options,
            index=0,
            help="Faster models recommended for batch processing"
        )

        st.divider()

        # Analysis settings
        max_duration = st.slider(
            "Max Duration to Analyze (seconds)",
            min_value=5,
            max_value=60,
            value=30,
            step=5,
            help="Analyze only the first N seconds of each video (faster)"
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
        options=["GCS Folder", "Upload Files"],
        horizontal=True
    )

    video_list = []

    if input_mode == "GCS Folder":
        # GCS folder input
        col1, col2 = st.columns([3, 1])

        with col1:
            folder_path = st.text_input(
                "GCS Folder Path (optional)",
                value="",
                placeholder="e.g., 'clips/' or leave empty for root",
                help="Enter folder path within the bucket (leave empty for root)"
            )

        with col2:
            st.write("")  # Spacing
            st.write("")  # Spacing
            if st.button("📂 Load Videos", type="primary"):
                bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")

                with st.spinner("Loading videos from GCS..."):
                    video_list = list_gcs_videos(bucket_name, folder_path)

                if video_list:
                    st.session_state.video_list = video_list
                    st.success(f"✅ Found {len(video_list)} videos")
                else:
                    st.warning("⚠️ No videos found in specified folder")

    else:
        # File upload mode
        uploaded_files = st.file_uploader(
            "Select video files to upload",
            type=["mp4", "mov", "avi"],
            accept_multiple_files=True,
            help="Upload multiple short video clips"
        )

        if uploaded_files:
            st.info(f"📊 Selected {len(uploaded_files)} file(s)")

            if st.button("📤 Upload to GCS", type="primary"):
                bucket_name = os.getenv("GCP_BUCKET_NAME", "bball_project")
                uploaded_uris = []

                progress_bar = st.progress(0)
                status_text = st.empty()

                for idx, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Uploading {uploaded_file.name}...")

                    # Save to temp file
                    temp_path = f"/tmp/{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.read())

                    # Upload to GCS
                    gcs_uri = upload_to_gcs(temp_path, bucket_name)

                    if gcs_uri:
                        uploaded_uris.append(gcs_uri)

                    # Clean up temp file
                    os.remove(temp_path)

                    # Update progress
                    progress_bar.progress((idx + 1) / len(uploaded_files))

                progress_bar.progress(100)
                status_text.success(f"✅ Uploaded {len(uploaded_uris)} videos")

                # Store in session state
                st.session_state.video_list = uploaded_uris
                video_list = uploaded_uris

    # Check for videos in session state
    if 'video_list' in st.session_state and st.session_state.video_list:
        video_list = st.session_state.video_list

    # Display video list and analysis
    if video_list:
        st.divider()
        st.subheader(f"📋 Videos to Process ({len(video_list)})")

        # Display video list in expandable section
        with st.expander("View video list", expanded=False):
            for idx, uri in enumerate(video_list, 1):
                st.text(f"{idx}. {uri}")

        st.divider()

        # Analysis section
        st.subheader("🎬 Analysis & Rename")

        if st.button("🚀 Analyze All Videos", type="primary", use_container_width=True):
            # Initialize agent
            with st.spinner(f"Initializing {selected_sport} agent..."):
                agent = create_coach_agent(model_name=selected_model, sport=selected_sport)

            # Process each video
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, video_uri in enumerate(video_list):
                # Extract filename
                original_filename = Path(video_uri).name

                status_text.text(f"Analyzing {idx + 1}/{len(video_list)}: {original_filename}")

                try:
                    # Get description and suggested filename
                    description, suggested_filename = agent.describe_for_filename(
                        video_uri=video_uri,
                        max_duration=max_duration
                    )

                    # Preserve extension
                    extension = Path(original_filename).suffix
                    suggested_filename_with_ext = f"{suggested_filename}{extension}"

                    results.append({
                        "Original URI": video_uri,
                        "Original Filename": original_filename,
                        "Description": description,
                        "Suggested Filename": suggested_filename_with_ext,
                        "Suggested Base": suggested_filename  # For renaming
                    })

                except Exception as e:
                    logger.error(f"Error analyzing {video_uri}: {e}")
                    results.append({
                        "Original URI": video_uri,
                        "Original Filename": original_filename,
                        "Description": f"Error: {str(e)}",
                        "Suggested Filename": original_filename,
                        "Suggested Base": Path(original_filename).stem
                    })

                # Update progress
                progress_bar.progress((idx + 1) / len(video_list))

            progress_bar.progress(100)
            status_text.success(f"✅ Analyzed {len(results)} videos")

            # Store results in session state
            st.session_state.batch_results = results

        # Display results if available
        if 'batch_results' in st.session_state and st.session_state.batch_results:
            st.divider()
            st.subheader("📊 Analysis Results")

            results = st.session_state.batch_results

            # Create DataFrame for display (without the base filename column)
            display_df = pd.DataFrame([
                {
                    "Original Filename": r["Original Filename"],
                    "Description": r["Description"],
                    "Suggested Filename": r["Suggested Filename"]
                }
                for r in results
            ])

            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # Export options
            st.divider()
            st.subheader("💾 Export Options")

            col1, col2, col3 = st.columns(3)

            with col1:
                # Download CSV mapping
                csv_data = display_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV Mapping",
                    data=csv_data,
                    file_name=f"video_rename_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col2:
                # Copy files with new names (keeps originals)
                if st.button("📋 Copy with New Names", use_container_width=True):
                    success_count = 0
                    error_count = 0

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for idx, result in enumerate(results):
                        status_text.text(f"Copying {idx + 1}/{len(results)}...")

                        success, new_uri_or_error = rename_gcs_file(
                            result["Original URI"],
                            result["Suggested Base"]
                        )

                        if success:
                            success_count += 1
                            result["New URI"] = new_uri_or_error
                        else:
                            error_count += 1
                            result["Error"] = new_uri_or_error

                        progress_bar.progress((idx + 1) / len(results))

                    progress_bar.progress(100)

                    if success_count > 0:
                        status_text.success(f"✅ Copied {success_count} videos with new names!")
                        if error_count > 0:
                            st.warning(f"⚠️ {error_count} videos failed to copy")
                    else:
                        status_text.error(f"❌ All copies failed")

            with col3:
                # Clear results
                if st.button("🗑️ Clear Results", use_container_width=True):
                    del st.session_state.batch_results
                    del st.session_state.video_list
                    st.rerun()

    else:
        st.info("👈 Select videos from GCS or upload files to begin")

    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #718096; padding: 1rem;'>
        Batch Video Rename - Powered by Gemini AI
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    # Verify environment variables
    required_vars = ["GCP_PROJECT_ID", "GCP_BUCKET_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        st.error(f"""
        ❌ Missing required environment variables: {', '.join(missing_vars)}

        Please set these in your .env file and restart the app.
        """)
    else:
        main()
