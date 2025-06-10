import streamlit as st
import requests
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeVideoClip, ColorClip, vfx
)
import tempfile
import os
import imageio_ffmpeg

os.environ["IMAGEIO_FFMPEG_EXE"] = imageio_ffmpeg.get_ffmpeg_exe()

st.set_page_config(page_title="🎬 Combine Video Parts", layout="wide")
st.title("🎞️ Final Video Preview (All Parts Combined)")
#online
API_BASE = st.secrets["api_base"]
# localhost
# API_BASE = "http://127.0.0.1:8000/api"

# Must contain batch_ids for all parts (list of strings)
if "batch_ids" not in st.session_state or not st.session_state["batch_ids"]:
    st.error("❌ No part batch IDs found. Please upload parts first.")
    st.stop()

part_batches = st.session_state["batch_ids"]

# UI selection
mode = st.radio("Choose a Mode", ["Normal", "Animated"])
animation_options = []
if mode == "Animated":
    animation_options = st.multiselect(
        "🎨 Choose Animations (applied in rotation per image)",
        ["fadein", "slide_left", "slide_right", "zoom_in", "zoom_out", "grow", "shrink"],
        default=["fadein", "zoom_in"]
    )

# Animation helper
def create_padded_clip(path, duration=3, size=(1080, 720), animation=None):
    base = ImageClip(path).set_duration(duration).resize(height=size[1])
    bg = ColorClip(size=size, color=(0, 0, 0)).set_duration(duration)
    base = base.set_position("center")

    clip = CompositeVideoClip([bg, base])

    if animation == "fadein":
        clip = clip.crossfadein(1)
    elif animation == "slide_left":
        clip = base.set_position(lambda t: ('center', int(size[1] * (1 - t / duration))))
        clip = CompositeVideoClip([bg, clip])
    elif animation == "slide_right":
        clip = base.set_position(lambda t: ('center', int(-size[1] * (1 - t / duration))))
        clip = CompositeVideoClip([bg, clip])
    elif animation == "zoom_in":
        clip = clip.fx(vfx.resize, lambda t: 1 + 0.1 * t)
    elif animation == "zoom_out":
        clip = clip.fx(vfx.resize, lambda t: 1.2 - 0.1 * t)
    elif animation == "grow":
        clip = base.set_start(0).fx(vfx.resize, lambda t: 0.2 + 0.8 * (t / duration))
        clip = CompositeVideoClip([bg, clip])
    elif animation == "shrink":
        clip = base.set_start(0).fx(vfx.resize, lambda t: 1.2 - 0.6 * (t / duration))
        clip = CompositeVideoClip([bg, clip])

    return clip

# 🎬 Generate video
if st.button("🎬 Generate Final Combined Video"):
    part_videos = []

    for idx, batch_id in enumerate(part_batches):
        st.markdown(f"### 🔄 Processing Part {idx+1}")

        LIST_API = f"{API_BASE}/list-images/{batch_id}/"
        GET_IMAGE_API = f"{API_BASE}/get-image/"
        GET_AUDIO_API = f"{API_BASE}/get-audio/{batch_id}/"

        # Fetch image list
        res = requests.get(LIST_API)
        if res.status_code != 200 or not res.json():
            st.error(f"🚫 Failed to fetch images for part {idx+1}")
            continue

        images_meta = res.json()
        image_paths = []
        for img in images_meta:
            file_id = img["file_id"]
            img_res = requests.get(f"{GET_IMAGE_API}{file_id}/")
            if img_res.status_code == 200:
                ext = img["filename"].split(".")[-1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                tmp.write(img_res.content)
                tmp.close()
                image_paths.append(tmp.name)

        # Fetch audio
        audio_res = requests.get(GET_AUDIO_API)
        if audio_res.status_code != 200:
            st.error(f"🎧 Failed to fetch audio for part {idx+1}")
            continue

        audio_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        audio_tmp.write(audio_res.content)
        audio_tmp.close()

        # Create image clips
        duration = st.session_state["audio_duration"] / len(images_meta)
        clips = []
        for i, path in enumerate(image_paths):
            anim = animation_options[i % len(animation_options)] if mode == "Animated" and animation_options else None
            clip = create_padded_clip(path, duration, animation=anim)
            clips.append(clip)

        if clips:
            video = concatenate_videoclips(clips, method="compose")
            audio = AudioFileClip(audio_tmp.name)
              # ✅ Ensure video matches audio duration to prevent early cutoffs
            if video.duration < audio.duration:
                video = video.set_duration(audio.duration)
            final_clip = video.set_audio(audio)
            part_videos.append(final_clip)

    # Combine all parts
    if part_videos:
        final_video = concatenate_videoclips(part_videos, method="chain")
        output_path = os.path.join(tempfile.gettempdir(), f"combined_video.mp4")
        final_video.write_videofile(output_path, fps=24)

        with open(output_path, "rb") as f:
            st.video(f.read())
            st.download_button("⬇️ Download Final Combined Video", f, file_name="final_combined_video.mp4")
    else:
        st.error("🚫 No valid video parts were created.")
