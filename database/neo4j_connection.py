from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

def get_neo4j_connection():
    """Create and return a Neo4j connection."""
    try:
        # Get environment variables
        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        user = os.getenv('NEO4J_USER')
        password = os.getenv('NEO4J_PASSWORD')
        database = os.getenv('NEO4J_DATABASE', 'academicworld')

        print("\nAttempting to connect to Neo4j...")
        print(f"URI: {uri}")
        print(f"Database: {database}")

        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session(database=database) as session:
            try:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]
                print("Basic connection test successful")
                
                result = session.run("MATCH (n) RETURN count(n) as count")
                count = result.single()["count"]
                print(f"Successfully connected to Neo4j!")
                print(f"Total number of nodes in database: {count}")
            except Exception as e:
                print(f"Error executing test query: {e}")
                raise
        
        return driver
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        return None
