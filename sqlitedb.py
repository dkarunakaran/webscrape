import sqlite3
class SqliteDB:
    def __init__(self):

        # Create a SQLite database and table
        self.conn = sqlite3.connect('data/data.sqlite3')
        self.cursor = self.conn.cursor()

    def conn_close(self):
        self.conn.close()
        
