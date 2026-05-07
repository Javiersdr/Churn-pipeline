FROM python:3.12-slim
# Slim version is okay

# Now we install git and delete cache
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# I already had created a requirements file, so we will keep using it
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

# We can copy the rest of the project now
COPY . .

CMD ["bash"]