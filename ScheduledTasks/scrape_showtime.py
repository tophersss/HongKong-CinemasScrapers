import os
import sqlite3
import orjson
import time
import concurrent.futures
import threading
from urllib.parse import urljoin
from data.db_management import ShowtimesTable
# from hkmovie.ShowtimeScraper import ShowtimeScraper
from hkmovie.ShowtimeFirefoxScraper import ShowtimeScraper

# =====================================================================================================================|
# =====================================================================================================================|
# {| Chapter II - Scrape Movie Showtimes in Theatre |}
# Runs at 10:15am, 08:15pm
# flow:
#   1) select top 20 movies with at least 50 likes
#   2) create three threads and run selenium-wire driver
#   3) go to https://hkmovie6.com/movie/{hkmovie6_code}/showtime
#   4) navigate through all the showing dates (simulate button click event)
#   5) read driver.requests.response.body and extract showtime_code using regular expression
# =====================================================================================================================|
# =====================================================================================================================|


def get_target_movies(minimum_like: int = 50, top: int = 15):
    _db = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\hk-movies.db'))
    _conn = sqlite3.connect(_db)
    _cursor = _conn.cursor()
    try:
        _cursor.execute("SELECT hkmovie6_code FROM vLatestReactions "
                        "WHERE InTheatre = 1 AND Like > (:like) "
                        "ORDER BY like DESC LIMIT (:top)",
                        {"like": minimum_like, "top": top})
        _results = _cursor.fetchall()
        _codes = list()
        for __row in _results:
            for __code in __row:
                _codes.append(__code)
        return _codes
    except Exception as err:
        print(f'error when getting MovieID from LatestReactions: {str(err)}')
    finally:
        _conn.close()


def get_scraper():
    _scraper = getattr(threadLocal, 'scraper', None)
    if _scraper is None:
        # print(f'driver created')
        _scraper = ShowtimeScraper(headless=True)
        setattr(threadLocal, 'scraper', _scraper)
        scraper_log.append(_scraper)
    return _scraper


def automate_scrape(hkmovie6_code):
    local_scraper = get_scraper()
    try:
        secret_codes = local_scraper.scrape(hkmovie6_code)
        local_scraper.shuffle_user_agent()
        return secret_codes
    except Exception as err:
        print(f'-automate_scrape error: {str(err)}')
        local_scraper.tear_down()
        print('local scraper tore down')
        scraper_index = [i for i, _s in enumerate(scraper_log)
                         if _s.driver.session_id == local_scraper.driver.session_id][0]

        del scraper_log[scraper_index]

        setattr(threadLocal, 'scraper', None)
        time.sleep(1)
        return automate_scrape(hkmovie6_code=hkmovie6_code)


def threads_work(hkmovie6_codes, threader: int = 2):
    t0 = time.time()

    # ||| Multi-threading
    with concurrent.futures.ThreadPoolExecutor(max_workers=threader) as executor:
        _showtimes = list(executor.map(automate_scrape, hkmovie6_codes))
    t1 = time.time()
    print(f"Multi-threading: {t1 - t0} seconds to download {len(hkmovie6_codes)} urls.")

    for s in scraper_log:
        s.tear_down()
    return _showtimes


def export_showtime_to_db(results):
    _db = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\hk-movies.db'))
    _conn = sqlite3.connect(_db)
    _cursor = _conn.cursor()

    showtimes_table = ShowtimesTable()

    # ! - create tables if not exist
    try:
        _cursor.executescript(showtimes_table.create_table_statement())
    except Exception as err:
        print(f'received error when creating Showtimes table: {str(err)}')

    for _movie in results:
        _hkmovie6_code = _movie["movie_code"]
        _showtime_codes = [{'showtime_code': _code} for _code in _movie["secret_codes"]]
        _insert_sql = """
                INSERT INTO Showtimes ( showtime_code, MovieID ) 
                SELECT :showtime_code, Movies.MovieID
                FROM Movies WHERE Movies.hkmovie6_code = '{movie_code}'
                AND NOT EXISTS 
                (SELECT 1 FROM Showtimes WHERE showtime_code = :showtime_code)
            """.format(movie_code=_hkmovie6_code).strip().replace('\n', '')
        try:
            print(f'insert sql: {_insert_sql}')
            _cursor.executemany(_insert_sql, _showtime_codes)
        except Exception as err:
            print(f'received error when inserting into Showtimes table: {str(err)}')

    _conn.commit()
    _conn.close()

    return True


if __name__ == "__main__":
    target_movies = get_target_movies(minimum_like=50, top=20)
    if target_movies is not None and len(target_movies) > 0:
        threadLocal = threading.local()
        scraper_log = []

        showtimes = threads_work(target_movies, 3)
        showtimes = [s for s in showtimes if s is not None]

        export_showtime_to_db(results=showtimes)
