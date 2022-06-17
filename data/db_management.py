import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
import os


# todo: https://www.sqlite.org/draft/lang_UPSERT.html
def create_tables_and_views():
    _schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\schema.sql'))
    # print(f'_path = {_path}')
    with open(_schema_path, 'r') as f:
        _create_script = f.read()

    _db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\hk-movies.db'))
    _conn = sqlite3.connect(_db_path)
    _cursor = _conn.cursor()
    _cursor.executescript(_create_script)
    _conn.commit()
    _conn.close()
    return True


def export_schema_from_db():
    _db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\hk-movies.db'))
    _schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\schema.sql'))
    _conn = sqlite3.connect(_db_path)
    _cursor = _conn.cursor()
    _query = "select sql from sqlite_master where sql is not null;"
    _cursor.execute(_query)
    _results = _cursor.fetchall()
    # print(_results)
    _conn.commit()
    _conn.close()

    with open(_schema_path, 'w+') as f:
        for _r in _results:
            _statement = str(_r[0]).replace('CREATE TABLE', 'CREATE TABLE IF NOT EXISTS')\
                .replace('CREATE INDEX', 'CREATE INDEX IF NOT EXISTS') \
                .replace('CREATE TRIGGER', 'CREATE TRIGGER IF NOT EXISTS') \
                .replace('CREATE VIEW', 'CREATE VIEW IF NOT EXISTS') + ';\n'
            f.write(_statement)

    print(f'Schema has successfully exported to a sql file.\n{_statement}')

    return


# def query_time_unknown_shows(limit:int = 2000):


