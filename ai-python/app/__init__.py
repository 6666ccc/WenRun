"""温润 AI 服务的代码入口地图。

从 ``main.py`` 开始看：它创建 HTTP 服务并在启动时连接会话检查点。
``api/routes/chat.py`` 接收 Java 的聊天请求；``api/dependencies/auth.py`` 验证 Java
签发的委托令牌；``graphs/hospital/graphs.py`` 把意图识别、回答和工具节点连成流程。
``services/java_tool_client.py`` 负责向 Java 查询或提交医院业务，``rag`` 负责院内资料。

这里的“图”是对话处理步骤及其先后关系；“状态”是步骤之间共享的本轮数据；
“检查点”是暂停后还能继续运行的进度记录；HITL 指写操作前等待真人确认。
"""
