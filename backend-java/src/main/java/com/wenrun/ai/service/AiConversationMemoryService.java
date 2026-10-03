package com.wenrun.ai.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.concurrency.ConversationExecutionLock;
import com.wenrun.ai.security.DelegatedToolPrincipal;
import com.wenrun.ai.vo.AiSummaryCommitRequest;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.AiConversation;
import com.wenrun.entity.ChatMessage;
import com.wenrun.repository.AiConversationRepository;
import com.wenrun.repository.ChatMessageRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

/** Internal summaries are candidates, not verified medical facts. */
@Service
@RequiredArgsConstructor
public class AiConversationMemoryService {
    private final AiConversationRepository conversations;
    private final ChatMessageRepository messages;
    private final ConversationExecutionLock executionLock;
    private final ObjectMapper json;
    private static final Set<String> FIELDS = Set.of("schema_version", "patient_self_reports",
            "pending_tasks", "superseded_items", "version", "last_message_id");

    public AiConversation owned(DelegatedToolPrincipal principal, String id) {
        AiConversation row = conversations.selectByUserIdAndConversationId(principal.userId(), id);
        if (row == null || !Objects.equals(row.getPatientId(), principal.patientId()))
            throw new BusinessException(ResultCode.NOT_FOUND, "会话不存在或无权访问");
        return row;
    }

    public Map<String, Object> recovery(DelegatedToolPrincipal principal, String id, long after, long upper) {
        owned(principal, id);
        List<ChatMessage> page = messages.selectAfterId(id, principal.userId(), after, upper, 200);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("messages", page);
        long next = page.isEmpty() ? after : page.getLast().getId();
        result.put("nextId", next);
        result.put("hasMore", !messages.selectAfterId(id, principal.userId(), next, upper, 1).isEmpty());
        return result;
    }

    @Transactional
    public Map<String, Object> commit(DelegatedToolPrincipal principal, AiSummaryCommitRequest body) {
        AiConversation row = owned(principal, body.getConversationId());
        if (!executionLock.ownsExecution(principal.userId(), body.getConversationId(), body.getExecutionId()))
            throw new BusinessException(409, "会话执行权已失效，未提交摘要");
        JsonNode candidate = json.valueToTree(body.getSummary());
        validate(candidate);
        long version = row.getSummaryVersion() == null ? 0 : row.getSummaryVersion();
        JsonNode previous = read(row.getSummaryJson());
        if (version == body.getExpectedVersion() + 1 && candidate.equals(previous))
            return ack(candidate); // ACK lost: exact same candidate is idempotent.
        if (version != body.getExpectedVersion() || candidate.path("version").asLong() != version + 1)
            throw new BusinessException(409, "摘要版本已变化，请重新恢复");
        if (previous != null) {
            for (JsonNode report : previous.path("patient_self_reports"))
                if (!contains(candidate.path("patient_self_reports"), report)) throw invalid();
            for (JsonNode item : previous.path("pending_tasks"))
                if (!contains(candidate.path("pending_tasks"), item)
                        && !contains(candidate.path("superseded_items"), item)) throw invalid();
        }
        long after = previous == null ? 0 : previous.path("last_message_id").asLong();
        long last = candidate.path("last_message_id").asLong();
        if (last <= after) throw invalid();
        List<ChatMessage> prefix = messages.selectAfterId(body.getConversationId(), principal.userId(), after, last, 201);
        if (prefix.isEmpty() || prefix.size() > 200 || prefix.getLast().getId() != last
                || !prefix.stream().map(ChatMessage::getId).toList().equals(body.getCoveredMessageIds()))
            throw new BusinessException(409, "摘要覆盖位置不连续，原文继续保留");
        // Only literal patient statements from owned source messages may be added.
        for (JsonNode report : candidate.path("patient_self_reports")) {
            boolean retained = previous != null && contains(previous.path("patient_self_reports"), report);
            if (retained) continue;
            ChatMessage source = prefix.stream().filter(message -> message.getId() == report.path("source_message_id").asLong())
                    .findFirst().orElseThrow(AiConversationMemoryService::invalid);
            if (!"user".equals(source.getRole()) || !source.getContent().contains(report.path("text").asText()))
                throw invalid();
        }
        try {
            if (conversations.commitSummary(principal.userId(), body.getConversationId(), version,
                    json.writeValueAsString(candidate)) != 1)
                throw new BusinessException(409, "摘要提交冲突，原文继续保留");
        } catch (com.fasterxml.jackson.core.JsonProcessingException ex) { throw invalid(); }
        return ack(candidate);
    }

    private static boolean contains(JsonNode values, JsonNode candidate) {
        for (JsonNode value : values) if (value.equals(candidate)) return true;
        return false;
    }
    private JsonNode read(String value) {
        if (value == null) return null;
        try { return json.readTree(value); } catch (Exception ex) { throw invalid(); }
    }
    private static void validate(JsonNode value) {
        if (!value.isObject() || value.path("schema_version").asInt() != 2
                || !value.path("version").isIntegralNumber() || value.path("version").asLong() < 1
                || !value.path("last_message_id").isIntegralNumber() || value.path("last_message_id").asLong() < 1)
            throw invalid();
        value.fieldNames().forEachRemaining(field -> { if (!FIELDS.contains(field)) throw invalid(); });
        for (String field : List.of("patient_self_reports", "pending_tasks", "superseded_items")) {
            if (!value.path(field).isArray() || value.path(field).size() > 200) throw invalid();
        }
        for (JsonNode report : value.path("patient_self_reports")) {
            if (!"user_statement".equals(report.path("source").asText())
                    || !"unverified".equals(report.path("verification").asText())
                    || report.path("text").asText().isBlank() || report.path("text").asText().length() > 500)
                throw invalid();
        }
        for (String field : List.of("pending_tasks", "superseded_items"))
            for (JsonNode line : value.path(field))
                if (!line.isTextual() || line.asText().isBlank() || line.asText().length() > 500) throw invalid();
    }
    private static Map<String, Object> ack(JsonNode summary) {
        return Map.of("version", summary.path("version").asLong(), "lastMessageId", summary.path("last_message_id").asLong());
    }
    private static BusinessException invalid() {
        return new BusinessException(ResultCode.BAD_REQUEST, "摘要格式或来源无效，原文继续保留");
    }
}
