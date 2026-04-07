from typing import Optional, Callable
from faster_whisper import WhisperModel
from pathlib import Path

# 本地模型目录（通过 docker-compose volume 挂载，不依赖 HF Hub）
_LOCAL_MODEL_DIR = Path(__file__).parent.parent / "models" / "whisper-base"


def _fmt_time(seconds: float) -> str:
    """将秒数格式化为 m:ss"""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


class Transcriber:
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self.model: Optional[WhisperModel] = None
        self.detected_language: Optional[str] = None

    def _load_model(self):
        """延迟加载模型，优先使用本地目录"""
        if self.model is None:
            compute_type = "float16" if self.device == "cuda" else "int8"
            # 本地目录存在时直接加载，否则回退到按名称下载
            model_path = str(_LOCAL_MODEL_DIR) if _LOCAL_MODEL_DIR.exists() else self.model_size
            self.model = WhisperModel(
                model_path,
                device=self.device,
                compute_type=compute_type
            )

    def transcribe(self, audio_path: str, progress_callback: Optional[Callable] = None) -> str:
        """转录音频文件

        Args:
            audio_path: 音频文件路径
            progress_callback: 可选进度回调 (stage, text) -> None，每 5% 调用一次

        Returns:
            转录文本
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        self._load_model()

        segments, info = self.model.transcribe(
            str(audio_file),
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
        total = info.duration or 1.0  # 防止除零

        # 收集文本，同时上报进度
        text_only_lines = []
        last_reported_pct = -1

        for segment in segments:
            text = segment.text.strip()
            if text:
                text_only_lines.append(text)

            if progress_callback and total > 0:
                pct = int(segment.end / total * 100)
                # 每 5% 上报一次
                if pct >= last_reported_pct + 5:
                    elapsed = _fmt_time(segment.end)
                    duration = _fmt_time(total)
                    progress_callback(
                        "transcribing",
                        f"转录中... {pct}% ({elapsed} / {duration})"
                    )
                    last_reported_pct = pct

        # 合并段落
        plain_text = "\n\n".join(text_only_lines)

        return plain_text

# 全局转录器实例
transcriber = Transcriber()
