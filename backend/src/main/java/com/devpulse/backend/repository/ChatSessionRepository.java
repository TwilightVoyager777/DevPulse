package com.devpulse.backend.repository;

import com.devpulse.backend.model.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ChatSessionRepository extends JpaRepository<ChatSession, UUID> {
    List<ChatSession> findByWorkspaceIdAndUserIdOrderByUpdatedAtDesc(UUID workspaceId, UUID userId);
    Optional<ChatSession> findByIdAndWorkspaceId(UUID id, UUID workspaceId);
}
