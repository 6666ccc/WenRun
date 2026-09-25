"""切块阶段的长度、重叠和分词器配置；向量模型配置在 rag/chroma.py。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IngestionConfig:
    """控制每段最大长度，以及相邻段重复保留多少文字。"""

    max_tokens: int = 512
    overlap_tokens: int = 64
    min_chunk_tokens: int = 8
    tokenizer_model: str = "Qwen/Qwen2.5-0.5B"

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if not 0 <= self.overlap_tokens < self.max_tokens:
            raise ValueError("overlap_tokens must be in [0, max_tokens)")
        if self.min_chunk_tokens < 1:
            raise ValueError("min_chunk_tokens must be positive")
        if not self.tokenizer_model.strip():
            raise ValueError("tokenizer_model must not be empty")
