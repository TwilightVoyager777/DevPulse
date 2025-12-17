package com.devpulse.backend.controller;

import com.devpulse.backend.dto.session.*;
import com.devpulse.backend.service.MessageService;
import com.devpulse.backend.service.SessionService;
import com.devpulse.backend.service.SseService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/workspaces/{workspaceId}/sessions")
@RequiredArgsConstructor
public class SessionController {

    private final SessionService sessionService;
    private final MessageService messageService;
    private final SseService sseService;

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

    @GetMapping(value = "/{sessionId}/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@PathVariable UUID workspaceId,
                              @PathVariable UUID sessionId,
                              @RequestParam(required = false) UUID taskId) {
        sessionService.getSession(workspaceId, sessionId); // verify exists
        return sseService.createEmitter(sessionId.toString());
    }
}
