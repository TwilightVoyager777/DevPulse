package com.devpulse.backend.service;

import com.devpulse.backend.dto.document.DocumentResponse;
import com.devpulse.backend.event.DocumentIngestionEvent;
import com.devpulse.backend.exception.ResourceNotFoundException;
import com.devpulse.backend.model.Document;
import com.devpulse.backend.model.Task;
import com.devpulse.backend.repository.DocumentRepository;
import com.devpulse.backend.repository.TaskRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class DocumentServiceTest {

    @Mock DocumentRepository documentRepository;
    @Mock TaskRepository taskRepository;
    @Mock KafkaProducerService kafkaProducerService;
    @InjectMocks DocumentService documentService;

    @Test
    void uploadDocument_savesDocumentAndPublishesToKafka() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID docId = UUID.randomUUID();
        MockMultipartFile file = new MockMultipartFile(
            "file", "test.md", "text/plain", "# Hello\nMarkdown content".getBytes());

        when(documentRepository.save(any())).thenAnswer(inv -> {
            Document d = inv.getArgument(0);
            d.setId(docId);
            return d;
        });
        when(taskRepository.save(any())).thenAnswer(inv -> {
            Task t = inv.getArgument(0);
            t.setId(UUID.randomUUID());
            return t;
        });

        DocumentResponse resp = documentService.uploadDocument(workspaceId, file);

        assertThat(resp.id()).isEqualTo(docId);
        assertThat(resp.title()).isEqualTo("test.md");
        assertThat(resp.status()).isEqualTo("PENDING");

        ArgumentCaptor<DocumentIngestionEvent> eventCaptor =
            ArgumentCaptor.forClass(DocumentIngestionEvent.class);
        verify(kafkaProducerService).publishDocumentIngestion(eventCaptor.capture());
        assertThat(eventCaptor.getValue().documentId()).isEqualTo(docId);
        assertThat(eventCaptor.getValue().workspaceId()).isEqualTo(workspaceId);
        assertThat(eventCaptor.getValue().sourceType()).isEqualTo("UPLOAD");
    }

    @Test
    void listDocuments_returnsAllForWorkspace() {
        UUID workspaceId = UUID.randomUUID();
        Document d1 = Document.builder().id(UUID.randomUUID()).workspaceId(workspaceId)
            .title("Doc1").status("INDEXED").build();
        Document d2 = Document.builder().id(UUID.randomUUID()).workspaceId(workspaceId)
            .title("Doc2").status("PENDING").build();

        when(documentRepository.findByWorkspaceId(workspaceId)).thenReturn(List.of(d1, d2));

        List<DocumentResponse> list = documentService.listDocuments(workspaceId);

        assertThat(list).hasSize(2);
        assertThat(list).extracting(DocumentResponse::title).containsExactlyInAnyOrder("Doc1", "Doc2");
    }

    @Test
    void deleteDocument_notFound_throwsException() {
        UUID workspaceId = UUID.randomUUID();
        UUID docId = UUID.randomUUID();
        when(documentRepository.findByIdAndWorkspaceId(docId, workspaceId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> documentService.deleteDocument(workspaceId, docId))
            .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void importSoDocument_publishesToKafka() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID docId = UUID.randomUUID();
        when(documentRepository.save(any())).thenAnswer(inv -> {
            Document d = inv.getArgument(0);
            d.setId(docId);
            return d;
        });
        when(taskRepository.save(any())).thenAnswer(inv -> {
            Task t = inv.getArgument(0);
            t.setId(UUID.randomUUID());
            return t;
        });

        documentService.importSoDocument(workspaceId,
            new com.devpulse.backend.dto.document.ImportSoRequest(
                "How does Java GC work?", "GC content here", null));

        ArgumentCaptor<DocumentIngestionEvent> captor =
            ArgumentCaptor.forClass(DocumentIngestionEvent.class);
        verify(kafkaProducerService).publishDocumentIngestion(captor.capture());
        assertThat(captor.getValue().sourceType()).isEqualTo("SO_IMPORT");
    }
}
