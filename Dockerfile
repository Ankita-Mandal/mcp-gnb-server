FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including sudo and OAI dependencies
RUN apt-get update && \
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        sudo \
        procps \
        libsctp1 \
        libsctp-dev \
        libconfig-dev \
        # libconfig++9v5 \
        libblas-dev \
        liblapack-dev \
        liblapacke-dev \
        libfftw3-dev \
        libmbedtls-dev \
        # libmbedcrypto7 \
        # libmbedx509-1 \
        libpthread-stubs0-dev \
        libusb-1.0-0-dev \
        usbutils \
        libczmq-dev \
        python3-dev \
        build-essential \
        git \
        && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce-cli docker-compose-plugin && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python modules (needed for imports)
COPY action_logger.py .
COPY helper.py .

# Configure sudo without password for root user
RUN echo "root ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    echo "Defaults !requiretty" >> /etc/sudoers

# Create necessary directories
RUN mkdir -p /app/logs /app/scripts

# Copy scripts and make them executable
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000
ENV LOG_LEVEL=INFO

# Expose the port
EXPOSE 8000

# Default command (will be overridden by docker-compose)
CMD ["python", "server.py"]