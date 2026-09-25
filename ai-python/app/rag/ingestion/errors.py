"""把文档预处理失败按阶段区分，方便上传接口提示和日志定位。"""


class DocumentParseError(RuntimeError):
    """文件无法解析为内部文档结构。"""


class DocumentCleaningError(RuntimeError):
    """解析出的内容无法安全清理。"""


class DocumentClassificationError(RuntimeError):
    """清理后的文档无法归类。"""


class ChunkingError(RuntimeError):
    """已分类的文档无法切成可生成向量的片段。"""
