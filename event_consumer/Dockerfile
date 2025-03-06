# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file to the working directory
ADD ./requirements.txt /app/requirements.txt

# Install any needed dependencies specified in requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Set the command to run your Python script
CMD [ "python", "main.py" ]
