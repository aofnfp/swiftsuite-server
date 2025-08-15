# Base image

FROM python:3.11-slim
 
# Set working directory

WORKDIR /app

# Install system dependencies for mysqlclient and other build tools
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    musl-dev \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching

COPY ./app/requirements.txt /app/requirements.txt
 
# Install Python dependencies

RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt
 
# Copy project files

COPY ./app /app
 
# Collect static files

RUN python manage.py collectstatic
 
# Expose port (CapRover will map this)

EXPOSE 8000
 
# Start Gunicorn server

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "your_project.wsgi:application", "--workers", "4"]
 
