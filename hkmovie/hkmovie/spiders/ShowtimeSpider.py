# import scrapy
# from ..items import SeatplanItem, regex_duration, regex_release_date
# from scrapy.loader import ItemLoader
# from scrapy.linkextractors import LinkExtractor
# from scrapy.spiders import CrawlSpider, Rule
# from urllib.parse import urljoin


# class ShowtimespiderSpider(scrapy.Spider):
#     name = 'ShowtimeSpider'
#     allowed_domains = ['https://hkmovie6.com/movie']
#
#     # rules = (
#     #     Rule(LinkExtractor(allow=r'Items/'), callback='parse_item', follow=True),
#     # )
#
#     def parse(self, response):
#         item = SeatplanItem()
#         l = ItemLoader(item=item, response=response)
#
#         l.add_css('?', 'svg.seatplan.seatplan')
#
#         yield l.load_item()
#
#         # div.text.dispMobile

# from requests_html import HTMLSession, HTMLResponse
#
# session = HTMLSession()
# url = 'https://hkmovie6.com/movie/fb874e20-26af-41a9-a71c-ca55575de71a/showtime/3f166a44-c2bc-45aa-9e09-f3f0481c33c6'
#
# r = session.get(url)
# r.html.render(sleep=1, keep_page=True)
#
# seatplan = r.html.find('div.seatplanWrapper > svg')
#
# print(seatplan)


