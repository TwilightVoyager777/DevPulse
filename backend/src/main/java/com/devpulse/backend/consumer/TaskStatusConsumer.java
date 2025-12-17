package com.devpulse.backend.consumer;

import com.devpulse.backend.event.TaskStatusEvent;
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

    @KafkaListener(topics = "task-status", groupId = "backend-consumer",
                   containerFactory = "kafkaListenerContainerFactory")
    public void consume(ConsumerRecord<String, String> record, Acknowledgment ack) {
        try {
            TaskStatusEvent event = objectMapper.readValue(record.value(), TaskStatusEvent.class);
            processEvent(event);
            ack.acknowledge();
        } catch (Exception e) {
            log.error("Failed to process task-status event from partition {} offset {}",
                record.partition(), record.offset(), e);
            ack.acknowledge(); // Don't retry deserialization failures; DLQ via config
        }
    }

    private void processEvent(TaskStatusEvent event) throws Exception {
        // Idempotency check: skip if task already processed
        String processedKey = "processed:event:" + event.taskId();
        if (redisService.hasKey(processedKey)) {
            log.debug("Skipping duplicate event for task {}", event.taskId());
            return;
        }

        // Forward chunk/done/failed event to SSE via Redis Pub/Sub
        String eventJson = objectMapper.writeValueAsString(event);
        redisService.publishSseEvent(event.sessionId().toString(), eventJson);

        // On completion: persist assistant message + update task status
        if (event.isDone() && "done".equals(event.status())) {
            messageService.handleAiResponse(event);
            redisService.cacheTaskStatus(event.taskId().toString(), eventJson);
            redisService.set(processedKey, "1", 3600L);
        } else if ("failed".equals(event.status())) {
            redisService.cacheTaskStatus(event.taskId().toString(), eventJson);
            redisService.set(processedKey, "1", 3600L);
        }
    }
}
