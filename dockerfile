# Use an official Python runtime as a parent image
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Set environment variables for configuration
ENV DASH_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8050

# Expose the port Dash runs on
EXPOSE $PORT

# Command to run the application
CMD ["python", "app.py"]
