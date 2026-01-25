#!/usr/bin/env python3
"""
视频转文字脚本
支持本地视频文件和视频URL（B站、抖音、YouTube等）
使用 faster-whisper 进行语音识别
"""

import os
import sys
import argparse
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VideoTranscriber:
    """视频转录器"""

    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """
        初始化转录器

        Args:
            model_size: Whisper模型大小 (tiny, base, small, medium, large)
            device: 设备类型 (cpu, cuda)
        """
        self.model_size = model_size
        self.device = device
        self.model = None
        self.detected_language = None

    def _load_model(self):
        """延迟加载模型"""
        if self.model is None:
            logger.info(f"正在加载 Whisper 模型: {self.model_size}")
            try:
                from faster_whisper import WhisperModel
                compute_type = "float16" if self.device == "cuda" else "int8"
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=compute_type
                )
                logger.info("模型加载完成")
            except ImportError:
                logger.error("faster-whisper 未安装，请运行: pip install faster-whisper")
                raise
            except Exception as e:
                logger.error(f"模型加载失败: {e}")
                raise

    def extract_audio(self, video_path: str, output_dir: Optional[str] = None) -> str:
        """
        从视频中提取音频

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录

        Returns:
            音频文件路径
        """
        logger.info(f"正在提取音频: {video_path}")

        if output_dir is None:
            output_dir = tempfile.gettempdir()
        else:
            os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, "audio.m4a")

        # 使用 ffmpeg 提取音频为 m4a 格式（单声道 16kHz，适合 Whisper）
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn",  # 不处理视频
            "-ac", "1",  # 单声道
            "-ar", "16000",  # 16kHz 采样率
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            output_path
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"音频提取完成: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"音频提取失败: {e.stderr.decode()}")
            raise
        except FileNotFoundError:
            logger.error("ffmpeg 未安装，请先安装 ffmpeg")
            raise

    def download_video(self, url: str, output_dir: str) -> Tuple[str, str]:
        """
        使用 yt-dlp 下载视频并提取音频

        Args:
            url: 视频URL
            output_dir: 输出目录

        Returns:
            (音频文件路径, 视频标题)
        """
        logger.info(f"正在下载视频: {url}")

        os.makedirs(output_dir, exist_ok=True)

        import uuid
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(output_dir, f"audio_{unique_id}.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192'
            }],
            'postprocessor_args': ['-ac', '1', '-ar', '16000'],
            'prefer_ffmpeg': True,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'unknown')
                logger.info(f"视频标题: {video_title}")

                ydl.download([url])

            # 查找生成的音频文件
            for ext in ['m4a', 'webm', 'mp4', 'mp3', 'wav']:
                audio_file = os.path.join(output_dir, f"audio_{unique_id}.{ext}")
                if os.path.exists(audio_file):
                    logger.info(f"下载完成: {audio_file}")
                    return audio_file, video_title

            raise Exception("未找到下载的音频文件")

        except ImportError:
            logger.error("yt-dlp 未安装，请运行: pip install yt-dlp")
            raise
        except Exception as e:
            logger.error(f"下载失败: {e}")
            raise

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        output_file: Optional[str] = None
    ) -> str:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 指定语言（可选，如 zh, en, ja 等）
            output_file: 输出文件路径（可选）

        Returns:
            转录文本
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        self._load_model()

        logger.info(f"开始转录: {audio_path}")

        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            best_of=5,
            temperature=[0.0, 0.2, 0.4],
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 900,
                "speech_pad_ms": 300
            },
            no_speech_threshold=0.7,
            compression_ratio_threshold=2.3,
            condition_on_previous_text=False
        )

        self.detected_language = info.language
        logger.info(f"检测到的语言: {info.language} (概率: {info.language_probability:.2f})")

        # 用于生成纯文本版本
        text_only_lines = []

        for segment in segments:
            text = segment.text.strip()
            if text:
                text_only_lines.append(text)

        # 合并结果 - md 和 txt 都是纯文本，段落之间有换行
        plain_text = "\n\n".join(text_only_lines)

        logger.info("转录完成")

        # 保存到文件
        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)

            # 保存 Markdown 版本（纯文本）
            md_file = output_file if output_file.endswith('.md') else f"{output_file}.md"
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(plain_text)
            logger.info(f"Markdown 已保存: {md_file}")

            # 保存纯文本版本（相同内容）
            txt_file = output_file.replace('.md', '.txt') if output_file.endswith('.md') else f"{output_file}.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(plain_text)
            logger.info(f"纯文本已保存: {txt_file}")

        return plain_text

    def process_video(
        self,
        input_path: str,
        output_dir: str = "outputs",
        model_size: str = "base",
        language: Optional[str] = None,
        keep_audio: bool = False
    ) -> str:
        """
        处理视频文件或URL

        Args:
            input_path: 视频文件路径或URL
            output_dir: 输出目录
            model_size: 模型大小
            language: 指定语言
            keep_audio: 是否保留临时音频文件

        Returns:
            转录文本
        """
        self.model_size = model_size

        # 判断是URL还是本地文件
        if input_path.startswith(('http://', 'https://')):
            audio_path, video_title = self.download_video(input_path, output_dir)
            output_name = self._sanitize_filename(video_title)
        else:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"文件不存在: {input_path}")
            audio_path = self.extract_audio(input_path, output_dir)
            output_name = Path(input_path).stem

        try:
            output_file = os.path.join(output_dir, output_name)
            result = self.transcribe(audio_path, language, output_file)
            return result
        finally:
            # 清理临时音频文件
            if not keep_audio and os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"已删除临时音频文件: {audio_path}")

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:200]  # 限制长度


def main():
    parser = argparse.ArgumentParser(description='视频转文字工具')
    parser.add_argument('input', help='视频文件路径或视频URL')
    parser.add_argument('-o', '--output', default='outputs', help='输出目录 (默认: outputs)')
    parser.add_argument('-m', '--model', default='base',
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help='Whisper 模型大小 (默认: base)')
    parser.add_argument('-l', '--language', help='指定语言 (如: zh, en, ja)')
    parser.add_argument('-d', '--device', default='cpu',
                        choices=['cpu', 'cuda'],
                        help='设备类型 (默认: cpu)')
    parser.add_argument('--keep-audio', action='store_true',
                        help='保留临时音频文件')

    args = parser.parse_args()

    # 检查 ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("错误: 未找到 ffmpeg，请先安装")
        logger.info("安装方法:")
        logger.info("  macOS:   brew install ffmpeg")
        logger.info("  Ubuntu:  sudo apt install ffmpeg")
        logger.info("  Windows: https://ffmpeg.org/download.html")
        sys.exit(1)

    transcriber = VideoTranscriber(model_size=args.model, device=args.device)

    try:
        result = transcriber.process_video(
            input_path=args.input,
            output_dir=args.output,
            model_size=args.model,
            language=args.language,
            keep_audio=args.keep_audio
        )
        print("\n" + "="*60)
        print("转录完成!")
        print("="*60)
        print(f"\n输出文件保存在: {args.output}/\n")
    except Exception as e:
        logger.error(f"处理失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
