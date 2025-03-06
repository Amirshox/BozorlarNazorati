# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app


# Copy the requirements file into the container
ADD ./requirements.txt /app/requirements.txt



# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt





# Copy the FastAPI application code into the container
ADD . /app

# Expose the port on which the FastAPI application will run
EXPOSE 8012

