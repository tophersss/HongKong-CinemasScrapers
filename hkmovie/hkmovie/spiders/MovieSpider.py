import scrapy
from scrapy import signals
# from hkmovie.hkmovie.items import HkmovieItem
from ..items import HkmovieItem, regex_duration, regex_release_date
from scrapy.loader import ItemLoader
from urllib.parse import urljoin
from w3lib.html import remove_tags
from requests_html import HTMLSession
import re
from datetime import datetime

# ! - crawl command:
# ! - scrapy crawl MovieSpider -O hk-movies.json


def get_movie_links():
    """
    added on 2021-11-17 because original scrapy method (response.css('a.movie.clickable::attr(href)')) failure
    href sometimes do not generate (? - due to loading speed?)
    use requests_html to request hkmovie6.com and render Javascript
    :return: a list of absolute links pointing to hkmovie6/movie page
    """
    _session = HTMLSession()
    _r = _session.get('https://hkmovie6.com/showing')
    _r.html.render(timeout=30)
    _links = [__l for __l in _r.html.absolute_links if 'https://hkmovie6.com/movie' in str(__l)]
    _session.close()
    return _links


if __name__ == "hkmovie.hkmovie.spiders.MovieSpider":
    links = get_movie_links()


class MoviespiderSpider(scrapy.Spider):
    name = 'MovieSpider'
    allowed_domains = ['https://hkmovie6.com/showing']
    start_urls = ['https://hkmovie6.com/showing/']

    def parse(self, response):
        for _link in links:
            yield response.follow(_link, callback=self.parse_info, dont_filter=True)

        # ! - get all movies href and loop
        # original
        # for link in response.css('a.movie.clickable::attr(href)'):
        #     print(f'info_url = {link.get()}')
        #     info_url = urljoin('https://hkmovie6.com', link.get())
        #     if 'hkmovie6.com/movie' in info_url:
        #         print(f"'hkmovie6.com/movie' not in link.get():")
        #         yield response.follow(link.get(), callback=self.parse_info, dont_filter=True)

    def parse_info(self, response):
        item = HkmovieItem()
        l = ItemLoader(item=item, response=response)
        l.add_css('name', 'div.title.movieTitle > h1#banner-movieName::text')
        l.add_css('name_en', 'div.title.movieTitle > h2#banner-movieName-alt')
        l.add_css('rating', 'div.scores > span.rating')
        l.add_css('like', 'div.scores > span:nth-child(3) > span:nth-child(1)')
        l.add_css('comment_count', 'div.scores > span:nth-child(3) > span:nth-child(2)')
        l.add_css('category', 'div.title.movieTitle > div.times.f.row > div.cat')
        l.add_css('synopsis', 'div.synopsis > div > span > span::attr(aria-label)')

        # ! - this element contains concatenated text including info such as duration and release date,
        # ! - these info are to be extracted using Regular Expression
        details = response.css('div.title.movieTitle > div.times.f.row').get()
        l.add_value('duration', regex_duration(remove_tags(details)))
        l.add_value('release_date', regex_release_date(remove_tags(details)))

        # ! - hkmovie6_code is moved to the bottom so it appears as the last field in the output json
        l.add_value('hkmovie6_code', response.request.url)

        yield l.load_item()
