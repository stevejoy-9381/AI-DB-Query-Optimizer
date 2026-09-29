import mysql.connector

def connect_db():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="yourpassword",
        database="company_db"
    )
    return connection
