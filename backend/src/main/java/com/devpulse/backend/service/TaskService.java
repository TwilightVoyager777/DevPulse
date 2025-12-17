package com.devpulse.backend.service;

import com.devpulse.backend.exception.ResourceNotFoundException;
import com.devpulse.backend.model.Task;
import com.devpulse.backend.repository.TaskRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class TaskService {

    private final TaskRepository taskRepository;
    private final RedisService redisService;

    public Map<String, Object> getTaskStatus(UUID taskId) {
        // First check Redis cache (fast path)
        String cached = redisService.getTaskStatus(taskId.toString());
        if (cached != null) {
            return Map.of("taskId", taskId, "cached", true, "data", cached);
        }

        Task task = taskRepository.findById(taskId)
            .orElseThrow(() -> new ResourceNotFoundException("Task not found: " + taskId));

        return Map.of(
            "taskId", task.getId(),
            "type", task.getType(),
            "status", task.getStatus(),
            "retryCount", task.getRetryCount(),
            "createdAt", task.getCreatedAt(),
            "updatedAt", task.getUpdatedAt()
        );
    }
}
