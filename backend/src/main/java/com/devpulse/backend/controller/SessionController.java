package com.devpulse.backend.controller;

import com.devpulse.backend.dto.session.*;
import com.devpulse.backend.service.MessageService;
import com.devpulse.backend.service.SessionService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/workspaces/{workspaceId}/sessions")
@RequiredArgsConstructor
public class SessionController {

    private final SessionService sessionService;
    private final MessageService messageService;

    @GetMapping
    public ResponseEntity<List<SessionResponse>> list(@PathVariable UUID workspaceId,
                                                       @AuthenticationPrincipal UserDetails user) {
        return ResponseEntity.ok(sessionService.listSessions(workspaceId,
            UUID.fromString(user.getUsername())));
    }

    @PostMapping
    public ResponseEntity<SessionResponse> create(@PathVariable UUID workspaceId,
                                                   @AuthenticationPrincipal UserDetails user,
                                                   @RequestBody SessionRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
            .body(sessionService.createSession(workspaceId, UUID.fromString(user.getUsername()), req));
    }

    @GetMapping("/{sessionId}")
    public ResponseEntity<SessionResponse> get(@PathVariable UUID workspaceId,
                                                @PathVariable UUID sessionId) {
        return ResponseEntity.ok(sessionService.getSession(workspaceId, sessionId));
    }

    @DeleteMapping("/{sessionId}")
    public ResponseEntity<Void> delete(@PathVariable UUID workspaceId,
                                        @PathVariable UUID sessionId) {
        sessionService.deleteSession(workspaceId, sessionId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/{sessionId}/messages")
    public ResponseEntity<List<MessageResponse>> getMessages(@PathVariable UUID workspaceId,
                                                              @PathVariable UUID sessionId) {
        return ResponseEntity.ok(messageService.getHistory(workspaceId, sessionId));
    }

    @PostMapping("/{sessionId}/messages")
    public ResponseEntity<SendMessageResponse> sendMessage(
            @PathVariable UUID workspaceId,
            @PathVariable UUID sessionId,
            @AuthenticationPrincipal UserDetails user,
            @RequestBody MessageRequest req) {
        return ResponseEntity.status(HttpStatus.ACCEPTED)
            .body(messageService.sendMessage(workspaceId, sessionId,
                UUID.fromString(user.getUsername()), req));
    }
    // SSE endpoint added in Task 15
}
