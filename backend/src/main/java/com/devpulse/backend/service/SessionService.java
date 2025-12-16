package com.devpulse.backend.service;

import com.devpulse.backend.dto.session.SessionRequest;
import com.devpulse.backend.dto.session.SessionResponse;
import com.devpulse.backend.exception.ResourceNotFoundException;
import com.devpulse.backend.model.ChatSession;
import com.devpulse.backend.repository.ChatSessionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class SessionService {

    private final ChatSessionRepository sessionRepository;

    public List<SessionResponse> listSessions(UUID workspaceId, UUID userId) {
        return sessionRepository.findByWorkspaceIdAndUserIdOrderByUpdatedAtDesc(workspaceId, userId)
            .stream().map(this::toResponse).toList();
    }

    public SessionResponse createSession(UUID workspaceId, UUID userId, SessionRequest req) {
        String title = (req.title() != null && !req.title().isBlank()) ? req.title() : "New Chat";
        ChatSession session = ChatSession.builder()
            .workspaceId(workspaceId)
            .userId(userId)
            .title(title)
            .build();
        return toResponse(sessionRepository.save(session));
    }

    public SessionResponse getSession(UUID workspaceId, UUID sessionId) {
        ChatSession session = sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId)
            .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        return toResponse(session);
    }

    public void deleteSession(UUID workspaceId, UUID sessionId) {
        ChatSession session = sessionRepository.findByIdAndWorkspaceId(sessionId, workspaceId)
            .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        sessionRepository.delete(session);
    }

    private SessionResponse toResponse(ChatSession s) {
        return new SessionResponse(s.getId(), s.getWorkspaceId(), s.getTitle(),
                                    s.getCreatedAt(), s.getUpdatedAt());
    }
}
