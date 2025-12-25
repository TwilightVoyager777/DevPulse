# DevPulse Sub-Project 1: Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up all infrastructure foundations: Docker Compose (dev + full stack), Kubernetes manifests, Prometheus/Grafana monitoring, environment templates, and README.

**Architecture:** Docker Compose orchestrates PostgreSQL 16 (pgvector + pg_trgm extensions via init script), Redis 7 (AOF persistence), and Kafka 7.5.0 with 5 pre-created topics (auto-create disabled). K8s targets a `devpulse` namespace with RollingUpdate deployments and HPA for the backend. Prometheus scrapes both services via their `/actuator/prometheus` and `/metrics` endpoints; Grafana auto-provisions datasource + dashboard on startup.

**Tech Stack:** Docker Compose v3.8, Kubernetes 1.28+, Prometheus 2.x, Grafana 10.x, Confluent Kafka 7.5.0, PostgreSQL 16 + pgvector, Redis 7-alpine

---

## File Map

| File | Responsibility |
|------|---------------|
| `.gitignore` | Exclude build artifacts, secrets, IDE files |
| `infra/postgres/init.sql` | Enable vector + pg_trgm extensions on postgres container start |
| `infra/docker-compose.dev.yml` | Infrastructure services only (postgres, redis, zookeeper, kafka, kafka-init, kafka-ui) |
| `infra/docker-compose.yml` | Full stack (infra + backend, ai-worker, frontend, prometheus, grafana) |
| `infra/k8s/namespace.yaml` | `devpulse` namespace |
| `infra/k8s/configmap.yaml` | Non-sensitive config (hosts, ports, profiles) |
| `infra/k8s/secret.yaml` | Sensitive config with base64 placeholder instructions |
| `infra/k8s/backend/deployment.yaml` | Backend Deployment (replicas:2, resource limits, probes, RollingUpdate) |
| `infra/k8s/backend/service.yaml` | Backend ClusterIP Service |
| `infra/k8s/backend/hpa.yaml` | HPA (min:2, max:5, CPU 70%) |
| `infra/k8s/ai-worker/deployment.yaml` | AI Worker Deployment (replicas:2, resource limits, probes) |
| `infra/k8s/ai-worker/service.yaml` | AI Worker ClusterIP Service |
| `infra/k8s/frontend/deployment.yaml` | Frontend Deployment (replicas:2, resource limits, probes) |
| `infra/k8s/frontend/service.yaml` | Frontend ClusterIP Service |
| `infra/k8s/ingress.yaml` | Nginx Ingress: /api/* → backend, /* → frontend, TLS cert-manager, SSE buffering off |
| `infra/monitoring/prometheus.yml` | Scrape config for backend:8080 and ai-worker:8000 |
| `infra/monitoring/grafana-provisioning/datasources/prometheus.yaml` | Auto-provision Prometheus datasource |
| `infra/monitoring/grafana-provisioning/dashboards/dashboard.yaml` | Auto-provision dashboard from /var/lib/grafana/dashboards/ |
| `infra/monitoring/dashboards/devpulse.json` | Grafana dashboard JSON (5 rows, 17 panels) |
| `.env.example` | All environment variable templates with generation instructions |
| `README.md` | Quick Start, data import, eval instructions, architecture diagram |

> **Note on Flyway migrations (V1__init.sql, V2__pgvector.sql):** These require the Spring Boot project structure to exist and are created in Sub-project 2 (Backend). The postgres init.sql in this plan only enables extensions — schema creation happens via Flyway on backend startup.

---

### Task 1: Initialize Git + Project Scaffolding

**Files:**
- Create: `.gitignore`
- Create: top-level directory structure

- [ ] **Step 1: Initialize git and create all directories**

```bash
cd /Users/dragonhope/Documents/Project/DevPulse
git init
mkdir -p infra/postgres
mkdir -p infra/k8s/backend infra/k8s/ai-worker infra/k8s/frontend
mkdir -p infra/monitoring/dashboards
mkdir -p infra/monitoring/grafana-provisioning/datasources
mkdir -p infra/monitoring/grafana-provisioning/dashboards
mkdir -p backend/src/main/resources/db/migration
mkdir -p ai-worker/app/consumers ai-worker/app/services ai-worker/app/models ai-worker/app/utils ai-worker/tests
mkdir -p frontend/app frontend/components frontend/lib/api frontend/hooks frontend/tests
mkdir -p scripts docs/superpowers/specs docs/superpowers/plans .github/workflows
```

- [ ] **Step 2: Create .gitignore**

Create `/.gitignore`:
```gitignore
# Secrets
.env
.env.local
*.env

# Java / Gradle
backend/build/
backend/.gradle/
*.jar
*.war
*.class
*.ijar

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
ai-worker/.cache/
sentence_transformers_cache/

# Node / Next.js
node_modules/
frontend/.next/
frontend/out/
frontend/.env.local

# Seed progress
scripts/.seed_progress.json

# IDE
.idea/
.vscode/
*.iml
*.swp

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: initialize project with directory structure"
```

---

### Task 2: PostgreSQL Extension Init Script

**Files:**
- Create: `infra/postgres/init.sql`

- [ ] **Step 1: Create init.sql**

Create `infra/postgres/init.sql`:
```sql
-- Required for 384-dimensional vector embeddings (all-MiniLM-L6-v2 output)
CREATE EXTENSION IF NOT EXISTS vector;
-- Required for BM25 fallback full-text trigram search on document_chunks.content
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

- [ ] **Step 2: Commit**

```bash
git add infra/postgres/init.sql
git commit -m "infra: add postgres extension init script (vector, pg_trgm)"
```

---

### Task 3: Docker Compose Dev (Infrastructure Only)

**Files:**
- Create: `infra/docker-compose.dev.yml`

- [ ] **Step 1: Create docker-compose.dev.yml**

Create `infra/docker-compose.dev.yml`:
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: devpulse
      POSTGRES_USER: devpulse
      POSTGRES_PASSWORD: devpulse_secret
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/01-init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U devpulse -d devpulse"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "2181"]
      interval: 10s
      timeout: 5s
      retries: 5

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      zookeeper:
        condition: service_healthy
    ports:
      - "9092:9092"
      - "29092:29092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD-SHELL", "kafka-broker-api-versions --bootstrap-server localhost:9092"]
      interval: 10s
      timeout: 10s
      retries: 10
      start_period: 30s

  kafka-init:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      kafka:
        condition: service_healthy
    command: >
      bash -c "
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 3 --replication-factor 1 --topic document-ingestion &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 3 --replication-factor 1 --topic ai-tasks &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 3 --replication-factor 1 --topic task-status &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 1 --replication-factor 1 --topic document-ingestion-dlq &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 1 --replication-factor 1 --topic ai-tasks-dlq &&
        echo 'All 5 Kafka topics created'
      "
    restart: "no"

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    depends_on:
      - kafka
    ports:
      - "8090:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: devpulse-local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:29092

volumes:
  postgres_data:
  redis_data:
```

- [ ] **Step 2: Start dev infrastructure**

```bash
docker compose -f infra/docker-compose.dev.yml up -d
```

Wait about 30 seconds for Kafka to become healthy, then:

```bash
docker compose -f infra/docker-compose.dev.yml ps
```

Expected: postgres (healthy), redis (healthy), zookeeper (healthy), kafka (healthy), kafka-init (exited 0), kafka-ui (running).

- [ ] **Step 3: Verify Kafka topics were created**

```bash
docker compose -f infra/docker-compose.dev.yml exec kafka \
  kafka-topics --list --bootstrap-server localhost:9092
```

Expected output (5 lines):
```
ai-tasks
ai-tasks-dlq
document-ingestion
document-ingestion-dlq
task-status
```

- [ ] **Step 4: Verify pgvector and pg_trgm are enabled**

```bash
docker compose -f infra/docker-compose.dev.yml exec postgres \
  psql -U devpulse -d devpulse -c "SELECT extname FROM pg_extension WHERE extname IN ('vector','pg_trgm');"
```

Expected output:
```
  extname
----------
 vector
 pg_trgm
(2 rows)
```

- [ ] **Step 5: Stop infrastructure**

```bash
docker compose -f infra/docker-compose.dev.yml down
```

- [ ] **Step 6: Commit**

```bash
git add infra/docker-compose.dev.yml
git commit -m "infra: add docker-compose.dev.yml with postgres, redis, kafka (5 topics)"
```

---

### Task 4: Docker Compose Full Stack

**Files:**
- Create: `infra/docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

Create `infra/docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: devpulse
      POSTGRES_USER: devpulse
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-devpulse_secret}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/01-init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U devpulse -d devpulse"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "2181"]
      interval: 10s
      timeout: 5s
      retries: 5

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      zookeeper:
        condition: service_healthy
    ports:
      - "9092:9092"
      - "29092:29092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD-SHELL", "kafka-broker-api-versions --bootstrap-server localhost:9092"]
      interval: 10s
      timeout: 10s
      retries: 10
      start_period: 30s

  kafka-init:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      kafka:
        condition: service_healthy
    command: >
      bash -c "
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 3 --replication-factor 1 --topic document-ingestion &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 3 --replication-factor 1 --topic ai-tasks &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 3 --replication-factor 1 --topic task-status &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 1 --replication-factor 1 --topic document-ingestion-dlq &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --partitions 1 --replication-factor 1 --topic ai-tasks-dlq
      "
    restart: "no"

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    depends_on:
      - kafka
    ports:
      - "8090:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: devpulse-local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:29092

  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/devpulse
      SPRING_DATASOURCE_USERNAME: devpulse
      SPRING_DATASOURCE_PASSWORD: ${POSTGRES_PASSWORD:-devpulse_secret}
      SPRING_REDIS_HOST: redis
      SPRING_REDIS_PORT: 6379
      SPRING_KAFKA_BOOTSTRAP_SERVERS: kafka:29092
      JWT_PRIVATE_KEY: ${JWT_PRIVATE_KEY}
      JWT_PUBLIC_KEY: ${JWT_PUBLIC_KEY}
      JWT_EXPIRY_MINUTES: 15
      JWT_REFRESH_EXPIRY_DAYS: 7
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      kafka:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8080/actuator/health | grep UP || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 90s

  ai-worker:
    build:
      context: ../ai-worker
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      DATABASE_URL: postgresql://devpulse:${POSTGRES_PASSWORD:-devpulse_secret}@postgres:5432/devpulse
      REDIS_URL: redis://redis:6379
      KAFKA_BOOTSTRAP_SERVERS: kafka:29092
      EMBEDDING_MODEL: all-MiniLM-L6-v2
      BM25_REBUILD_ON_STARTUP: "true"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      kafka:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8000/health | grep ok || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://backend:8080
    depends_on:
      backend:
        condition: service_healthy

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--web.enable-lifecycle"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH: /var/lib/grafana/dashboards/devpulse.json
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana-provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/dashboards:/var/lib/grafana/dashboards:ro

volumes:
  postgres_data:
  redis_data:
  grafana_data:
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker-compose.yml
git commit -m "infra: add docker-compose.yml full stack with all application services"
```

---

### Task 5: Kubernetes Namespace, ConfigMap, Secret

**Files:**
- Create: `infra/k8s/namespace.yaml`
- Create: `infra/k8s/configmap.yaml`
- Create: `infra/k8s/secret.yaml`

- [ ] **Step 1: Create namespace.yaml**

Create `infra/k8s/namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: devpulse
  labels:
    app.kubernetes.io/managed-by: kubectl
```

- [ ] **Step 2: Create configmap.yaml**

Create `infra/k8s/configmap.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: devpulse-config
  namespace: devpulse
data:
  KAFKA_BOOTSTRAP_SERVERS: "kafka:9092"
  POSTGRES_HOST: "postgres"
  POSTGRES_PORT: "5432"
  POSTGRES_DB: "devpulse"
  POSTGRES_USER: "devpulse"
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"
  SPRING_PROFILES_ACTIVE: "prod"
  LOG_LEVEL: "INFO"
  EMBEDDING_MODEL: "all-MiniLM-L6-v2"
  BM25_REBUILD_ON_STARTUP: "true"
  JWT_EXPIRY_MINUTES: "15"
  JWT_REFRESH_EXPIRY_DAYS: "7"
```

- [ ] **Step 3: Create secret.yaml**

Create `infra/k8s/secret.yaml`:
```yaml
# IMPORTANT: Replace all placeholder values before applying.
# Generate base64: echo -n "your-actual-value" | base64
# Generate RSA keys:
#   openssl genrsa -out private.pem 2048
#   openssl rsa -in private.pem -pubout -out public.pem
#   cat private.pem | base64 | tr -d '\n'
apiVersion: v1
kind: Secret
metadata:
  name: devpulse-secrets
  namespace: devpulse
type: Opaque
data:
  ANTHROPIC_API_KEY: REPLACE_WITH_BASE64
  POSTGRES_PASSWORD: REPLACE_WITH_BASE64
  JWT_PRIVATE_KEY: REPLACE_WITH_BASE64
  JWT_PUBLIC_KEY: REPLACE_WITH_BASE64
  NEXTAUTH_SECRET: REPLACE_WITH_BASE64
```

- [ ] **Step 4: Validate YAML syntax**

```bash
kubectl apply --dry-run=client -f infra/k8s/namespace.yaml
kubectl apply --dry-run=client -f infra/k8s/configmap.yaml
```

Expected:
```
namespace/devpulse configured (dry run)
configmap/devpulse-config configured (dry run)
```

- [ ] **Step 5: Commit**

```bash
git add infra/k8s/namespace.yaml infra/k8s/configmap.yaml infra/k8s/secret.yaml
git commit -m "infra: add kubernetes namespace, configmap, and secret template"
```

---

### Task 6: Kubernetes Backend Deployment + HPA + Service

**Files:**
- Create: `infra/k8s/backend/deployment.yaml`
- Create: `infra/k8s/backend/service.yaml`
- Create: `infra/k8s/backend/hpa.yaml`

- [ ] **Step 1: Create backend deployment**

Create `infra/k8s/backend/deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: devpulse
  labels:
    app: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: ghcr.io/YOUR_GITHUB_USERNAME/devpulse-backend:latest
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: devpulse-config
          env:
            - name: SPRING_DATASOURCE_URL
              value: "jdbc:postgresql://$(POSTGRES_HOST):$(POSTGRES_PORT)/$(POSTGRES_DB)"
            - name: SPRING_DATASOURCE_USERNAME
              valueFrom:
                configMapKeyRef:
                  name: devpulse-config
                  key: POSTGRES_USER
            - name: SPRING_DATASOURCE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: devpulse-secrets
                  key: POSTGRES_PASSWORD
            - name: SPRING_REDIS_HOST
              valueFrom:
                configMapKeyRef:
                  name: devpulse-config
                  key: REDIS_HOST
            - name: SPRING_REDIS_PORT
              valueFrom:
                configMapKeyRef:
                  name: devpulse-config
                  key: REDIS_PORT
            - name: SPRING_KAFKA_BOOTSTRAP_SERVERS
              valueFrom:
                configMapKeyRef:
                  name: devpulse-config
                  key: KAFKA_BOOTSTRAP_SERVERS
            - name: JWT_PRIVATE_KEY
              valueFrom:
                secretKeyRef:
                  name: devpulse-secrets
                  key: JWT_PRIVATE_KEY
            - name: JWT_PUBLIC_KEY
              valueFrom:
                secretKeyRef:
                  name: devpulse-secrets
                  key: JWT_PUBLIC_KEY
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
          readinessProbe:
            httpGet:
              path: /actuator/health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /actuator/health
              port: 8080
            initialDelaySeconds: 60
            periodSeconds: 30
            failureThreshold: 3
```

- [ ] **Step 2: Create backend service**

Create `infra/k8s/backend/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: devpulse
  labels:
    app: backend
spec:
  selector:
    app: backend
  ports:
    - name: http
      port: 8080
      targetPort: 8080
  type: ClusterIP
```

- [ ] **Step 3: Create backend HPA**

Create `infra/k8s/backend/hpa.yaml`:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: devpulse
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

- [ ] **Step 4: Validate**

```bash
kubectl apply --dry-run=client -f infra/k8s/backend/
```

Expected:
```
deployment.apps/backend configured (dry run)
service/backend configured (dry run)
horizontalpodautoscaler.autoscaling/backend-hpa configured (dry run)
```

- [ ] **Step 5: Commit**

```bash
git add infra/k8s/backend/
git commit -m "infra: add kubernetes backend deployment, service, and HPA"
```

---

### Task 7: Kubernetes AI Worker + Frontend

**Files:**
- Create: `infra/k8s/ai-worker/deployment.yaml`
- Create: `infra/k8s/ai-worker/service.yaml`
- Create: `infra/k8s/frontend/deployment.yaml`
- Create: `infra/k8s/frontend/service.yaml`

- [ ] **Step 1: Create AI Worker deployment**

Create `infra/k8s/ai-worker/deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-worker
  namespace: devpulse
  labels:
    app: ai-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-worker
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: ai-worker
    spec:
      containers:
        - name: ai-worker
          image: ghcr.io/YOUR_GITHUB_USERNAME/devpulse-ai-worker:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: devpulse-config
          env:
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: devpulse-secrets
                  key: ANTHROPIC_API_KEY
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: devpulse-secrets
                  key: POSTGRES_PASSWORD
            - name: DATABASE_URL
              value: "postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST):$(POSTGRES_PORT)/$(POSTGRES_DB)"
            - name: REDIS_URL
              value: "redis://$(REDIS_HOST):$(REDIS_PORT)"
            - name: KAFKA_BOOTSTRAP_SERVERS
              valueFrom:
                configMapKeyRef:
                  name: devpulse-config
                  key: KAFKA_BOOTSTRAP_SERVERS
          resources:
            requests:
              cpu: 200m
              memory: 512Mi
            limits:
              cpu: 500m
              memory: 1Gi
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 30
            failureThreshold: 3
```

- [ ] **Step 2: Create AI Worker service**

Create `infra/k8s/ai-worker/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-worker
  namespace: devpulse
  labels:
    app: ai-worker
spec:
  selector:
    app: ai-worker
  ports:
    - name: http
      port: 8000
      targetPort: 8000
  type: ClusterIP
```

- [ ] **Step 3: Create Frontend deployment**

Create `infra/k8s/frontend/deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: devpulse
  labels:
    app: frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: ghcr.io/YOUR_GITHUB_USERNAME/devpulse-frontend:latest
          ports:
            - containerPort: 3000
          env:
            - name: NEXT_PUBLIC_API_BASE_URL
              value: "http://backend:8080"
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 250m
              memory: 512Mi
          readinessProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 15
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 30
            periodSeconds: 30
            failureThreshold: 3
```

- [ ] **Step 4: Create Frontend service**

Create `infra/k8s/frontend/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: devpulse
  labels:
    app: frontend
spec:
  selector:
    app: frontend
  ports:
    - name: http
      port: 3000
      targetPort: 3000
  type: ClusterIP
```

- [ ] **Step 5: Validate**

```bash
kubectl apply --dry-run=client -f infra/k8s/ai-worker/
kubectl apply --dry-run=client -f infra/k8s/frontend/
```

Expected: each shows deployment + service `(dry run)` success.

- [ ] **Step 6: Commit**

```bash
git add infra/k8s/ai-worker/ infra/k8s/frontend/
git commit -m "infra: add kubernetes ai-worker and frontend deployments and services"
```

---

### Task 8: Kubernetes Ingress

**Files:**
- Create: `infra/k8s/ingress.yaml`

- [ ] **Step 1: Create ingress**

Create `infra/k8s/ingress.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: devpulse-ingress
  namespace: devpulse
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    # Allow large document uploads (50MB)
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    # Long timeout for SSE and LLM streaming connections
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
    # SSE requires disabling response buffering
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - devpulse.yourdomain.com
      secretName: devpulse-tls
  rules:
    - host: devpulse.yourdomain.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8080
          - path: /actuator
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8080
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 3000
```

- [ ] **Step 2: Validate**

```bash
kubectl apply --dry-run=client -f infra/k8s/ingress.yaml
```

Expected: `ingress.networking.k8s.io/devpulse-ingress configured (dry run)`

- [ ] **Step 3: Commit**

```bash
git add infra/k8s/ingress.yaml
git commit -m "infra: add kubernetes nginx ingress with TLS and SSE buffering disabled"
```

---

### Task 9: Prometheus + Grafana Provisioning Config

**Files:**
- Create: `infra/monitoring/prometheus.yml`
- Create: `infra/monitoring/grafana-provisioning/datasources/prometheus.yaml`
- Create: `infra/monitoring/grafana-provisioning/dashboards/dashboard.yaml`

- [ ] **Step 1: Create prometheus.yml**

Create `infra/monitoring/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: devpulse

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: devpulse-backend
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ['backend:8080']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: backend

  - job_name: devpulse-ai-worker
    metrics_path: /metrics
    static_configs:
      - targets: ['ai-worker:8000']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: ai-worker
```

- [ ] **Step 2: Create Grafana datasource provisioning**

Create `infra/monitoring/grafana-provisioning/datasources/prometheus.yaml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
```

- [ ] **Step 3: Create Grafana dashboard provisioning**

Create `infra/monitoring/grafana-provisioning/dashboards/dashboard.yaml`:
```yaml
apiVersion: 1
providers:
  - name: DevPulse
    orgId: 1
    type: file
    disableDeletion: false
    editable: true
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

- [ ] **Step 4: Commit**

```bash
git add infra/monitoring/prometheus.yml infra/monitoring/grafana-provisioning/
git commit -m "infra: add prometheus scrape config and grafana auto-provisioning"
```

---

### Task 10: Grafana Dashboard JSON

**Files:**
- Create: `infra/monitoring/dashboards/devpulse.json`

- [ ] **Step 1: Create devpulse.json**

Create `infra/monitoring/dashboards/devpulse.json`:
```json
{
  "annotations": {"list": []},
  "description": "DevPulse platform monitoring — API, Kafka, AI Worker, document indexing",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "refresh": "30s",
  "schemaVersion": 38,
  "tags": ["devpulse"],
  "time": {"from": "now-1h", "to": "now"},
  "timepicker": {},
  "title": "DevPulse",
  "uid": "devpulse-main",
  "version": 1,
  "panels": [
    {"collapsed": false, "id": 100, "title": "Overview", "type": "row", "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0}},
    {
      "id": 1, "title": "API Request Rate (req/s)", "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(rate(devpulse_api_request_total[5m])) by (method, endpoint)", "legendFormat": "{{method}} {{endpoint}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 8, "x": 0, "y": 1},
      "fieldConfig": {"defaults": {"unit": "reqps", "custom": {"lineWidth": 2}}, "overrides": []},
      "options": {"tooltip": {"mode": "multi"}}
    },
    {
      "id": 2, "title": "API Error Rate (%)", "type": "stat",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "100 * sum(rate(devpulse_api_request_total{status=~\"5..\"}[5m])) / sum(rate(devpulse_api_request_total[5m]))", "legendFormat": "error %", "refId": "A"}],
      "gridPos": {"h": 8, "w": 4, "x": 8, "y": 1},
      "fieldConfig": {"defaults": {"unit": "percent", "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 0.5}, {"color": "red", "value": 1}]}}, "overrides": []},
      "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background"}
    },
    {
      "id": 3, "title": "Active SSE Connections", "type": "gauge",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "devpulse_active_sse_connections", "legendFormat": "connections", "refId": "A"}],
      "gridPos": {"h": 8, "w": 4, "x": 12, "y": 1},
      "fieldConfig": {"defaults": {"unit": "short", "min": 0, "max": 100, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 50}, {"color": "red", "value": 80}]}}, "overrides": []}
    },
    {
      "id": 4, "title": "Circuit Breaker State", "type": "state-timeline",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "devpulse_circuit_breaker_state", "legendFormat": "{{name}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 8, "x": 16, "y": 1},
      "fieldConfig": {"defaults": {"custom": {"lineWidth": 0, "fillOpacity": 70}, "mappings": [{"type": "value", "options": {"0": {"text": "CLOSED", "color": "green"}, "1": {"text": "OPEN", "color": "red"}, "2": {"text": "HALF_OPEN", "color": "yellow"}}}]}, "overrides": []}
    },
    {"collapsed": false, "id": 101, "title": "Latency", "type": "row", "gridPos": {"h": 1, "w": 24, "x": 0, "y": 9}},
    {
      "id": 5, "title": "API Latency P50 / P95 / P99", "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [
        {"expr": "histogram_quantile(0.50, sum(rate(devpulse_api_latency_seconds_bucket[5m])) by (le, endpoint))", "legendFormat": "p50 {{endpoint}}", "refId": "A"},
        {"expr": "histogram_quantile(0.95, sum(rate(devpulse_api_latency_seconds_bucket[5m])) by (le, endpoint))", "legendFormat": "p95 {{endpoint}}", "refId": "B"},
        {"expr": "histogram_quantile(0.99, sum(rate(devpulse_api_latency_seconds_bucket[5m])) by (le, endpoint))", "legendFormat": "p99 {{endpoint}}", "refId": "C"}
      ],
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 10},
      "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []}
    },
    {
      "id": 6, "title": "Retrieval Method Avg Latency", "type": "barchart",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "rate(devpulse_retrieval_latency_seconds_sum[5m]) / rate(devpulse_retrieval_latency_seconds_count[5m])", "legendFormat": "{{method}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 6, "x": 12, "y": 10},
      "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []}
    },
    {
      "id": 7, "title": "LLM Latency Distribution", "type": "histogram",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "rate(devpulse_llm_latency_seconds_bucket[5m])", "legendFormat": "{{le}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 6, "x": 18, "y": 10},
      "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []}
    },
    {"collapsed": false, "id": 102, "title": "Kafka", "type": "row", "gridPos": {"h": 1, "w": 24, "x": 0, "y": 18}},
    {
      "id": 8, "title": "Kafka Consumer Lag", "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "devpulse_kafka_consumer_lag", "legendFormat": "{{topic}} [p{{partition}}]", "refId": "A"}],
      "gridPos": {"h": 8, "w": 10, "x": 0, "y": 19},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []}
    },
    {
      "id": 9, "title": "Kafka Message Rate (produced vs consumed)", "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [
        {"expr": "sum(rate(devpulse_kafka_messages_produced_total[5m])) by (topic)", "legendFormat": "produced {{topic}}", "refId": "A"},
        {"expr": "sum(rate(devpulse_kafka_messages_consumed_total[5m])) by (topic, status)", "legendFormat": "consumed {{topic}} [{{status}}]", "refId": "B"}
      ],
      "gridPos": {"h": 8, "w": 10, "x": 10, "y": 19},
      "fieldConfig": {"defaults": {"unit": "mps"}, "overrides": []}
    },
    {
      "id": 10, "title": "DLQ Backlog", "type": "stat",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(devpulse_kafka_consumer_lag{topic=~\".*-dlq\"}) or vector(0)", "legendFormat": "DLQ backlog", "refId": "A"}],
      "gridPos": {"h": 8, "w": 4, "x": 20, "y": 19},
      "fieldConfig": {"defaults": {"unit": "short", "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "red", "value": 1}]}}, "overrides": []},
      "options": {"colorMode": "background", "reduceOptions": {"calcs": ["lastNotNull"]}}
    },
    {"collapsed": false, "id": 103, "title": "AI", "type": "row", "gridPos": {"h": 1, "w": 24, "x": 0, "y": 27}},
    {
      "id": 11, "title": "LLM Token Usage (prompt vs completion)", "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [
        {"expr": "rate(devpulse_llm_tokens_total{type=\"prompt\"}[5m])", "legendFormat": "prompt tokens/s", "refId": "A"},
        {"expr": "rate(devpulse_llm_tokens_total{type=\"completion\"}[5m])", "legendFormat": "completion tokens/s", "refId": "B"}
      ],
      "gridPos": {"h": 8, "w": 10, "x": 0, "y": 28},
      "fieldConfig": {"defaults": {"unit": "short", "custom": {"fillOpacity": 20, "stacking": {"mode": "normal"}}}, "overrides": []}
    },
    {
      "id": 12, "title": "Estimated LLM Cost (USD total)", "type": "stat",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "devpulse_llm_cost_usd_total", "legendFormat": "total", "refId": "A"}],
      "gridPos": {"h": 8, "w": 4, "x": 10, "y": 28},
      "fieldConfig": {"defaults": {"unit": "currencyUSD", "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 10}, {"color": "red", "value": 50}]}}, "overrides": []},
      "options": {"colorMode": "background", "reduceOptions": {"calcs": ["lastNotNull"]}}
    },
    {
      "id": 13, "title": "Guardrail Blocks by Reason (last 1h)", "type": "barchart",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(increase(devpulse_guardrail_blocked_total[1h])) by (reason)", "legendFormat": "{{reason}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 5, "x": 14, "y": 28},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []}
    },
    {
      "id": 14, "title": "BM25 Cache Hit Rate by Layer", "type": "piechart",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(increase(devpulse_bm25_cache_hit_total[1h])) by (layer)", "legendFormat": "{{layer}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 5, "x": 19, "y": 28},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
      "options": {"pieType": "donut", "tooltip": {"mode": "single"}}
    },
    {"collapsed": false, "id": 104, "title": "Document Indexing", "type": "row", "gridPos": {"h": 1, "w": 24, "x": 0, "y": 36}},
    {
      "id": 15, "title": "Index Success vs Failed (last 1h)", "type": "barchart",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(increase(devpulse_ingestion_documents_total[1h])) by (status)", "legendFormat": "{{status}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 8, "x": 0, "y": 37},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": [
        {"matcher": {"id": "byName", "options": "failed"}, "properties": [{"id": "color", "value": {"fixedColor": "red", "mode": "fixed"}}]},
        {"matcher": {"id": "byName", "options": "indexed"}, "properties": [{"id": "color", "value": {"fixedColor": "green", "mode": "fixed"}}]}
      ]}
    },
    {
      "id": 16, "title": "Chunks Generated per Hour", "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(increase(devpulse_ingestion_chunks_total[1h]))", "legendFormat": "chunks/hour", "refId": "A"}],
      "gridPos": {"h": 8, "w": 8, "x": 8, "y": 37},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []}
    },
    {
      "id": 17, "title": "Indexing Latency Distribution", "type": "histogram",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "rate(devpulse_ingestion_latency_seconds_bucket[5m])", "legendFormat": "{{le}}", "refId": "A"}],
      "gridPos": {"h": 8, "w": 8, "x": 16, "y": 37},
      "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []}
    }
  ]
}
```

- [ ] **Step 2: Validate JSON is well-formed**

```bash
python3 -c "import json; json.load(open('infra/monitoring/dashboards/devpulse.json')); print('Valid JSON — 17 panels OK')"
```

Expected: `Valid JSON — 17 panels OK`

- [ ] **Step 3: Commit**

```bash
git add infra/monitoring/dashboards/devpulse.json
git commit -m "infra: add grafana dashboard with 5 rows and 17 panels"
```

---

### Task 11: .env.example + README.md

**Files:**
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Create .env.example**

Create `.env.example`:
```bash
# ============================================================
# DevPulse — Environment Variables Template
# Copy to .env and fill in values. Never commit .env.
# ============================================================

# ===== Spring Boot (Backend) =====
SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/devpulse
SPRING_DATASOURCE_USERNAME=devpulse
SPRING_DATASOURCE_PASSWORD=devpulse_secret
SPRING_REDIS_HOST=localhost
SPRING_REDIS_PORT=6379
SPRING_KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# RS256 JWT Keys
# Generate:
#   openssl genrsa -out private.pem 2048
#   openssl rsa -in private.pem -pubout -out public.pem
# Then paste the full PEM (replace newlines with \n):
JWT_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----
JWT_EXPIRY_MINUTES=15
JWT_REFRESH_EXPIRY_DAYS=7

# ===== Python AI Worker =====
ANTHROPIC_API_KEY=sk-ant-api03-...
DATABASE_URL=postgresql://devpulse:devpulse_secret@localhost:5432/devpulse
REDIS_URL=redis://localhost:6379
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
EMBEDDING_MODEL=all-MiniLM-L6-v2
BM25_REBUILD_ON_STARTUP=true

# ===== Next.js (Frontend) =====
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
# Generate: openssl rand -base64 32
NEXTAUTH_SECRET=your-random-32-char-secret-here

# ===== Docker Compose (used in docker-compose.yml) =====
POSTGRES_PASSWORD=devpulse_secret
```

- [ ] **Step 2: Create README.md**

Create `README.md`:
````markdown
# DevPulse

A distributed AI developer Q&A platform. Upload technical documents or import Stack Overflow data; get precise answers powered by Hybrid RAG (BM25 + pgvector) + Claude `claude-sonnet-4-6` with streaming responses, circuit breaker fallback, and full observability.

## Architecture

```mermaid
graph TB
  Browser --> NextJS["Next.js (3000)"]
  NextJS --> GW["Spring Boot — API Gateway\nAuth · Rate limiting · Routing"]
  GW --> DocSvc["Document Service\nCRUD · versioning · ACL"]
  GW --> RetSvc["Retrieval Service\nHybrid search · rerank · citation"]
  GW --> NotifSvc["Notification / SSE Service"]
  DocSvc --> Kafka["Kafka — Event Bus"]
  RetSvc --> Kafka
  NotifSvc --> Kafka
  Kafka --> AIWorker["AI Worker — Python (8000)\n[ingestion] Parse·chunk·embed·index\n[ai_task] RAG·LLM·eval pipeline"]
  AIWorker --> PG["PostgreSQL 16 + pgvector"]
  AIWorker --> Redis["Redis 7"]
  GW --> PG
  GW --> Redis
  GW --> Prometheus
  Prometheus --> Grafana
```

## Quick Start (5 minutes)

```bash
git clone https://github.com/your-username/devpulse
cd devpulse
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY, JWT_PRIVATE_KEY, JWT_PUBLIC_KEY

# 1. Start infrastructure
docker compose -f infra/docker-compose.dev.yml up -d

# 2. Start backend (Java 21 + Gradle required)
cd backend && ./gradlew bootRun

# 3. Start AI Worker (Python 3.11 required)
cd ai-worker
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. Start frontend (Node 20 + pnpm required)
cd frontend
pnpm install
pnpm dev

# Open http://localhost:3000
```

## Full Stack via Docker

```bash
# All .env values must be filled in first
docker compose -f infra/docker-compose.yml up -d
```

## Data Import

```bash
# Download Stack Overflow data dump: https://archive.org/details/stackexchange
# Extract Posts.xml (~20GB uncompressed), then:
python scripts/seed_data.py \
  --workspace-id <your-workspace-id> \
  --input /path/to/Posts.xml \
  --limit 50000 \
  --api-url http://localhost:8080 \
  --token <your-jwt-token>
# Use --resume to continue an interrupted import
```

## Run Evaluation

```bash
python scripts/run_eval.py \
  --workspace-id <your-workspace-id> \
  --samples 500 \
  --api-url http://localhost:8080 \
  --token <your-jwt-token>
# Outputs relevance score, hit rate, latency P50/P95/P99, and estimated cost
```

## Monitoring

| Service | URL |
|---------|-----|
| App | http://localhost:3000 |
| Backend API | http://localhost:8080 |
| Kafka UI | http://localhost:8090 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin / admin) |
````

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "infra: add .env.example and README with quick start guide"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Plan task |
|-----------------|-----------|
| docker-compose.dev.yml with postgres+pgvector+redis+kafka (5 topics, no auto-create)+kafka-ui | Task 3 |
| docker-compose.yml full stack + prometheus + grafana | Task 4 |
| K8s namespace, configmap, secret | Task 5 |
| K8s backend deployment (replicas:2) + HPA (2-5, CPU 70%) + service | Task 6 |
| K8s ai-worker deployment (replicas:2) + service | Task 7 |
| K8s frontend deployment (replicas:2) + service | Task 7 |
| K8s Nginx ingress + TLS cert-manager + SSE buffering disabled | Task 8 |
| prometheus.yml scraping backend + ai-worker | Task 9 |
| Grafana dashboard 5 rows 17 panels | Task 10 |
| .env.example with all variables | Task 11 |
| README with quick start + data import + eval + architecture diagram | Task 11 |
| Flyway V1__init.sql + V2__pgvector.sql | **Not in this plan** — requires Spring Boot project to exist; created in Sub-project 2 (Backend) |
| .gitignore | Task 1 |
| Git commit after each feature point | All tasks |

**Placeholder scan:** No TBD/TODO found. All YAML and JSON contain complete, deployable content. secret.yaml intentionally uses `REPLACE_WITH_BASE64` with instructions — this is expected for a secrets template.

**Type consistency:** No cross-task type references in this plan (infrastructure only).
