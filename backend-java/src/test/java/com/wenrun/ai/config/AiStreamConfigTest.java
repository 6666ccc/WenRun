package com.wenrun.ai.config;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;

import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringJUnitConfig(AiStreamConfig.class)
class AiStreamConfigTest {

    @Autowired
    @Qualifier("aiStreamExecutor")
    private AsyncTaskExecutor streamExecutor;

    @Test
    void registersNamedAsyncTaskExecutor() throws Exception {
        assertNotNull(streamExecutor);
        AtomicBoolean ran = new AtomicBoolean(false);
        streamExecutor.submit(() -> ran.set(true)).get();
        assertTrue(ran.get());
    }
}
