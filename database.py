import mysql.connector
import os
from config import Config

def get_db():
    """Open a new MySQL connection for the current request."""
    db_config = {
        "host": Config.DB_HOST,
        "user": Config.DB_USER,
        "password": Config.DB_PASSWORD,
        "database": Config.DB_NAME
    }
    return mysql.connector.connect(**db_config)

def init_db_schema():
    print("Initializing database schema...")
    try:
        config_no_db = {
            "host": Config.DB_HOST,
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
