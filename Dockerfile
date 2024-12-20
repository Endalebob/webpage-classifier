# Use a standard Python 3.12 slim image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and both Chromium and Firefox browsers
RUN pip install playwright && playwright install chromium firefox

# Install required libraries for Chromium and Firefox to run in headless mode
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libexpat1 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libgtk-3-0 \
    libxshmfence1 \
    libxtst6 \
    fonts-liberation \
    fonts-noto-color-emoji \
    libfontconfig1 \
    libfreetype6 \
    libxrender1 \
    libxinerama1 \
    libx11-xcb1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the application code
COPY . .

# Expose the port that FastAPI will run on
EXPOSE 8001

# Run FastAPI app using Uvicorn with multiple workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
