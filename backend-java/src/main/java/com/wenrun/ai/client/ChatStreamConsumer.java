package com.wenrun.ai.client;

import com.wenrun.ai.vo.ChatStreamEventVO;

@FunctionalInterface
public interface ChatStreamConsumer {

    void accept(ChatStreamEventVO event);
}


