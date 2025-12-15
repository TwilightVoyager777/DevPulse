package com.devpulse.backend.controller;

import com.devpulse.backend.dto.workspace.*;
import com.devpulse.backend.service.WorkspaceService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/workspaces")
@RequiredArgsConstructor
public class WorkspaceController {

    private final WorkspaceService workspaceService;

    @GetMapping
    public ResponseEntity<List<WorkspaceResponse>> list(@AuthenticationPrincipal UserDetails user) {
        return ResponseEntity.ok(workspaceService.listByOwner(UUID.fromString(user.getUsername())));
    }

    @PostMapping
    public ResponseEntity<WorkspaceResponse> create(@AuthenticationPrincipal UserDetails user,
                                                     @RequestBody WorkspaceRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
            .body(workspaceService.create(UUID.fromString(user.getUsername()), req));
    }

    @GetMapping("/{id}")
    public ResponseEntity<WorkspaceResponse> get(@PathVariable UUID id,
                                                  @AuthenticationPrincipal UserDetails user) {
        return ResponseEntity.ok(workspaceService.getById(id, UUID.fromString(user.getUsername())));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable UUID id,
                                        @AuthenticationPrincipal UserDetails user) {
        workspaceService.delete(id, UUID.fromString(user.getUsername()));
        return ResponseEntity.noContent().build();
    }
}
