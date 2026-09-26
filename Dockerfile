FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user (Hugging Face Spaces requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Copy the rest of the application
COPY --chown=user . .

# Expose the port Hugging Face looks for
EXPOSE 7860

# Run the startup script
CMD ["bash", "start.sh"]
