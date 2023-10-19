FROM python:3.10

# Setup Work Directory 
ENV WORK_DIR=/code

# Create user and group to run container as
RUN useradd -ms /bin/bash django

# Setup App
COPY --chown=django:django pickem ${WORK_DIR}
COPY --chown=django:django docker/app/docker-entrypoint.sh ${WORK_DIR}/bin/docker-entrypoint.sh 

# Install Packages
RUN apt update && apt install -y postgresql-client
RUN pip install --upgrade pip

# Switch user/workdir 
USER django
WORKDIR ${WORK_DIR}

# Set environment variables  
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1 

# Install Dependencies 
COPY pickem/requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose App Port and run server
EXPOSE 8000
ENTRYPOINT ["/code/bin/docker-entrypoint.sh"]