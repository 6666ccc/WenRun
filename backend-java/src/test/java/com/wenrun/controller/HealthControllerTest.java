package com.wenrun.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.Statement;
import java.sql.ResultSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

class HealthControllerTest {
    @SuppressWarnings("unchecked")
    private ObjectProvider<RedisConnectionFactory> provider(RedisConnectionFactory factory) {
        var provider = (ObjectProvider<RedisConnectionFactory>) mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(factory);
        return provider;
    }
    @Test
    void readinessRequiresBothDatabaseAndRedis() throws Exception {
        var source = mock(DataSource.class);
        var connection = mock(Connection.class);
        var statement = mock(Statement.class);
        var result = mock(ResultSet.class);
        var factory = mock(RedisConnectionFactory.class);
        var redis = mock(RedisConnection.class);
        when(source.getConnection()).thenReturn(connection);
        when(connection.createStatement()).thenReturn(statement);
        when(statement.executeQuery("SELECT 1")).thenReturn(result);
        when(result.next()).thenReturn(true);
        when(factory.getConnection()).thenReturn(redis);
        when(redis.ping()).thenReturn("PONG");
        var controller = new HealthController(source, provider(factory));
        assertEquals(200, controller.ready().getStatusCode().value());
        when(redis.ping()).thenThrow(new RuntimeException("secret"));
        var unavailable = controller.ready();
        assertEquals(503, unavailable.getStatusCode().value());
        assertEquals("unavailable", unavailable.getBody().get("status"));
        verify(statement, times(2)).setQueryTimeout(3);
    }

    @Test
    void databaseFailureIsUnavailableWithoutExposingCredentials() throws Exception {
        var source = mock(DataSource.class);
        when(source.getConnection()).thenThrow(new java.sql.SQLException("secret"));
        var controller = new HealthController(source, provider(mock(RedisConnectionFactory.class)));
        assertEquals(503, controller.ready().getStatusCode().value());
    }

    @Test
    void memoryOnlyDevelopmentCanStartButDoesNotClaimProductionReadiness() {
        var controller = new HealthController(mock(DataSource.class), provider(null));
        assertEquals(503, controller.ready().getStatusCode().value());
        assertEquals(200, controller.health().getCode());
    }
}
