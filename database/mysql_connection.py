import pymysql
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def get_mysql_connection():
    """Create and return a MySQL database connection."""
    try:
        connection = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            port=int(os.getenv("MYSQL_PORT", 3306))  # Fallback to 3306 if not set
        )
        print("Successfully connected to MySQL!")
        return connection
    except Exception as e:
        print(f"Error connecting to MySQL: {e}")
        return None