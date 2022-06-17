# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy.loader import ItemLoader
from itemloaders.processors import TakeFirst, MapCompose
from w3lib.html import remove_tags
import re


def extract_hkmovie6_code(url):
    """
    extract unique hkmovie6 code assigned by hkmovie6.com to the movie from the url
    this function expects the url to always be https://hkmovie6.com/movie/UNIQUE_HKMOVIE6_CODE

    hkmovie6_code is used as the name instead of id, movie_id, etc. because the latter are reserved to be the
    primary key of the movie for the database.
    :param url: as parsed from response.request.url
    :return: unique hkmovie6_code
    """
    hkmovie6_code = str(url).replace("https://hkmovie6.com/movie/", "")
    return hkmovie6_code


def zero_rating(text):
    """
    replace rating "– –", aka films that have yet published, with "-1"
    :param text: extracted from div.ratingText
    :return: always return -1.0; float is the expected data type of rating
    """
    return "-1" if text == "- -" else text


def strip_text(text):
    return str(text).strip()


def regex_release_date(text):
    date_search = re.search('(20[0-9]{2})年([0-1]?[0-9])月([0-3]?[0-9])日', text)
    if date_search:
        yyyy = date_search.group(1)
        mm = str(date_search.group(2)).zfill(2)
        dd = str(date_search.group(3)).zfill(2)
        date = f'{yyyy}-{mm}-{dd}'
    else:
        date = None
    return date


def regex_duration(text):
    duration_search = re.search('([0-9]{1,3}) ?分鐘', text)
    if duration_search:
        minute = duration_search.group(1).strip()
    else:
        minute = "0"
    return minute


class HkmovieItem(scrapy.Item):
    """
    One must ensure the field names used below are same as those in SQLite Tables
    """
    hkmovie6_code = scrapy.Field(input_processor=MapCompose(extract_hkmovie6_code), output_processor=TakeFirst())
    name = scrapy.Field(input_processor=MapCompose(remove_tags, strip_text), output_processor=TakeFirst())
    name_en = scrapy.Field(input_processor=MapCompose(remove_tags, strip_text), output_processor=TakeFirst())
    synopsis = scrapy.Field(input_processor=MapCompose(remove_tags, strip_text), output_processor=TakeFirst())
    rating = scrapy.Field(input_processor=MapCompose(remove_tags, strip_text, zero_rating),
                          output_processor=TakeFirst())
    like = scrapy.Field(input_processor=MapCompose(remove_tags, strip_text), output_processor=TakeFirst())
    comment_count = scrapy.Field(input_processor=MapCompose(remove_tags, strip_text), output_processor=TakeFirst())
    release_date = scrapy.Field(input_processor=MapCompose(strip_text), output_processor=TakeFirst())
    duration = scrapy.Field(input_processor=MapCompose(strip_text), output_processor=TakeFirst())
    category = scrapy.Field(input_processor=MapCompose(remove_tags, strip_text), output_processor=TakeFirst())


class SeatplanItem(scrapy.Item):
    hkmovie6_code = scrapy.Field(input_processor=MapCompose(extract_hkmovie6_code), output_processor=TakeFirst())
    show_date = scrapy.Field()
    show_hour = scrapy.Field()
    price = scrapy.Field()