class SQLiteTableModel(ABC):
    # def __init__(self):
    #     self.table_name = ""
    #     self.primary_key = ""
    @property
    @abstractmethod
    def table_name(self):
        """return table name"""

    @property
    @abstractmethod
    def primary_key(self):
        """return primary key of the table"""

    @property
    @abstractmethod
    def columns(self):
        """
            return a list of column_name-data_type-nullable pair dictionaries
            example: [
                {"column_name": "MovieID", "dtype": "integer", "primary_key": True},
                {"column_name": "hkmovie6_code", "dtype": "text", "nullable": False},
                {"column_name": "name", "dtype": "text"}
            ]

            only FIVE data types ar allowed: NULL, INTEGER, REAL, TEXT, BLOB
            read more: https://www.sqlite.org/datatype3.html
        """

    def generate_column_dtype_string(self):
        """
        join a list of column_name-data_type pair dictionaries with ", "
        to pass to create table sql statement for create_table function
        :return:
        """
        formatted_columns = ", ".join(
            [col['column_name'] + " " + col['dtype'] +
             str(" NOT NULL" if col.get('nullable') is False else "") +
             str(" UNIQUE" if col.get('unique') is True else "") +
             str(" DEFAULT " + str(col.get('default')) if col.get('default') is not None else "") +
             str(" PRIMARY KEY" if col.get('primary_key') is True else "") for col in self.columns]
        )
        return formatted_columns

    def create_table_statement(self):
        name_dtype_pairs = self.generate_column_dtype_string()
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS {table} ( {formatted_columns} )
        """.format(table=self.table_name, formatted_columns=name_dtype_pairs).strip()
        return create_table_sql

    def digest_scrapy_items(self, scrapy_items: list):
        """
        this function only has to be called ONCE per scrapy item class for each crawl

        read more: https://stackoverflow.com/questions/53963028/how-to-insert-multiple-rows-from-a-python-nested-dictionary-to-a-sqlite-db
        :param scrapy_items:
        :return:
        """
        for item in scrapy_items:
            sql_dict = dict()
            for col in self.columns:
                col_name = col['column_name']
                if col.get('primary_key') is None:
                    sql_dict[col_name] = item.get(col_name)
                if col_name == 'EnteredDate':
                    sql_dict[col_name] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                elif col_name == 'ModifiedDate':
                    sql_dict[col_name] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            yield sql_dict


class MoviesTable(SQLiteTableModel):
    @property
    def table_name(self):
        return "Movies"

    @property
    def primary_key(self):
        return "MovieID"

    @property
    def columns(self):
        """
            return a list of column_name-data_type-nullable pair dictionaries
            example: [
                {"column_name": "MovieID", "dtype": "integer", "primary_key": True},
                {"column_name": "hkmovie6_code", "dtype": "text", "nullable": False},
                {"column_name": "name", "dtype": "text"}
            ]

            only FIVE data types ar allowed: NULL, INTEGER, REAL, TEXT, BLOB
            read more: https://www.sqlite.org/datatype3.html

            !!IMPORTANT: One must ensure the field names used below are same as those in Scrapy items
        """
        return [
            {"column_name": "MovieID",          "dtype": "integer", "primary_key": True},
            {"column_name": "hkmovie6_code",    "dtype": "text", "unique": True, "nullable": False},
            {"column_name": "name",             "dtype": "text", "nullable": False},
            {"column_name": "name_en",          "dtype": "text"},
            {"column_name": "synopsis",         "dtype": "text"},
            {"column_name": "release_date",     "dtype": "text"},
            {"column_name": "duration",         "dtype": "integer"},
            {"column_name": "category",         "dtype": "text"},
            {"column_name": "InTheatre",        "dtype": "integer", "nullable": False},
            {"column_name": "ModifiedDate",     "dtype": "integer(4)",
                                                "default": "(strftime('%s','now'))", "nullable": False},
            {"column_name": "EnteredDate",      "dtype": "integer(4)", "default": "(strftime('%s','now'))",
                                                "nullable": False}
        ]

    def insert_statement(self):
        """
        read more: https://stackoverflow.com/questions/53963028/how-to-insert-multiple-rows-from-a-python-nested-dictionary-to-a-sqlite-db
        read more: https://docs.python.org/3/library/sqlite3.html#sqlite3-placeholders
        :param scrapy_item:
        :return:
        """
        insert_sql = """
            INSERT INTO {table} ( 
                hkmovie6_code, name, name_en, synopsis, release_date, duration, 
                category, InTheatre
            ) VALUES ( :hkmovie6_code, :name, :name_en, :synopsis, :release_date, :duration, 
            :category, :InTheatre )
            ON CONFLICT ( hkmovie6_code )
            DO UPDATE SET name = :name, name_en = :name_en, synopsis = :synopsis, release_date = :release_date, 
                duration = :duration, category = :category, InTheatre = 1, ModifiedDate = (strftime('%s','now'))
        """.format(table=self.table_name).strip().replace('\n', '')
        return insert_sql

    def reset_InTheatre(self):
        """
        During the execution of scrape_hkmovie6_code,
        all movies will be set InTheatre = 0,
        then only the movies that appear in scrape_hkmovie6_code result will be set to InTheatre = 1 .
        :return:
        """
        sql = "UPDATE Movies SET InTheatre = 0"
        return sql


class ReactionsTable(SQLiteTableModel):
    @property
    def table_name(self):
        return "Reactions"

    @property
    def primary_key(self):
        return "ReactionID"

    @property
    def columns(self):
        """
            return a list of column_name-data_type-nullable pair dictionaries
            example: [
                {"column_name": "MovieID", "dtype": "integer", "primary_key": True},
                {"column_name": "hkmovie6_code", "dtype": "text", "nullable": False},
                {"column_name": "name", "dtype": "text"}
            ]

            only FIVE data types ar allowed: NULL, INTEGER, REAL, TEXT, BLOB
            read more: https://www.sqlite.org/datatype3.html

            !!IMPORTANT: One must ensure the field names used below are same as those in Scrapy items
        """
        return [
            {"column_name": "ReactionID",       "dtype": "integer", "primary_key": True},
            {"column_name": "rating",           "dtype": "integer"},
            {"column_name": "like",             "dtype": "integer"},
            {"column_name": "comment_count",    "dtype": "integer"},
            {"column_name": "MovieID",          "dtype": "integer", "nullable": False},
            {"column_name": "EnteredDate",      "dtype": "integer(4)", "default": "(strftime('%s','now'))",
                                                "nullable": False}
        ]

    def insert_statement(self):
        insert_sql = """
            INSERT INTO {table} ( rating, like, comment_count, MovieID ) 
            SELECT :rating, :like, :comment_count, Movies.MovieID
            FROM Movies WHERE Movies.hkmovie6_code = :hkmovie6_code
        """.format(table=self.table_name).strip().replace('\n', '')
        return insert_sql


class HousesTable(SQLiteTableModel):
    @property
    def table_name(self):
        return "Houses"

    @property
    def primary_key(self):
        return "HouseID"

    @property
    def columns(self):
        """
            HouseID will not be supplied until Seatplan is scraped
            as this information is not present in
        """
        return [
            {"column_name": "HouseID",          "dtype": "integer", "primary_key": True},
            {"column_name": "name",             "dtype": "text", "nullable": False},
            {"column_name": "TheatreID",        "dtype": "integer"},
            {"column_name": "EnteredDate",      "dtype": "integer(4)", "default": "(strftime('%s','now'))",
                                                "nullable": False}
        ]

    def insert_statement(self):
        insert_sql = """
            INSERT INTO {table} ( name, TheatreID ) 
            SELECT :name, Theatres.TheatreID
            FROM Theatres WHERE Theatres.name = :theatre_name
        """.format(table=self.table_name).strip().replace('\n', '')
        return insert_sql


class ShowtimesTable(SQLiteTableModel):
    @property
    def table_name(self):
        return "Showtimes"

    @property
    def primary_key(self):
        return "ShowtimeID"

    @property
    def columns(self):
        """
            HouseID will not be supplied until Seatplan is scraped
            as this information is not present in
        """
        return [
            {"column_name": "ShowtimeID",       "dtype": "integer", "primary_key": True},
            {"column_name": "showtime_code",    "dtype": "text", "unique": True, "nullable": False},
            {"column_name": "price",            "dtype": "integer"},
            {"column_name": "HouseID",          "dtype": "integer"},
            {"column_name": "MovieID",          "dtype": "integer", "nullable": False},
            {"column_name": "start_time",       "dtype": "integer(4)"},
            {"column_name": "EnteredDate",      "dtype": "integer(4)", "default": "(strftime('%s','now'))",
                                                "nullable": False}
        ]

    def insert_statement(self):
        insert_sql = """
            INSERT INTO {table} ( showtime_code, MovieID, start_time ) 
            SELECT :showtime_code, Movies.MovieID. :start_time
            FROM Movies WHERE Movies.hkmovie6_code = :hkmovie6_code
        """.format(table=self.table_name).strip().replace('\n', '')
        return insert_sql


class SalesHistoryTable(SQLiteTableModel):
    @property
    def table_name(self):
        return "SalesHistory"

    @property
    def primary_key(self):
        return "ID"

    @property
    def columns(self):
        """
            return a list of column_name-data_type-nullable pair dictionaries
            example: [
                {"column_name": "MovieID", "dtype": "integer", "primary_key": True},
                {"column_name": "hkmovie6_code", "dtype": "text", "nullable": False},
                {"column_name": "name", "dtype": "text"}
            ]

            only FIVE data types ar allowed: NULL, INTEGER, REAL, TEXT, BLOB
            read more: https://www.sqlite.org/datatype3.html

            !!IMPORTANT: One must ensure the field names used below are same as those in Scrapy items
        """
        return [
            {"column_name": "ID",               "dtype": "integer", "primary_key": True},
            {"column_name": "SeatID",           "dtype": "integer"},
            {"column_name": "ShowtimeID",       "dtype": "integer"},
            {"column_name": "EnteredDate",      "dtype": "integer(4)", "default": "(strftime('%s','now'))",
                                                "nullable": False}
        ]

    def insert_statement(self):
        insert_sql = """
            INSERT INTO {table} ( rating, like, comment_count, MovieID ) 
            SELECT :rating, :like, :comment_count, Movies.MovieID
            FROM Movies WHERE Movies.hkmovie6_code = :hkmovie6_code
        """.format(table=self.table_name).strip().replace('\n', '')
        return insert_sql


class SeatsTable(SQLiteTableModel):
    @property
    def table_name(self):
        return "Seats"

    @property
    def primary_key(self):
        return "SeatID"

    @property
    def columns(self):
        """
            return a list of column_name-data_type-nullable pair dictionaries
            example: [
                {"column_name": "MovieID", "dtype": "integer", "primary_key": True},
                {"column_name": "hkmovie6_code", "dtype": "text", "nullable": False},
                {"column_name": "name", "dtype": "text"}
            ]

            only FIVE data types ar allowed: NULL, INTEGER, REAL, TEXT, BLOB
            read more: https://www.sqlite.org/datatype3.html

            !!IMPORTANT: One must ensure the field names used below are same as those in Scrapy items
        """
        return [
            {"column_name": "SeatID",           "dtype": "integer", "primary_key": True},
            {"column_name": "seat_number",      "dtype": "text"},
            {"column_name": "HouseID",          "dtype": "integer"},
            {"column_name": "EnteredDate",      "dtype": "integer(4)", "default": "(strftime('%s','now'))",
                                                "nullable": False}
        ]

    def insert_statement(self):
        """
        read more: https://stackoverflow.com/questions/53963028/how-to-insert-multiple-rows-from-a-python-nested-dictionary-to-a-sqlite-db
        read more: https://docs.python.org/3/library/sqlite3.html#sqlite3-placeholders
        :param scrapy_item:
        :return:
        """
        insert_sql = """
            INSERT INTO Seats ( seat_number, HouseID, x, y ) 
            SELECT :seat_number, {_house_id}, :x, :y
            WHERE NOT EXISTS (
                SELECT 1 FROM Seats WHERE Seats.x = :x AND Seats.y = :y AND Seats.HouseID = {_house_id}) 
            )  
            ON CONFLICT ( hkmovie6_code )
            DO UPDATE SET name = :name, name_en = :name_en, synopsis = :synopsis, release_date = :release_date, 
                duration = :duration, category = :category, InTheatre = 1, ModifiedDate = (strftime('%s','now'))
        """.format(_house_id=self.table_name).strip().replace('\n', '')
        return insert_sql


class TheatresTable(SQLiteTableModel):
    @property
    def table_name(self):
        return "Theatres"

    @property
    def primary_key(self):
        return "TheatreID"

    @property
    def columns(self):
        """
            return a list of column_name-data_type-nullable pair dictionaries
            example: [
                {"column_name": "MovieID", "dtype": "integer", "primary_key": True},
                {"column_name": "hkmovie6_code", "dtype": "text", "nullable": False},
                {"column_name": "name", "dtype": "text"}
            ]

            only FIVE data types ar allowed: NULL, INTEGER, REAL, TEXT, BLOB
            read more: https://www.sqlite.org/datatype3.html

            !!IMPORTANT: One must ensure the field names used below are same as those in Scrapy items
        """
        return [
            {"column_name": "TheatreID",        "dtype": "integer", "primary_key": True},
            {"column_name": "name",             "dtype": "text", "unique": True},
            {"column_name": "EnteredDate",      "dtype": "integer(4)", "default": "(strftime('%s','now'))",
                                                "nullable": False}
        ]


if __name__ == "__main__":
    export_schema_from_db()
else:
    create_tables_and_views()
