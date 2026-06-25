import mysql.connector
import os
from config import Config

import mysql.connector.pooling

db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        db_config = {
            "host": Config.DB_HOST,
            "port": Config.DB_PORT,
            "user": Config.DB_USER,
            "password": Config.DB_PASSWORD,
            "database": Config.DB_NAME,
            "pool_name": "mypool",
            "pool_size": 10,
            "pool_reset_session": False
        }
        db_pool = mysql.connector.pooling.MySQLConnectionPool(**db_config)

def get_db():
    """Get a MySQL connection from the pool for the current request."""
    global db_pool
    if db_pool is None:
        init_db_pool()
    return db_pool.get_connection()

def init_db_schema():
    print("Initializing database schema...")
    try:
        config_no_db = {
            "host": Config.DB_HOST,
            "port": Config.DB_PORT,
            "user": Config.DB_USER,
            "password": Config.DB_PASSWORD
        }
        
        conn = mysql.connector.connect(**config_no_db)
        cursor = conn.cursor()
        
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
            conn.commit()
            print("Database and tables initialized successfully.")
        else:
            print(f"schema.sql not found at {schema_path}")
            
        cursor.close()
        conn.close()
    except Exception as e:
        import traceback
        print("Error during database initialization/migration:")
        print(traceback.format_exc())
