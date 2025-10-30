# Deployment

**Navigation**: [Documentation Home](../INDEX.md) > [Development](./INDEX.md) > Deployment

## Overview

Docker-based deployment, environment configuration, and production best practices.

## Deployment Options

### Local Development

**Use Case**: Development and testing
**Setup**: SQLite database, local file system, run directly without containers
**Configuration**: Development defaults
**See**: [Getting Started](./getting-started.md)

### Docker Deployment (Recommended)

**Use Case**: Containerized deployment for consistency and isolation
**Setup**: Docker Compose orchestration
**Services**: Backend API, frontend static files, optional database
**Configuration**: Environment-based

### Production Deployment

**Use Case**: Production with scalability and reliability
**Setup**: Container orchestration (Docker Compose, Kubernetes)
**Services**: Load-balanced API, CDN-served frontend, PostgreSQL database
**Configuration**: Production-hardened with secrets management
**Monitoring**: Comprehensive logging and observability

## Docker Configuration

**Location**: `docker-compose.yml` in project root

**Services**:
- **backend**: FastAPI application (Dockerfile: `backend/Dockerfile`, Python 3.12+, uv for dependencies, non-root user, health check)
- **frontend**: Nginx serving built React app (Dockerfile: `frontend/Dockerfile`, multi-stage build, SPA routing, gzip compression)
- **database**: PostgreSQL (optional, defaults to SQLite)

**Volume Mounts**: Local codebases, database data, configuration files

## Environment Configuration

### Backend Environment Variables

**Required for Production**:
```bash
DATABASE_URL=postgresql://user:password@localhost/devboard
OPENAI_API_KEY=your_openai_key  # At least one LLM provider required
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=https://your-domain.com
```

**Optional Integrations**:
```bash
GITHUB_ACCESS_TOKEN=your_github_token
JIRA_BASE_URL=https://company.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_jira_token
SLACK_BOT_TOKEN=your_slack_token
LOGFIRE_TOKEN=your_logfire_token  # Observability
```

**Optional Configuration**:
```bash
PORT=8000
LOG_LEVEL=INFO
DEBUG=false
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

### Frontend Environment Variables

**Required for Production**:
```bash
VITE_API_BASE_URL=https://api.devboard.com
```

## Deployment Steps

### Docker Compose Deployment

1. **Set Environment Variables**: Create `.env` file in project root with required variables
2. **Build Images**: `docker-compose build`
3. **Start Services**: `docker-compose up -d`
4. **Run Migrations**: `docker-compose exec backend alembic upgrade head`
5. **Verify Health**: Check `http://localhost:8000/health`

### Kubernetes Deployment

**Configuration**: Kubernetes manifests for deployments, services, ingress
**Secrets**: Use Kubernetes secrets for sensitive configuration
**Persistent Storage**: PersistentVolumeClaims for database and codebase data
**Ingress**: Configure ingress for external access with TLS

## Production Best Practices

### Security

- Use environment variables for secrets, never commit to version control
- Enable HTTPS/TLS for all external connections
- Set `ALLOWED_ORIGINS` to restrict CORS to trusted domains
- Run containers as non-root user
- Keep dependencies updated with security patches

### Database

- Use PostgreSQL for production (better concurrency than SQLite)
- Enable connection pooling (`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`)
- Regular backups (automated with retention policy)
- Monitor query performance

### Monitoring

- Enable structured logging (`LOG_LEVEL=INFO` or `WARNING` for production)
- Use Logfire or similar for observability
- Set up health check monitoring
- Track API response times and error rates
- Monitor resource usage (CPU, memory, disk)

### Scaling

- Horizontal scaling: Run multiple backend instances behind load balancer
- Database: Use connection pooling, consider read replicas for heavy read workloads
- Frontend: Serve static files via CDN
- Caching: Cache LLM responses and external API calls where appropriate

### Backups

- **Database**: Daily automated backups with 30-day retention
- **Configuration**: Backup `.env` files securely
- **Codebase Data**: Backup linked codebases or ensure regeneration capability

## Troubleshooting

### Common Issues

**Database Connection Errors**: Verify `DATABASE_URL` format and credentials
**LLM API Errors**: Check API keys are valid and have quota
**Frontend 404 Errors**: Ensure Nginx configured for SPA routing
**Container Startup Failures**: Check logs with `docker-compose logs <service>`

### Health Checks

**Backend**: `GET /health` returns status, version, database connection
**Frontend**: Check Nginx is serving files correctly

### Logs

**Docker Compose**: `docker-compose logs -f <service>`
**Kubernetes**: `kubectl logs <pod-name>`

## See Also

- [Getting Started](./getting-started.md) - Local development setup
- [Contributing](./contributing.md) - Development workflow
- [Testing](./testing.md) - Testing guidelines
