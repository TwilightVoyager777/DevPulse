package com.devpulse.backend.repository;

import com.devpulse.backend.model.Document;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface DocumentRepository extends JpaRepository<Document, UUID> {
    List<Document> findByWorkspaceId(UUID workspaceId);
    Optional<Document> findByIdAndWorkspaceId(UUID id, UUID workspaceId);
}
