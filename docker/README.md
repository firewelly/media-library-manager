# Media Library Docker Deployment

This directory contains the Dockerized version of the Media Library application, featuring a Vue 3 frontend and a FastAPI backend.

## Structure

- `backend/`: FastAPI application code, database models, and migration scripts.
- `frontend/`: Vue 3 application code.
- `docker-compose.yml`: Orchestration file to run both services.

## Prerequisites

- Docker and Docker Compose installed on your NAS or server.

## Deployment Instructions

1.  **Transfer Files**: Copy the entire `docker` folder to your NAS/Server.
    ```bash
    scp -r docker user@your-nas-ip:/path/to/deployment/
    ```

2.  **Database Migration (Optional)**:
    If you want to keep your existing data, copy your `media_library.db` file to the `docker/data` directory (create it if it doesn't exist).
    ```bash
    mkdir -p docker/data
    cp /path/to/existing/media_library.db docker/data/
    ```
    *Note: If you don't provide a database, a new one will be created automatically.*

3.  **Configure Media Paths**:
    Edit `docker-compose.yml` to mount your media folders into the backend container.
    ```yaml
    services:
      backend:
        volumes:
          - ./data:/app/data
          - /path/to/your/nas/media:/media  # <--- Add this line
    ```
    *Make sure the internal path (`/media`) matches what you expect, or update your database paths accordingly.*

4.  **Start the Services**:
    Run the following command inside the `docker` folder:
    ```bash
    docker-compose up -d --build
    ```

5.  **Access the Application**:
    Open your browser and navigate to:
    `http://<your-nas-ip>`

## Features

- **Frontend**: Modern Vue 3 interface to browse and search videos.
- **Backend**: FastAPI server handling database operations.
- **Scanning**: The backend includes `fast_smart_media_updater.py` which can be run inside the container to scan for new files.
    ```bash
    docker exec -it media-library-backend python fast_smart_media_updater.py --path /media/folder
    ```

## Development

- Frontend runs on port 80 (mapped from internal port 80).
- Backend runs on port 8000.
