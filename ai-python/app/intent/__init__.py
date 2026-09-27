"""意图识别的前两步，由 begin_node 调用。

阅读顺序以 app/graphs/hospital/nodes/begin.py 的 begin_node 为准：
高精度规则（rules.py）→ 本地分类器（Ollama 或保留的 sklearn）→ 云端大模型。
本包只负责前两步，串联在 cascade.py。
"""

from app.intent.cascade import LocalRouteResult, route_locally

__all__ = ["LocalRouteResult", "route_locally"]
