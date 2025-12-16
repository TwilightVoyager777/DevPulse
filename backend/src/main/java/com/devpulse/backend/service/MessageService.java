package com.devpulse.backend.service;

import com.devpulse.backend.dto.session.*;
import com.devpulse.backend.event.AiTaskEvent;
import com.devpulse.backend.event.TaskStatusEvent;
import com.devpulse.backend.exception.RateLimitExceededException;
import com.devpulse.backend.exception.ResourceNotFoundException;
import com.devpulse.backend.model.ChatSession;
import com.devpulse.backend.model.Message;
import com.devpulse.backend.model.Task;
import com.devpulse.backend.repository.ChatSessionRepository;
import com.devpulse.backend.repository.MessageRepository;
import com.devpulse.backend.repository.TaskRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class MessageService {

    private final ChatSessionRepository sessionRepository;
    private final MessageRepository messageRepository;
    private final TaskRepository taskRepository;
    private final KafkaProducerService kafkaProducerService;
    private final RedisService redisService;

    @Transactional
    public SendMessageResponse sendMessage(UUID workspaceId, UUID sessionId,
                                            UUID userId, MessageRequest req) {
        ChatSession session = sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId)
            .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));

        if (redisService.isRateLimited(userId.toString())) {
            throw new RateLimitExceededException("Rate limit exceeded: 10 messages/minute");
        }

        Message userMsg = Message.builder()
            .sessionId(sessionId)
            .role("user")
            .content(req.content())
            .build();
        Message savedMsg = messageRepository.save(userMsg);

        List<Message> recent = messageRepository.findTop10BySessionIdOrderByCreatedAtDesc(sessionId);
        List<AiTaskEvent.ConversationMessage> history = recent.stream()
            .sorted(Comparator.comparing(Message::getCreatedAt,
                Comparator.nullsLast(Comparator.naturalOrder())))
            .map(m -> new AiTaskEvent.ConversationMessage(m.getRole(), m.getContent()))
            .collect(Collectors.toList());

        Task task = Task.builder()
            .type("AI_QUERY")
            .status("PENDING")
            .build();
        Task savedTask = taskRepository.save(task);

        AiTaskEvent event = new AiTaskEvent(
            savedTask.getId(), sessionId, workspaceId, req.content(), history, Instant.now());
        kafkaProducerService.publishAiTask(event);

        session.setUpdatedAt(Instant.now());
        sessionRepository.save(session);

        return new SendMessageResponse(savedTask.getId(), savedMsg.getId());
    }

    @Transactional
    public void handleAiResponse(TaskStatusEvent event) {
        Message assistantMsg = Message.builder()
            .sessionId(event.sessionId())
            .role("assistant")
            .content(event.fullResponse())
            .sources(serializeSources(event.sources()))
            .tokensUsed(event.tokensUsed())
            .latencyMs(event.latencyMs())
            .build();
        messageRepository.save(assistantMsg);

        taskRepository.findById(event.taskId()).ifPresent(task -> {
            task.setStatus("DONE");
            taskRepository.save(task);
        });

        if (event.fullResponse() != null && event.workspaceId() != null) {
            String hash = Integer.toHexString(event.userMessageHash());
            redisService.cacheAiResponse(event.workspaceId().toString(), hash, event.fullResponse());
        }
    }

    public List<MessageResponse> getHistory(UUID workspaceId, UUID sessionId) {
        sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId)
            .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        return messageRepository.findBySessionIdOrderByCreatedAtAsc(sessionId).stream()
            .map(this::toResponse)
            .toList();
    }

    private String serializeSources(List<TaskStatusEvent.SourceInfo> sources) {
        if (sources == null || sources.isEmpty()) return null;
        try {
            return new ObjectMapper().writeValueAsString(sources);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize sources", e);
            return null;
        }
    }

    private MessageResponse toResponse(Message m) {
        return new MessageResponse(
            m.getId(), m.getRole(), m.getContent(),
            null,
            m.getTokensUsed(), m.getLatencyMs(), m.getCreatedAt());
    }
}
