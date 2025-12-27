package com.devpulse.backend.consumer;

import com.devpulse.backend.event.TaskStatusEvent;
import com.devpulse.backend.metrics.MetricsService;
import com.devpulse.backend.service.MessageService;
import com.devpulse.backend.service.RedisService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class TaskStatusConsumer {

    private final ObjectMapper objectMapper;
    private final RedisService redisService;
    private final MessageService messageService;
    private final MetricsService metricsService;

    @KafkaListener(topics = "task-status", groupId = "backend-consumer",
                   containerFactory = "kafkaListenerContainerFactory")
    public void consume(ConsumerRecord<String, String> record, Acknowledgment ack) {
        try {
            TaskStatusEvent event = objectMapper.readValue(record.value(), TaskStatusEvent.class);
            processEvent(event);
            ack.acknowledge();
            metricsService.recordKafkaConsumed("task-status", "success");
        } catch (Exception e) {
            log.error("Failed to process task-status event from partition {} offset {}",
                record.partition(), record.offset(), e);
            metricsService.recordKafkaConsumed("task-status", "error");
            ack.acknowledge(); // Don't retry deserialization failures; DLQ via config
        }
    }

    private void processEvent(TaskStatusEvent event) throws Exception {
        String taskId = event.taskId().toString();

        // Idempotency check: skip if task already fully processed
        String processedKey = "processed:event:" + taskId;
        if (redisService.hasKey(processedKey)) {
            log.debug("Skipping duplicate event for task {}", taskId);
            return;
        }

        // Distributed lock: prevent concurrent processing of the same task
        boolean locked = redisService.tryProcessingLock(taskId);
        if (!locked) {
            log.debug("Task {} already being processed by another instance, skipping", taskId);
            return;
        }

        try {
            // Forward chunk/done/failed event to SSE via Redis Pub/Sub
            String eventJson = objectMapper.writeValueAsString(event);
            redisService.publishSseEvent(event.sessionId().toString(), eventJson);

            // On completion: persist assistant message + mark processed
            if (event.isDone() && "done".equals(event.status())) {
                messageService.handleAiResponse(event);
                redisService.cacheTaskStatus(taskId, eventJson);
                redisService.set(processedKey, "1", 3600L);
            } else if ("failed".equals(event.status())) {
                redisService.cacheTaskStatus(taskId, eventJson);
                redisService.set(processedKey, "1", 3600L);
            }
        } finally {
            redisService.releaseProcessingLock(taskId);
        }
    }
}
