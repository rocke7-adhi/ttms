import mysql.connector
from config import Config

try:
    # First connect without database
    db = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        port=Config.MYSQL_PORT
    )

    cursor = db.cursor()

    # Drop database if exists
    cursor.execute("DROP DATABASE IF EXISTS faculty_timetable")
    
    # Create database without character set specification
    cursor.execute("CREATE DATABASE faculty_timetable")
    print("Database created successfully!")

    # Close first connection
    cursor.close()
    db.close()

    # Connect to the faculty_timetable database
    db = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        port=Config.MYSQL_PORT,
        database=Config.MYSQL_DB
    )

    cursor = db.cursor()

    # Read SQL file
    with open('faculty_timetable.sql', 'r') as file:
        # Remove the database creation commands
        sql_content = file.read()
        sql_commands = sql_content.split(';')
        # Filter out database creation and use commands
        sql_commands = [cmd for cmd in sql_commands if not cmd.strip().upper().startswith(('CREATE DATABASE', 'USE'))]

    # Execute each command
    for command in sql_commands:
        if command.strip():
            try:
                cursor.execute(command)
                db.commit()
            except mysql.connector.Error as err:
                print(f"Error executing command: {err}")
                continue

    print("Database populated successfully!")

except mysql.connector.Error as err:
    print(f"Error: {err}")

finally:
    if 'cursor' in locals():
        cursor.close()
    if 'db' in locals():
        db.close() 