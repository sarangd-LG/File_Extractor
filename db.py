# Configuration 
# The service is configured via environment variables (or a config file): 
# •	DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_TABLE 
# •	CONCURRENCY — number of parallel workers (optional, with a sensible default) 
# •	PORT — HTTP port to listen on 


from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()