package com.devpulse.backend.service;

import com.devpulse.backend.event.AiTaskEvent;
import com.devpulse.backend.event.DocumentIngestionEvent;
import com.devpulse.backend.metrics.MetricsService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
@Slf4j
public class KafkaProducerService {

    private static final String TOPIC_INGESTION = "document-ingestion";
    private static final String TOPIC_AI_TASKS  = "ai-tasks";

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;
    private final MetricsService metricsService;

    public void publishDocumentIngestion(DocumentIngestionEvent event) {
        send(TOPIC_INGESTION, event.documentId().toString(), event);
    }

    public void publishAiTask(AiTaskEvent event) {
        send(TOPIC_AI_TASKS, event.taskId().toString(), event);
    }

    private void send(String topic, String key, Object payload) {
        try {
            String json = objectMapper.writeValueAsString(payload);
            kafkaTemplate.send(topic, key, json);
            metricsService.recordKafkaProduced(topic);
            log.debug("Sent to {}: key={}", topic, key);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize event for topic {}", topic, e);
            throw new RuntimeException("Kafka serialization failed", e);
        }
    }
}
