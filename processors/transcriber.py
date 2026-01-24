from typing import Optional
from faster_whisper import WhisperModel
from pathlib import Path

class Transcriber:
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self.model: Optional[WhisperModel] = None
        self.detected_language: Optional[str] = None

    def _load_model(self):
        """延迟加载模型"""
        if self.model is None:
            compute_type = "float16" if self.device == "cuda" else "int8"
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type
            )

    def transcribe(self, audio_path: str) -> str:
        """转录音频文件

        Args:
            audio_path: 音频文件路径

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

        # 收集文本
        text_only_lines = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                text_only_lines.append(text)

        # 合并段落
        plain_text = "\n\n".join(text_only_lines)

        return plain_text

# 全局转录器实例
transcriber = Transcriber()
