import sqlite3


class DbStorage:
    def __init__(self):
        self.cursor = None
        self.conn = None
        self.file_path = "db_storage.dat"
        self.connect()

    def connect(self):
        self.conn = sqlite3.connect(self.file_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_db()

    def create_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects
            (
                project_id bigint NOT NULL PRIMARY KEY,
                project_name character varying NOT NULL
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS boreholes
            (
                borehole_id bigint NOT NULL PRIMARY KEY,
                borehole_name character varying NOT NULL,
                length numeric,
                depth numeric,
                fissure_inside boolean,
                project_id bigint NOT NULL REFERENCES projects (project_id)
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS files
            (
                file_id bigint NOT NULL PRIMARY KEY,
                file_name character varying NOT NULL,
                borehole_id bigint NOT NULL REFERENCES boreholes (borehole_id),
                part_of_file_id smallint NOT NULL,
                creation_date date,
                data json NOT NULL
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS frequency_characteristics
            (
                borehole_id bigint NOT NULL REFERENCES boreholes (borehole_id),
                file_id bigint NOT NULL REFERENCES files (file_id),
                frequency_characteristic_id integer NOT NULL
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS wind_roses
            (
                borehole_id bigint NOT NULL REFERENCES boreholes (borehole_id),
                file_id bigint NOT NULL REFERENCES files (file_id),
                wind_rose_id integer NOT NULL,
                measurement_id integer NOT NULL
            );
        ''')

        self.conn.commit()