# Setup and build for the app:

## make the env setup

create a file named .flaskenv and configure the environment variables

* FLASK_APP = app
* FLASK_DEBUG =1
* DB_USER = file_extractor
* DB_PASSWORD = password
* DB_HOST = db
* DB_NAME = file_extractor_db
* POSTGRES_USER = file_extractor
* POSTGRES_PASSWORD = password
* POSTGRES_DB = file_extractor_db
* POSTGRES_HOST = db
* DATABASE_URL = postgresql://file_extractor:password@db/file_extractor_db
* WEB_CONCURRENCY = 2
* SCAN_WORKERS = 4
* GUNICORN_TIMEOUT = 120

## to build 

run - docker-compose up --build

## to shutdown 

run - docker-compose down

## connect to database - 

docker-compose exec db psql -U file_extractor -d file_extractor_db

## connect app to shell -

docker-compose exec web sh


