package com.devpulse.backend.service;

import com.devpulse.backend.event.AiTaskEvent;
import com.devpulse.backend.event.DocumentIngestionEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class KafkaProducerServiceTest {

    @Mock KafkaTemplate<String, String> kafkaTemplate;
    @Spy  ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());
    @InjectMocks KafkaProducerService kafkaProducerService;

    @Test
    void publishDocumentIngestion_sendsToCorrectTopic() throws Exception {
        UUID docId = UUID.randomUUID();
        UUID wsId = UUID.randomUUID();
        DocumentIngestionEvent event = new DocumentIngestionEvent(
            docId, wsId, "UPLOAD", "content here", null, Instant.now());

        kafkaProducerService.publishDocumentIngestion(event);

        ArgumentCaptor<String> topicCaptor = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> keyCaptor = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> valueCaptor = ArgumentCaptor.forClass(String.class);

        verify(kafkaTemplate).send(topicCaptor.capture(), keyCaptor.capture(), valueCaptor.capture());
        assertThat(topicCaptor.getValue()).isEqualTo("document-ingestion");
        assertThat(keyCaptor.getValue()).isEqualTo(docId.toString());

        String json = valueCaptor.getValue();
        assertThat(json).contains(docId.toString());
    }

    @Test
    void publishAiTask_sendsToCorrectTopic() throws Exception {
        UUID taskId = UUID.randomUUID();
        UUID sessionId = UUID.randomUUID();
        AiTaskEvent event = new AiTaskEvent(
            taskId, sessionId, UUID.randomUUID(), "What is Java?",
            List.of(), Instant.now());

        kafkaProducerService.publishAiTask(event);

        ArgumentCaptor<String> topicCaptor = ArgumentCaptor.forClass(String.class);
        verify(kafkaTemplate).send(topicCaptor.capture(), anyString(), anyString());
        assertThat(topicCaptor.getValue()).isEqualTo("ai-tasks");
    }
}
