package com.devpulse.backend.service;

import com.devpulse.backend.dto.document.DocumentResponse;
import com.devpulse.backend.dto.document.ImportSoRequest;
import com.devpulse.backend.event.DocumentIngestionEvent;
import com.devpulse.backend.exception.ResourceNotFoundException;
import com.devpulse.backend.model.Document;
import com.devpulse.backend.model.Task;
import com.devpulse.backend.repository.DocumentRepository;
import com.devpulse.backend.repository.TaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class DocumentService {

    private final DocumentRepository documentRepository;
    private final TaskRepository taskRepository;
    private final KafkaProducerService kafkaProducerService;

    public DocumentResponse uploadDocument(UUID workspaceId, MultipartFile file) throws IOException {
        String content = new String(file.getBytes());
        Document doc = Document.builder()
            .workspaceId(workspaceId)
            .title(file.getOriginalFilename())
            .content(content)
            .sourceType("UPLOAD")
            .status("PENDING")
            .build();
        Document saved = documentRepository.save(doc);

        publishIngestion(saved, "UPLOAD", content, null);
        return toResponse(saved);
    }

    public DocumentResponse importSoDocument(UUID workspaceId, ImportSoRequest req) {
        Document doc = Document.builder()
            .workspaceId(workspaceId)
            .title(req.title())
            .content(req.content())
            .sourceType("SO_IMPORT")
            .status("PENDING")
            .build();
        Document saved = documentRepository.save(doc);

        Map<String, Object> meta = req.metadata() != null ? new HashMap<>(req.metadata()) : new HashMap<>();
        publishIngestion(saved, "SO_IMPORT", req.content(), meta);
        return toResponse(saved);
    }

    public List<DocumentResponse> listDocuments(UUID workspaceId) {
        return documentRepository.findByWorkspaceId(workspaceId).stream()
            .map(this::toResponse)
            .toList();
    }

    public DocumentResponse getDocument(UUID workspaceId, UUID docId) {
        Document doc = documentRepository.findByIdAndWorkspaceId(docId, workspaceId)
            .orElseThrow(() -> new ResourceNotFoundException("Document not found: " + docId));
        return toResponse(doc);
    }

    public void deleteDocument(UUID workspaceId, UUID docId) {
        Document doc = documentRepository.findByIdAndWorkspaceId(docId, workspaceId)
            .orElseThrow(() -> new ResourceNotFoundException("Document not found: " + docId));
        documentRepository.delete(doc);
    }

    private void publishIngestion(Document doc, String sourceType, String content,
                                   Map<String, Object> metadata) {
        Task task = Task.builder()
            .type("DOCUMENT_INGESTION")
            .payload("{\"documentId\":\"" + doc.getId() + "\"}")
            .status("PENDING")
            .build();
        taskRepository.save(task);

        DocumentIngestionEvent event = new DocumentIngestionEvent(
            doc.getId(), doc.getWorkspaceId(), sourceType, content, metadata, Instant.now());
        kafkaProducerService.publishDocumentIngestion(event);
    }

    private DocumentResponse toResponse(Document doc) {
        return new DocumentResponse(
            doc.getId(), doc.getWorkspaceId(), doc.getTitle(),
            doc.getSourceType(), doc.getStatus(), doc.getChunkCount(),
            doc.getErrorMessage(), doc.getCreatedAt(), doc.getIndexedAt());
    }
}
