from scrapy.crawler import CrawlerProcess
from fake_useragent import UserAgent
from hkmovie.hkmovie.spiders import MovieSpider

# =====================================================================================================================|
# =====================================================================================================================|
# {| Chapter I - Scrape Movie Codes |}
# Runs at 10am, 6pm, 2am everyday
# flow:
#   1) create HTML session of https://hkmovie6.com/showing
#   2) render JavaScript for movie card elements using requests_html library
#   3) get all hyperlinks that starts with https://hkmovie6.com/movie
#       then goes to the movie profile page one by one
#   4) extract and insert movie info into Movies, Reactions tables
#       see details in hkmovie\hkmovie\spiders\MovieSpider.py > parse_info()
# =====================================================================================================================|
# =====================================================================================================================|


def spider_crawl(spider):
    ua = UserAgent()
    p = CrawlerProcess(settings={
        "BOT_NAME": "hkmovie",
        "SPIDER_MODULES": ["hkmovie.hkmovie.spiders"],
        "NEWSPIDER_MODULE": "hkmovie.hkmovie.spiders",
        "FEED_EXPORT_ENCODING": "utf-8",
        "USER_AGENT": ua.random,
        "ROBOTSTXT_OBEY": False,
        "ITEM_PIPELINES": {'hkmovie.hkmovie.pipelines.HkmoviePipeline': 300}
    })
    p.crawl(spider)
    p.start()
    return True


if __name__ == '__main__':
    spider_crawl(spider=MovieSpider.MoviespiderSpider)
