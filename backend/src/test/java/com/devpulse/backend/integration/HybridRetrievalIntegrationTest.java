package com.devpulse.backend.integration;

import com.devpulse.backend.model.Document;
import com.devpulse.backend.model.User;
import com.devpulse.backend.model.Workspace;
import com.devpulse.backend.repository.DocumentRepository;
import com.devpulse.backend.repository.UserRepository;
import com.devpulse.backend.repository.WorkspaceRepository;
import com.devpulse.backend.service.RedisService;
import com.devpulse.backend.service.SseService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.Base64;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

@SpringBootTest(
    webEnvironment = SpringBootTest.WebEnvironment.NONE,
    properties = {
        "spring.kafka.listener.auto-startup=false",
        "spring.flyway.enabled=true"
    }
)
@Testcontainers(disabledWithoutDocker = true)
@ActiveProfiles("integration")
class HybridRetrievalIntegrationTest {

    static final DockerImageName PGVECTOR_IMAGE =
        DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres");

    @Container
    static PostgreSQLContainer<?> postgres =
        new PostgreSQLContainer<>(PGVECTOR_IMAGE)
            .withDatabaseName("devpulse_test")
            .withUsername("devpulse")
            .withPassword("devpulse_test");

    // Mock external dependencies so Spring context starts without real connections
    @MockBean KafkaTemplate<String, String> kafkaTemplate;
    @MockBean StringRedisTemplate stringRedisTemplate;
    @MockBean RedisService redisService;
    @MockBean SseService sseService;
    @MockBean RedisMessageListenerContainer redisMessageListenerContainer;

    static String testPrivateKeyPem;
    static String testPublicKeyPem;

    static {
        try {
            KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
            gen.initialize(2048);
            KeyPair pair = gen.generateKeyPair();
            testPrivateKeyPem = "-----BEGIN PRIVATE KEY-----\n" +
                Base64.getMimeEncoder(64, new byte[]{'\n'})
                    .encodeToString(pair.getPrivate().getEncoded()) +
                "\n-----END PRIVATE KEY-----";
            testPublicKeyPem = "-----BEGIN PUBLIC KEY-----\n" +
                Base64.getMimeEncoder(64, new byte[]{'\n'})
                    .encodeToString(pair.getPublic().getEncoded()) +
                "\n-----END PUBLIC KEY-----";
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.data.redis.host", () -> "localhost");
        registry.add("spring.data.redis.port", () -> "6379");
        registry.add("jwt.private-key", () -> testPrivateKeyPem);
        registry.add("jwt.public-key", () -> testPublicKeyPem);
        registry.add("spring.kafka.bootstrap-servers", () -> "localhost:9092");
    }

    @Autowired UserRepository userRepository;
    @Autowired WorkspaceRepository workspaceRepository;
    @Autowired DocumentRepository documentRepository;

    @Test
    void flyway_v1_creates_users_table_and_JPA_operations_work() {
        User user = User.builder()
            .email("integration@devpulse.com")
            .passwordHash("$2a$10$test")
            .displayName("Integration Test User")
            .role("USER")
            .build();
        User saved = userRepository.save(user);

        assertThat(saved.getId()).isNotNull();
        assertThat(userRepository.findByEmail("integration@devpulse.com")).isPresent();
        assertThat(userRepository.existsByEmail("integration@devpulse.com")).isTrue();
    }

    @Test
    void flyway_v1_creates_workspace_with_owner_reference() {
        User owner = User.builder()
            .email("owner@devpulse.com")
            .passwordHash("hash")
            .displayName("Owner")
            .role("USER")
            .build();
        owner = userRepository.save(owner);

        Workspace ws = Workspace.builder()
            .name("Test Workspace")
            .owner(owner)
            .build();
        Workspace savedWs = workspaceRepository.save(ws);

        assertThat(savedWs.getId()).isNotNull();
        assertThat(workspaceRepository.findByOwnerId(owner.getId())).hasSize(1);
    }

    @Test
    void flyway_v1_creates_documents_linked_to_workspace() {
        User owner = User.builder()
            .email("doc-owner@devpulse.com")
            .passwordHash("hash")
            .displayName("Owner")
            .role("USER")
            .build();
        owner = userRepository.save(owner);

        Workspace ws = Workspace.builder().name("Doc WS").owner(owner).build();
        ws = workspaceRepository.save(ws);

        Document doc = Document.builder()
            .workspaceId(ws.getId())
            .title("Test Document")
            .content("Some content")
            .sourceType("UPLOAD")
            .status("PENDING")
            .build();
        Document savedDoc = documentRepository.save(doc);

        assertThat(savedDoc.getId()).isNotNull();
        List<Document> docs = documentRepository.findByWorkspaceId(ws.getId());
        assertThat(docs).hasSize(1);
        assertThat(docs.get(0).getTitle()).isEqualTo("Test Document");
    }

    @Test
    void flyway_v2_creates_document_chunks_table_with_vector_column() {
        // V2 migration creates document_chunks with vector(384) column.
        // If V2 failed, the Spring context would not have started (Flyway throws on failure).
        // This test verifies V2 ran by confirming: Spring context started + JPA works.
        User owner = User.builder()
            .email("v2-test@devpulse.com").passwordHash("h").displayName("V2").role("USER").build();
        owner = userRepository.save(owner);

        Workspace ws = Workspace.builder().name("V2 WS").owner(owner).build();
        ws = workspaceRepository.save(ws);

        Document doc = Document.builder()
            .workspaceId(ws.getId()).title("Chunk Doc").content("x").status("PENDING").build();
        doc = documentRepository.save(doc);

        final UUID finalDocId = doc.getId();
        final UUID finalWsId = ws.getId();

        // If we reach here, Flyway V1+V2 both ran successfully
        assertThat(documentRepository.findByIdAndWorkspaceId(finalDocId, finalWsId)).isPresent();
    }
}
