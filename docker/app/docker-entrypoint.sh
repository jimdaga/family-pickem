#!/bin/sh

check_postgres () {

  # Postgres Settings
  DATABASE_HOST=${DATABASE_HOST:="postgresql"}
  DATABASE_PORT=${DATABASE_PORT:="5432"}
  DATABASE_USER=${DATABASE_USER:="postgres"}
  DATABASE_NAME=${DATABASE_NAME:="pickem"}

  echo "Waiting for django postgresql connection..."
  echo
  echo "   DATABASE_HOST=${DATABASE_HOST}"
  echo "   DATABASE_PORT=${DATABASE_PORT}"
  echo "   DATABASE_USER=${DATABASE_USER}"
  echo "   DATABASE_NAME=${DATABASE_NAME}"
  echo

  while /bin/true ; do
    pg_isready --host=${DATABASE_HOST} --port=${DATABASE_PORT} --user=${DATABASE_USER} --dbname=${DATABASE_NAME} > /dev/null 2>&1
    status=$?

    if [ "$status" = "0" ] ; then
      # PostgreSQL is accepting connections.
      echo "PostgreSQL is online"
      break
    elif [ "$status" = "3" ] ; then
      # pg_isready failed
      echo "Check that POSTGRES_HOST, POSTGRES_PORT, and POSTGRES_USER are set correctly."
      exit 1
    else
      echo "Postgres is still starting..."
    fi

    sleep 5
  done
}

# Check that postgres is working before starting the app
check_postgres

if [ "$1" = "migrate" ]; then
  # initContainer mode: prepare static files and run migrations, then exit.
  # Kept out of the main container so the liveness probe never SIGKILLs a
  # long-running migration mid-flight (seen on the 0.0.135 prd rollout).
  # Only committed migrations are applied — generating migrations at deploy
  # time (the old makemigrations step) invites schema drift the repo can't
  # reproduce.
  python manage.py collectstatic --noinput
  python manage.py migrate
  exit 0
fi

# Start Server
export RUN_WEB_SERVER=true
python manage.py runserver 0.0.0.0:8000
