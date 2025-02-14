import os
import requests
import ffmpeg
from pytube import YouTube
from abc import ABC, abstractmethod
import subprocess
import requests
import pandas as pd
from os import makedirs


downloaded_videos_output_dir = "./downloaded-videos"
normalized_videos_output_dir = "./normalized-videos"
merged_output_dir = "./merged"
temp_output_dir = "./temp"

def normalize_video_old(file_name):
    ffmpeg.input(file_name).output(file_name.replace(downloaded_videos_output_dir, normalized_videos_output_dir), vcodec="libx264", acodec="aac", strict="experimental").run(overwrite_output=True)
    print(f"\n✅ Video normalized correctly: {file_name}")
    return file_name.replace(downloaded_videos_output_dir, normalized_videos_output_dir)

class VideoDownloader(ABC):
    @abstractmethod
    def download(self, url, output_dir):
        pass

    def _download_file(self, url, output_dir, filename):
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)

        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB por chunk
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    print(f"\rDownloading: {downloaded_size / (1024 * 1024):.2f}MB / {total_size / (1024 * 1024):.2f}MB", end="")

        print(f"\n✅ Video downloaded correctly: {file_path}")

        if total_size and downloaded_size < total_size:
            print("⚠️ Warning: File is smaller than expected")


        return file_path
    
class SynthesiaDownloader(VideoDownloader):
    def download(self, id, output_dir, result_name):
        url = f"https://api.synthesia.io/v2/videos/{id}"
        headers = {
            "Authorization": "<API_KEY>",
            "accept": "application/json"
        }
        response = requests.get(url, headers=headers)
        url = response.json()['download']
        return self._download_file(url, output_dir, result_name)


class S3Downloader(VideoDownloader):
    def download(self, url, output_dir, result_name):
        return self._download_file(url, output_dir, result_name)

class VideoDownloadContext:
    def __init__(self, strategy: VideoDownloader):
        self.strategy = strategy

    def execute(self, url, output_dir, result_name):
        return self.strategy.download(url, output_dir, result_name)

from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.video.fx import all as vfx

target_width = 1280
target_height = 720

def resize_clip(clip):
    return clip.fx(vfx.resize, height=720)  # Resizes while maintaining aspect ratio

def download_videos(batch_name, videos_list):
  list_file = f"{merged_output_dir}/{batch_name}"
  s3_downloader = VideoDownloadContext(S3Downloader())
  synthesia_downloader = VideoDownloadContext(SynthesiaDownloader())
  video_files = []

  index = 1
  for video_url in videos_list:
    if("https" in video_url):
        video_files.append(s3_downloader.execute(video_url, downloaded_videos_output_dir, f'{batch_name}-{index}.mp4'))
    else:
        video_files.append(synthesia_downloader.execute(video_url, downloaded_videos_output_dir, f'{batch_name}-{index}.mp4'))
    index += 1

  # Extract audios
  audio_files = []
  for video in video_files:
      audio = video.replace('.mp4', '.aac')
      audio_files.append(audio)
      subprocess.run(["ffmpeg", "-i", video, "-q:a", "0", "-map", "a", audio, "-y"], check=True)
  
  merged_video_path = f"{temp_output_dir}/{batch_name}-noaudio.mp4"
  merged_audio_path = f"{temp_output_dir}/{batch_name}-audio.aac"
  scale_filters = "".join([f"[{i}:v]scale=1280:720[v{i}];" for i in range(len(video_files))])
  concat_inputs = "".join([f"[v{i}]" for i in range(len(video_files))])

  # Join videos without audio
  subprocess.run([
      "ffmpeg", *sum([["-i", v] for v in video_files], []),
      "-filter_complex",
      f"{scale_filters}{concat_inputs}concat=n={len(video_files)}:v=1:a=0[outv]",
      "-map", "[outv]", "-c:v", "libx264", "-preset", "ultrafast",
      merged_video_path, "-y"
  ], check=True)

  audio_inputs = "".join([f"[{i}:a]" for i in range(len(audio_files))])

  # Join audios
  subprocess.run([
      "ffmpeg", *sum([["-i", a] for a in audio_files], []),
      "-filter_complex", f"{audio_inputs}concat=n={len(audio_files)}:v=0:a=1[outa]",
      "-map", "[outa]", merged_audio_path, "-y"
  ], check=True)

  # Combine video with audio
  subprocess.run([
      "ffmpeg", "-i", merged_video_path, "-i", merged_audio_path,
      "-c:v", "copy", "-c:a", "aac", "-strict", "experimental",
      f'{merged_output_dir}/{batch_name}.mp4', "-y"
  ], check=True)

  print(f"✅ Videos merged correctly: {batch_name}-merged.mp4")

if __name__ == "__main__": 
  for d in ["downloaded-videos", "merged", "temp"]:
    makedirs(d, exist_ok=True)

  file_path = "./data.xlsx"
  df = pd.read_excel(file_path, engine="openpyxl")
  columns = ["URL or Synthesia ID", "Video ID", "Order", "Video Name"]
  data = df[columns].to_dict(orient="records")

  videos = {}
  for item in data:
      if item["Video Name"].strip() not in videos:
          videos[item["Video Name"].strip()] = {  "urls": [] }
      videos[item["Video Name"]]["urls"].append(item["URL or Synthesia ID"])

  for video_name, video_data in videos.items():
    try:
        download_videos(video_name, video_data["urls"])
    except:
        print(f"❌ Could not process: {video_name}")


  
