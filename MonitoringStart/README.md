# Activity Log Dashboard (React + FastAPI)

A full-stack application for viewing daily log summaries and detailed user activity, built with a minimalistic UI.

## 1. Project Overview & Architecture

This project consists of a React frontend that communicates with a FastAPI backend to display user activity logs. The backend, in turn, interacts with a PostgreSQL database to store and retrieve log data.

**Key Technologies:**

*   **Frontend:** React (Functional Hooks, Single-file App.jsx), Tailwind CSS
*   **Backend:** Python 3.10+, FastAPI, Uvicorn
*   **Database:** PostgreSQL

**Interaction Flow:**

`React (Frontend)` -> `FastAPI (Backend)` -> `PostgreSQL (Database)`

The FastAPI backend uses CORS (Cross-Origin Resource Sharing) middleware to allow requests from the React frontend.

## 2. Local Setup & Development

### Backend Setup (Python/FastAPI)

1.  **Create a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r backend/requirements.txt
    ```

3.  **Run the server:**

    ```bash
    uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
    ```

### Frontend Setup (Node/React)

1.  **Navigate to the frontend directory:**

    ```bash
    cd frontend
    ```

2.  **Install dependencies:**

    ```bash
    npm install
    ```

3.  **Run the development server:**

    ```bash
    npm run dev
    ```

## 3. API Endpoints Reference

The following are the core API endpoints. Interactive documentation (Swagger UI) is also available at `/docs` when the backend server is running.

| Method | Path                | Description                                      |
| :----- | :------------------ | :----------------------------------------------- |
| `POST` | `/logs`             | Creates a new activity log entry.                |
| `GET`  | `/logs`             | Retrieves a list of log entries with pagination. |
| `GET`  | `/logs/{id}`        | Retrieves a single log entry by its ID.          |
| `GET`  | `/logs/search`      | Searches for log entries by app name.            |
| `GET`  | `/api/logs/daily`   | Retrieves a summary of all log days.             |
| `GET`  | `/api/logs/detail/{date}` | Retrieves detailed log entries for a specific date. |

## 4. Deployment Guide (Production)

For production, the frontend and backend should be deployed separately.

*   **Frontend (React):** Deploy as a static site to a service like Vercel or Netlify.
*   **Backend (FastAPI):** Deploy as a web service to a PaaS like Render or Railway.

**Critical Post-Deployment Steps:**

1.  **Update Frontend API URL:** In the React `App.jsx` file, replace the local API URL (`http://localhost:8000`) with your deployed backend URL.
2.  **Configure Backend CORS:** In the FastAPI backend, update the `CORS_ORIGINS` environment variable to include the domain of your deployed frontend.

## 5. Environmental Variables & Configuration

The backend requires the following environment variables to be set in production:

| Variable        | Description                                      | Example Format                                    |
| :-------------- | :----------------------------------------------- | :------------------------------------------------ |
| `DATABASE_URL`  | The connection string for the PostgreSQL database. | `postgresql://user:password@host:port/dbname`     |
| `CORS_ORIGINS`  | A comma-separated list of allowed frontend origins. | `"https://your-frontend-domain.com"`                |
