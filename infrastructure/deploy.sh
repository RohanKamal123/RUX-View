#!/usr/bin/env bash
set -euo pipefail

# Default values
ENV="staging"
TAG=""
SKIP_TESTS=false
ROLLBACK=false

# Function to display usage
usage() {
    echo "Usage: $0 --env <staging|production> --tag <tag> [--skip-tests] [--rollback]"
    echo "  --env         Target environment (staging or production)"
    echo "  --tag         Docker image tag (e.g., v1.0.0)"
    echo "  --skip-tests  Skip running test suite"
    echo "  --rollback    Rollback to previous deployment on failure"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        *)
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$ENV" || -z "$TAG" ]]; then
    usage
fi

# Validate environment
if [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
    echo "Error: --env must be either 'staging' or 'production'"
    usage
fi

# Validate prerequisites
echo "Validating prerequisites..."
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud not found. Please install Google Cloud SDK."
    exit 1
fi
if ! command -v docker &> /dev/null; then
    echo "Error: docker not found. Please install Docker."
    exit 1
fi
if ! command -v python &> /dev/null; then
    echo "Error: python not found. Please install Python."
    exit 1
fi

# Get git commit hash for revision name
GIT_SHA=$(git rev-parse --short HEAD)
echo "Git commit SHA: $GIT_SHA"

# Set variables
PROJECT_ID="rux-view-497104"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/visionos:$TAG"
SERVICE_NAME="visionos-backend"

# Function to run tests
run_tests() {
    if [[ "$SKIP_TESTS" == false ]]; then
        echo "Running test suite..."
        pytest backend/tests/ -v
    else
        echo "Skipping test suite..."
    fi
}

# Function to build and push Docker image
build_and_push() {
    echo "Building Docker image: $IMAGE_NAME"
    docker build -t "$IMAGE_NAME" .
    echo "Pushing Docker image to Container Registry..."
    docker push "$IMAGE_NAME"
}

# Function to deploy to Cloud Run
deploy_to_cloud_run() {
    echo "Deploying to Cloud Run service: $SERVICE_NAME in $ENV (region: $REGION)"
    gcloud run deploy "$SERVICE_NAME" \
        --image="$IMAGE_NAME" \
        --platform=managed \
        --region="$REGION" \
        --allow-unauthenticated \
        --revision-suffix="$GIT_SHA" \
        --project="$PROJECT_ID" \
        --quiet
}

# Function to get deployed URL
get_deployed_url() {
    gcloud run services describe "$SERVICE_NAME" \
        --platform=managed \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format='value(status.url)'
}

# Function to run smoke test
run_smoke_test() {
    local url="$1"
    echo "Running smoke test against $url"
    # Simple health check
    local health_endpoint="$url/health"
    local max_attempts=10
    local attempt=1
    until curl -sf "$health_endpoint" > /dev/null; do
        if [[ $attempt -ge $max_attempts ]]; then
            echo "Smoke test failed: $health_endpoint not responding after $max_attempts attempts"
            return 1
        fi
        echo "Attempt $attempt: waiting for health endpoint..."
        sleep 10
        ((attempt++))
    done
    echo "Smoke test passed: health endpoint is responding"
}

# Function to rollback deployment
rollback_deployment() {
    echo "Rolling back deployment..."
    # Get the previous revision (not the current one)
    PREVIOUS_REVISION=$(gcloud run services describe "$SERVICE_NAME" \
        --platform=managed \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format='value(status.latestCreatedRevision)' | head -n 2 | tail -n 1)
    if [[ -z "$PREVIOUS_REVISION" || "$PREVIOUS_REVISION" == *"$GIT_SHA"* ]]; then
        echo "No previous revision found to rollback to."
        return 1
    fi
    echo "Rolling back to revision: $PREVIOUS_REVISION"
    gcloud run services update-traffic "$SERVICE_NAME" \
        --platform=managed \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --to-revisions="$PREVIOUS_REVISION=100" \
        --quiet
}

# Main deployment steps
main() {
    echo "Starting deployment to $ENV environment with tag $TAG"
    
    # Run tests
    run_tests
    
    # Build and push Docker image
    build_and_push
    
    # Deploy to Cloud Run
    deploy_to_cloud_run
    
    # Get deployed URL
    DEPLOYED_URL=$(get_deployed_url)
    echo "Deployed to: $DEPLOYED_URL"
    
    # Run smoke test
    if ! run_smoke_test "$DEPLOYED_URL"; then
        echo "Smoke test failed."
        if [[ "$ROLLBACK" == true ]]; then
            rollback_deployment
        fi
        exit 1
    fi
    
    echo "Deployment completed successfully!"
}

# Trap errors and rollback if requested
if [[ "$ROLLBACK" == true ]]; then
    trap 'echo "Deployment failed. Initiating rollback..."; rollback_deployment' ERR
fi

# Run main function
main "$@"
