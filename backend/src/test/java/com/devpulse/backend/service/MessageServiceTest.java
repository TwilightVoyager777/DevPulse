package com.devpulse.backend.service;

import com.devpulse.backend.dto.session.*;
import com.devpulse.backend.event.AiTaskEvent;
import com.devpulse.backend.exception.RateLimitExceededException;
import com.devpulse.backend.model.ChatSession;
import com.devpulse.backend.model.Message;
import com.devpulse.backend.model.Task;
import com.devpulse.backend.repository.ChatSessionRepository;
import com.devpulse.backend.repository.MessageRepository;
import com.devpulse.backend.repository.TaskRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class MessageServiceTest {

    @Mock ChatSessionRepository sessionRepository;
    @Mock MessageRepository messageRepository;
    @Mock TaskRepository taskRepository;
    @Mock KafkaProducerService kafkaProducerService;
    @Mock RedisService redisService;
    @InjectMocks MessageService messageService;

    private ChatSession mockSession(UUID sessionId, UUID workspaceId, UUID userId) {
        return ChatSession.builder()
            .id(sessionId).workspaceId(workspaceId).userId(userId).title("Chat").build();
    }

    @Test
    void sendMessage_savesUserMessageAndPublishesAiTask() {
        UUID sessionId  = UUID.randomUUID();
        UUID workspaceId = UUID.randomUUID();
        UUID userId     = UUID.randomUUID();
        UUID taskId     = UUID.randomUUID();

        when(sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId))
            .thenReturn(Optional.of(mockSession(sessionId, workspaceId, userId)));
        when(redisService.isRateLimited(userId.toString())).thenReturn(false);
        when(messageRepository.save(any())).thenAnswer(inv -> {
            Message m = inv.getArgument(0);
            m.setId(UUID.randomUUID());
            return m;
        });
        when(messageRepository.findTop10BySessionIdOrderByCreatedAtDesc(sessionId))
            .thenReturn(List.of());
        when(taskRepository.save(any())).thenAnswer(inv -> {
            Task t = inv.getArgument(0);
            t.setId(taskId);
            return t;
        });
        when(sessionRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        SendMessageResponse resp = messageService.sendMessage(
            workspaceId, sessionId, userId, new MessageRequest("What is Redis?"));

        assertThat(resp.taskId()).isEqualTo(taskId);

        ArgumentCaptor<Message> msgCaptor = ArgumentCaptor.forClass(Message.class);
        verify(messageRepository).save(msgCaptor.capture());
        assertThat(msgCaptor.getValue().getRole()).isEqualTo("user");
        assertThat(msgCaptor.getValue().getContent()).isEqualTo("What is Redis?");

        ArgumentCaptor<AiTaskEvent> eventCaptor = ArgumentCaptor.forClass(AiTaskEvent.class);
        verify(kafkaProducerService).publishAiTask(eventCaptor.capture());
        assertThat(eventCaptor.getValue().taskId()).isEqualTo(taskId);
        assertThat(eventCaptor.getValue().userMessage()).isEqualTo("What is Redis?");
    }

    @Test
    void sendMessage_sessionNotFound_throwsResourceNotFound() {
        UUID sessionId  = UUID.randomUUID();
        UUID workspaceId = UUID.randomUUID();
        UUID userId     = UUID.randomUUID();

        when(sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId))
            .thenReturn(Optional.empty());

        assertThatThrownBy(() -> messageService.sendMessage(
            workspaceId, sessionId, userId, new MessageRequest("Q")))
            .isInstanceOf(com.devpulse.backend.exception.ResourceNotFoundException.class);
    }

    @Test
    void sendMessage_rateLimited_throwsRateLimitException() {
        UUID sessionId  = UUID.randomUUID();
        UUID workspaceId = UUID.randomUUID();
        UUID userId     = UUID.randomUUID();

        when(sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId))
            .thenReturn(Optional.of(mockSession(sessionId, workspaceId, userId)));
        when(redisService.isRateLimited(userId.toString())).thenReturn(true);

        assertThatThrownBy(() -> messageService.sendMessage(
            workspaceId, sessionId, userId, new MessageRequest("Q")))
            .isInstanceOf(RateLimitExceededException.class);
    }

    @Test
    void getHistory_returnsMessagesOrderedByCreatedAt() {
        UUID sessionId  = UUID.randomUUID();
        UUID workspaceId = UUID.randomUUID();
        UUID userId     = UUID.randomUUID();

        when(sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId))
            .thenReturn(Optional.of(mockSession(sessionId, workspaceId, userId)));

        Message m1 = Message.builder().id(UUID.randomUUID()).sessionId(sessionId)
            .role("user").content("Q1").build();
        Message m2 = Message.builder().id(UUID.randomUUID()).sessionId(sessionId)
            .role("assistant").content("A1").build();
        when(messageRepository.findBySessionIdOrderByCreatedAtAsc(sessionId))
            .thenReturn(List.of(m1, m2));

        List<MessageResponse> history = messageService.getHistory(workspaceId, sessionId);

        assertThat(history).hasSize(2);
        assertThat(history.get(0).role()).isEqualTo("user");
        assertThat(history.get(1).role()).isEqualTo("assistant");
    }

    @Test
    void sendMessage_conversationHistory_includesLast10Messages() {
        UUID sessionId  = UUID.randomUUID();
        UUID workspaceId = UUID.randomUUID();
        UUID userId     = UUID.randomUUID();

        when(sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId))
            .thenReturn(Optional.of(mockSession(sessionId, workspaceId, userId)));
        when(redisService.isRateLimited(any())).thenReturn(false);
        when(messageRepository.save(any())).thenAnswer(inv -> {
            Message m = inv.getArgument(0);
            m.setId(UUID.randomUUID());
            return m;
        });

        List<Message> history = java.util.stream.IntStream.range(0, 10)
            .mapToObj(i -> Message.builder().id(UUID.randomUUID()).sessionId(sessionId)
                .role(i % 2 == 0 ? "user" : "assistant").content("msg " + i).build())
            .toList();
        when(messageRepository.findTop10BySessionIdOrderByCreatedAtDesc(sessionId))
            .thenReturn(history);
        when(taskRepository.save(any())).thenAnswer(inv -> {
            Task t = inv.getArgument(0);
            t.setId(UUID.randomUUID());
            return t;
        });
        when(sessionRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        messageService.sendMessage(workspaceId, sessionId, userId, new MessageRequest("New Q"));

        ArgumentCaptor<AiTaskEvent> captor = ArgumentCaptor.forClass(AiTaskEvent.class);
        verify(kafkaProducerService).publishAiTask(captor.capture());
        assertThat(captor.getValue().conversationHistory()).hasSize(10);
    }
}
