import requests
import streamlit as st
import uuid
from io import BytesIO
from gtts import gTTS
from mutagen.mp3 import MP3

st.set_page_config(page_title="Text to Video", layout="wide")
st.title("📽️ Welcome to the Text-to-Video Project")
#online
API_BASE = st.secrets["api_base"]
#localhost
# API_BASE = "http://127.0.0.1:8000/api"

# 🔁 Cleanup inactive batches older than 1 hour
try:
    # API_BASE = st.secrets["api_base"]
    response = requests.post(f"{API_BASE}/cleanup-inactive-batches/")
    if response.status_code == 200:
        result = response.json()
        st.info(f"🧹 Cleaned up {result['count']} inactive batch(es).")
    else:
        st.success("✅ No inactive batches found. Everything's clean!")
except Exception as e:
    st.error(f"Cleanup error: {e}")


st.title("🎬 Build Your Video in Parts")

UPLOAD_API = f"{API_BASE}/upload-folder/"
SCRIPT_API = f"{API_BASE}/save-script/"

# Session init
if "parts" not in st.session_state:
    st.session_state["parts"] = 0
if "durations" not in st.session_state:
    st.session_state["durations"] = []
if "labels" not in st.session_state:
    st.session_state["labels"] = []
if "video_duration_minutes" not in st.session_state:
    st.session_state["video_duration_minutes"] = 0
if "batch_ids" not in st.session_state:
    st.session_state["batch_ids"] = []

# Step 0: Select total video duration
duration_choice = st.radio("⏱️ Select total video duration", ["1 minute", "2 minutes"])
total_images = 22 if duration_choice == "1 minute" else 44
total_words = 100 if duration_choice == "1 minute" else 200
st.session_state["video_duration_minutes"] = 1 if duration_choice == "1 minute" else 2

# Step 1: Choose number of parts
if st.session_state["parts"] == 0:
    parts = st.number_input("🔢 How many parts do you want to divide your video into?", min_value=1, max_value=10, step=1)
    if st.button("Confirm Parts"):
        st.session_state["parts"] = parts
        st.session_state["durations"] = [100 // parts] * parts
        st.session_state["labels"] = [f"Part {i+1}" for i in range(parts)]
        # Generate unique batch_ids per part
        st.session_state["batch_ids"] = [str(uuid.uuid4()) for _ in range(parts)]
        st.session_state["audio_duration"] = 0
        st.rerun()

# Step 2: Build each part
else:
    total_parts = st.session_state["parts"]
    duration_parts = st.session_state["durations"]
    label_parts = st.session_state["labels"]
    batch_ids = st.session_state["batch_ids"]

    st.subheader("⏱️ Set Part Durations and Labels")

    # Modify durations and labels
    cols = st.columns(total_parts)
    for i in range(total_parts):
        with cols[i]:
            label = st.text_input(f"Label for Part {i+1}", value=label_parts[i], key=f"label_{i}")
            label_parts[i] = label
            val = st.number_input(f"% Duration", min_value=0, max_value=100, value=duration_parts[i], key=f"duration_{i}")
            duration_parts[i] = val

    # Check sum of percentages
    if sum(duration_parts) != 100:
        st.warning(f"⚠️ Duration percentages add up to {sum(duration_parts)}%. They must total 100%.")
    else:
        st.success("✅ Duration split is valid.")

    # Each Part Upload UI
    for i in range(total_parts):
        part_label = label_parts[i]
        percent = duration_parts[i]
        expected_images = round((percent / 100) * total_images)
        expected_words = round((percent / 100) * total_words)

        st.markdown(f"---\n### 📦 {part_label}")
        st.caption(f"🆔 Batch ID for {part_label}: `{batch_ids[i]}`")
        st.info(f"🖼️ **Expected ~{expected_images} images** | ✍️ **Expected ~{expected_words} words**")

        # Image upload
        image_files = st.file_uploader(f"Images for {part_label}", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"img_{i}")

        if image_files:
            st.caption("📷 Preview of selected images (first selected shown first):")
            st.image(image_files, width=150, caption=[img.name for img in image_files])

        # Script input
        calculated_height = max(68, int(expected_words * 1.2))
        script_text = st.text_area(f"Script for {part_label}", height=calculated_height, key=f"script_{i}")

        # Upload button
        if st.button(f"📤 Upload {part_label}"):
            if not image_files or not script_text.strip():
                st.error("❌ Please upload images and write a script.")
                st.stop()

            # Check image count
            if len(image_files) != expected_images:
                st.warning(f"⚠️ You uploaded {len(image_files)} images. Expected: {expected_images}")

            # Upload images
            for img in image_files:
                files = {
                    "image": (img.name, img, "image/jpeg")
                }
                data = {
                    "batch_id": batch_ids[i],
                    "part_number": i + 1
                }
                res = requests.post(UPLOAD_API, files=files, data=data)
                if res.status_code == 200:
                    st.success(f"✅ Uploaded: {img.name}")
                else:
                    st.error(f"❌ Failed to upload {img.name}: {res.text}")

            # Convert script to audio
            try:
                tts = gTTS(text=script_text, lang='en')
                audio_io = BytesIO()
                tts.write_to_fp(audio_io)
                audio_io.seek(0)
                audio = MP3(BytesIO(audio_io.getvalue()))
                duration_sec = audio.info.length
                st.session_state["audio_duration"] = duration_sec
                st.success(f"✅ Audio generated. Duration: {duration_sec:.2f} seconds")

                audio_io.seek(0)
                files = {
                    "audio": ("script.mp3", audio_io, "audio/mpeg")
                }
                data = {
                    "script": script_text,
                    "batch_id": batch_ids[i],
                    "part_number": i + 1,
                    "label": part_label,
                    "percentage": percent
                }
                res = requests.post(SCRIPT_API, files=files, data=data)
                if res.status_code == 200:
                    st.success("✅ Script & audio uploaded.")
                else:
                    st.error(f"❌ Script/audio upload failed: {res.text}")
            except Exception as e:
                st.error(f"🚫 Audio generation error: {e}")

    st.warning(f"Go to next page!")

    
            


