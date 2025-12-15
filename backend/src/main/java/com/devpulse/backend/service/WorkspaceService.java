package com.devpulse.backend.service;

import com.devpulse.backend.dto.workspace.*;
import com.devpulse.backend.exception.ResourceNotFoundException;
import com.devpulse.backend.model.User;
import com.devpulse.backend.model.Workspace;
import com.devpulse.backend.repository.UserRepository;
import com.devpulse.backend.repository.WorkspaceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class WorkspaceService {

    private final WorkspaceRepository workspaceRepository;
    private final UserRepository userRepository;

    public List<WorkspaceResponse> listByOwner(UUID ownerId) {
        return workspaceRepository.findByOwnerId(ownerId).stream()
            .map(this::toResponse)
            .toList();
    }

    public WorkspaceResponse create(UUID ownerId, WorkspaceRequest req) {
        User owner = userRepository.findById(ownerId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found: " + ownerId));
        Workspace ws = Workspace.builder()
            .name(req.name())
            .owner(owner)
            .build();
        return toResponse(workspaceRepository.save(ws));
    }

    public WorkspaceResponse getById(UUID id, UUID ownerId) {
        Workspace ws = workspaceRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("Workspace not found: " + id));
        if (!ws.getOwner().getId().equals(ownerId)) {
            throw new org.springframework.security.access.AccessDeniedException("Not your workspace");
        }
        return toResponse(ws);
    }

    public void delete(UUID id, UUID ownerId) {
        Workspace ws = workspaceRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("Workspace not found: " + id));
        if (!ws.getOwner().getId().equals(ownerId)) {
            throw new org.springframework.security.access.AccessDeniedException("Not your workspace");
        }
        workspaceRepository.delete(ws);
    }

    private WorkspaceResponse toResponse(Workspace ws) {
        return new WorkspaceResponse(ws.getId(), ws.getName(), ws.getOwner().getId(), ws.getCreatedAt());
    }
}
