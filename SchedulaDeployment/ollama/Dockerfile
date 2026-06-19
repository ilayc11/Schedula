FROM ollama/ollama:latest

# Install curl for healthchecks and keep-alive pings
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Keep default CMD from base image
