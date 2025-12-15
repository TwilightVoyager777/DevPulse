package com.devpulse.backend.controller;

import com.devpulse.backend.dto.document.DocumentResponse;
import com.devpulse.backend.dto.document.ImportSoRequest;
import com.devpulse.backend.service.DocumentService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/workspaces/{workspaceId}/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    @GetMapping
    public ResponseEntity<List<DocumentResponse>> list(@PathVariable UUID workspaceId) {
        return ResponseEntity.ok(documentService.listDocuments(workspaceId));
    }

    @PostMapping("/upload")
    public ResponseEntity<DocumentResponse> upload(@PathVariable UUID workspaceId,
                                                    @RequestParam("file") MultipartFile file)
            throws IOException {
        return ResponseEntity.status(HttpStatus.CREATED)
            .body(documentService.uploadDocument(workspaceId, file));
    }

    @PostMapping("/import-so")
    public ResponseEntity<DocumentResponse> importSo(@PathVariable UUID workspaceId,
                                                      @RequestBody ImportSoRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
            .body(documentService.importSoDocument(workspaceId, req));
    }

    @GetMapping("/{docId}")
    public ResponseEntity<DocumentResponse> get(@PathVariable UUID workspaceId,
                                                 @PathVariable UUID docId) {
        return ResponseEntity.ok(documentService.getDocument(workspaceId, docId));
    }

    @DeleteMapping("/{docId}")
    public ResponseEntity<Void> delete(@PathVariable UUID workspaceId,
                                        @PathVariable UUID docId) {
        documentService.deleteDocument(workspaceId, docId);
        return ResponseEntity.noContent().build();
    }
}
