# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.exporters import JsonItemExporter

import os
import sqlite3
import data.db_management
from data.db_management import MoviesTable, ReactionsTable


class HkmoviePipeline:
    def __init__(self):
        self.movie_items = list()
        self.reaction_items = list()
        self.scrapy_items = list()

        # ! - set up connection
        _db = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, r'data\hk-movies.db'))
        self.conn = sqlite3.connect(_db)
        self.cursor = self.conn.cursor()

    def insert_to_database(self):
        # ! - set up SQLite table objects for standardization and consistency
        movies_table = MoviesTable()
        reactions_table = ReactionsTable()

        # ! - 2022-05-26: obsolete (replaced by db_management.create_tables_and_views())
        # ! - create tables if not exist
        # try:
        #     self.cursor.executescript(movies_table.create_table_statement())
        # except Exception as err:
        #     print(f'received error when creating Movies table: {str(err)}')
        #
        # try:
        #     self.cursor.executescript(reactions_table.create_table_statement())
        # except Exception as err:
        #     print(f'received error when creating Reactions table: {str(err)}')

        # ! - make sure only the movies appear in this scrape are marked as "InTheatre"
        try:
            self.cursor.executescript(movies_table.reset_InTheatre())
        except Exception as err:
            print(f'received error when resetting InTheatre: {str(err)}')

        # ! - generate insert scripts
        movies_insert_sql = movies_table.insert_statement()
        reactions_insert_sql = reactions_table.insert_statement()

        # ! - insert results into database
        try:
            self.cursor.executemany(movies_insert_sql, self.scrapy_items)
        except Exception as err:
            print(f'received error when inserting movies items: {str(err)}')

        try:
            self.cursor.executemany(reactions_insert_sql, self.scrapy_items)
        except Exception as err:
            print(f'received error when inserting reactions items: {str(err)}')

    def process_item(self, item, spider):
        # current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # || Movies table INSERT fields
        # > hkmovie6_code, name, name_en, synopsis, release_date, duration, category, InTheatre, EnteredDate
        # movie_item = {
        #     'hkmovie6_code': item['hkmovie6_code'],
        #     'name': item['name'],
        #     'name_en': item.get('name_en', None),
        #     'synopsis': item.get('synopsis', None),
        #     'release_date': item['release_date'],
        #     'duration': item['duration'],
        #     'category': item['category'],
        #     'InTheatre': 1,     # 'InTheatre': 1 if item['release_date'] < current_time else 0,
        #     'EnteredDate': current_time
        # }
        # || Reactions table INSERT fields
        # > rating, like, comment_count, hkmovie6_code, EnteredDate
        # reaction_item = {
        #     'rating': item.get('rating', None),
        #     'like': item.get('like', None),
        #     'comment_count': item.get('comment_count', None),
        #     'hkmovie6_code': item['hkmovie6_code'],
        #     'EnteredDate': current_time
        # }

        scrapy_item = {
            # || Movies table
            'hkmovie6_code': item['hkmovie6_code'],
            'name': item['name'],
            'name_en': item.get('name_en', None),
            'synopsis': item.get('synopsis', None),
            'release_date': item['release_date'],
            'duration': item['duration'],
            'category': item['category'],
            'InTheatre': 1,  # 'InTheatre': 1 if item['release_date'] < current_time else 0,
            # || Reactions table
            'rating': item.get('rating', None),
            'like': item.get('like', None),
            'comment_count': item.get('comment_count', None),
            # 'EnteredDate': current_time
        }

        # self.movie_items.append(movie_item)
        # self.reaction_items.append(reaction_item)
        self.scrapy_items.append(scrapy_item)
        return item

    def close_spider(self, spider):
        self.insert_to_database()
        self.conn.commit()
        self.conn.close()
