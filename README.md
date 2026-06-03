# CeramiKG

CeramiKG is a ceramic-materials knowledge graph construction and visualization system. It includes a Vue frontend, a FastAPI knowledge graph backend, a PDF processing service, and local database/search services.

## Project Structure

- `kg-managesystem-master/`: Vue 3 + Vite frontend.
- `cig-kg-backend-master/`: FastAPI knowledge graph backend.
- `pdf-flask-handler/`: PDF upload, parsing, and document processing service.
- `mysql-init/`: MySQL initialization scripts.
- `docker-compose.yml`: Local Docker Compose orchestration.
- `PROJECT_MANUAL.md`: System design and project manual.

## Quick Start

1. Create local environment files:

   ```bash
   cp .env.example .env
   cp cig-kg-backend-master/.env.example cig-kg-backend-master/.env
   ```

2. Update passwords, ports, and model API settings in `.env`.

3. Start the stack:

   ```bash
   docker compose up -d --build
   ```

4. Default URLs:

   - Frontend: `http://localhost:8080`
   - KG backend docs: `http://localhost:8000/docs`
   - PDF service: `http://localhost:8001`

## Git Notes

Local `.env` files, uploads, caches, logs, and build outputs are ignored. Use the `.env.example` files as templates for deployment or local development.
