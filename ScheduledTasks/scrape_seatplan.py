import os
import sys
from collections import defaultdict
import time
import concurrent.futures
from hkmovie import SeatplanToolkit
import threading
import sqlite3
from data.db_management import HousesTable, SeatsTable, SalesHistoryTable
from hkmovie.SeatplanFirefoxScraper import SeatplanScraper, Terminator


# =====================================================================================================================|
# =====================================================================================================================|
# {| Chapter III - Scrape Seatplan |}
# Runs 5 times a day to scrape shows in the past 5(?) hours
# Runs 3 times a day to scrape shows that are just added to the database
# assumptions:
#   1) svg <rect> element's fill color to identify  availability of the seat (red = taken, else not taken)
#   2) seats that are marked in red due to social distancing measure are considered taken
#
# flow:
#   1) create three threads and run selenium driver
#   2) scrape show datetime, ticket price, house, seatplan svg
#   3) process seatplan svg using hkmovie\SeatplanToolkit.py SeatplanAnalyzer
#   4) get occupied_seats' info, parse Seat Number (if found), x coordinate (mandatory), y coordinate (mandatory)
#   5) insert results into database
# =====================================================================================================================|
# =====================================================================================================================|


def make_query(sql_query):
    _db = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\hk-movies.db'))
    _conn = sqlite3.connect(_db)
    _cursor = _conn.cursor()

    _cursor.execute(sql_query)
    _results = _cursor.fetchall()
    _conn.commit()
    _conn.close()

    import sys
    print(f'size of unformatted results: {sys.getsizeof(_results)}')

    # ! - format [key-value] pairs to [key - [values]] structure
    # ! - e.g. 'a': a1, 'a': a2 => 'a': [a1, a2]
    _d = defaultdict(list)
    for k, v in _results:
        _d[k].append(v)
    print(f'size of formatted results: {sys.getsizeof(_d)}')
    return _d


def query_unknown_date():
    _query_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, r'data\query_shows_where_date_unknown.sql'))
    with open(_query_path, 'r') as f:
        _query = f.read()

    _results = make_query(_query)
    return _results


def query_last_n_hour(last_n_hour=2):
    _query_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, r'data\query_showtimes_lastnhours.sql'))
    with open(_query_path, 'r') as f:
        _query = f.read()
        _query = _query.replace('@n', str(last_n_hour))

    _results = make_query(_query)
    return _results


def query_adhoc(offset):
    # ! - not in use
    print(f'offset={offset}')
    offset = offset * 2000
    _by_query_path = r'data\query_showtimes_adhoc.sql'
    _by_query_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, _by_query_path))
    with open(_by_query_path, 'r') as f:
        _by_query = f.read()
        _by_query = _by_query.replace('@n', str(offset))

    _final_query = _by_query
    _results = make_query(_final_query)

    return _results


def query_showtimes(top: int = 1500, by=None):
    # ! - not in use
    """
    :param top: number of shows to scan
    :param by: "timeslot" / "house"
    :return:
    """
    # ! - base query: always prioritize shows with unknown date for scanning
    _base_query_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, r'data\query_shows_where_date_unknown.sql'))
    # ! - query option a): movies sorted by popular timeslots
    if str(by).lower() == "timeslot":
        _by_query_path = r'data\query_showtimes_by_timeslot.sql'
    elif str(by).lower() == "house":
        _by_query_path = r'data\query_showtimes_by_house.sql'
    elif str(by).lower() == "last_n_hours":
        _by_query_path = r'data\query_showtimes_lastnhours.sql'
    elif str(by).lower() == "broadyway":
        _by_query_path = r'data\query_showtimes_broadway.sql'

    _by_query_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, _by_query_path))

    with open(_base_query_path, 'r') as f:
        _base_query = f.read()
        _base_query = _base_query.replace('@n', str(top))

    with open(_by_query_path, 'r') as f:
        _by_query = f.read()
        _by_query = _by_query.replace('@n', str(top))

    _final_query = _base_query + '\nUNION ALL\n' + _by_query
    _results = make_query(_final_query)

    return _results


def get_scraper():
    _scraper = getattr(threadLocal, 'scraper', None)
    if _scraper is None:
        # print(f'driver created')
        _scraper = SeatplanScraper(headless=True)
        print(f'\t\tlocal thread has no driver')
        print(f'created new driver: {_scraper.driver.session_id}')
        setattr(threadLocal, 'scraper', _scraper)
        scraper_log.append(_scraper)
    return _scraper


def automate_scrape(hkmovie6_code, showtime_code):
    """
    A wrapper to create threads to scrape seatplan data.

    When a driver in a thread fails, that driver will be removed and re-created,
    the scrape function will then resume
    :param hkmovie6_code:
    :param showtime_code:
    :return: a dictionary containing show info, e.g. movie start time, house, ticket price, seatplan svg
    """
    local_scraper = get_scraper()
    try:
        # raise Exception('intentional Exception raised')
        _profile = local_scraper.scrape(hkmovie6_code, showtime_code)
        return _profile
    except Terminator as terminator:
        print(f'calling SeatplanScraper._tear_down function: driver: {local_scraper.driver.session_id}')
        local_scraper.tear_down()
        scraper_index = [i for i, _s in enumerate(scraper_log)
                         if _s.driver.session_id == local_scraper.driver.session_id][0]

        del scraper_log[scraper_index]

        setattr(threadLocal, 'scraper', None)
        print(f'\t\t==> initiating another scraper for {showtime_code}')
        time.sleep(1)
        return automate_scrape(hkmovie6_code=hkmovie6_code, showtime_code=showtime_code)


def threads_work(content, threader: int = 2):
    # try:
    t0 = time.time()

    _show_container = list()
    # ||| Multi-threading
    with concurrent.futures.ThreadPoolExecutor(max_workers=threader) as executor:
        for _movie in content:
            args = ((_movie, _show) for _show in content[_movie])
            _show_profiles = list(executor.map(lambda p: automate_scrape(*p), args))
            # print(f'_show_profiles:\ttype={type(_show_profiles)}\tlen={len(_show_profiles)}')
            _show_container.extend(_show_profiles)

    _show_container = [__s for __s in _show_container if __s is not None]
            # _showtimes = list(executor.map(automate_scrape, hkmovie6_codes))
    t1 = time.time()
    print(f"Multi-threading: {t1 - t0} seconds to download {len(_show_container)} urls.")

    for _s in scraper_log:
        # print(f'tearing down')
        _s.tear_down()
    return _show_container
    # except Exception as err:
    #     print(f'threads_work() error: {str(err)}')
    #     pass


def export_profile_to_db(_profiles):
    """
    flow:
    1) DROP INDEX SalesHistory_indices to improve INSERT performance
    2) get all Houses' names from profiles and create House record if not exists
    3) UPDATE Showtimes SET start_time, ticket_price
    4) for each show in profiles, do:
    5) UPDATE Houses SET svg, capacity
    6) UPDATE Showtimes SET houseID
    7) INSERT INTO Seats (seat_number, houseID, x, y)
    8) INSERT INTO SalesHistory (seatID)
    9) CREATE INDEX SalesHistory_indices
    :param _profiles:
    :return:
    """
    _db = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'data\hk-movies.db'))
    _conn = sqlite3.connect(_db)
    _cursor = _conn.cursor()

    saleshistory_table = SalesHistoryTable()
    seats_table = SeatsTable()
    houses_table = HousesTable()

    # ! - create tables if not exist
    # try:
    #     _cursor.executescript(saleshistory_table.create_table_statement())
    #     _cursor.executescript(seats_table.create_table_statement())
    #     _cursor.executescript(houses_table.create_table_statement())
    # except Exception as err:
    #     print(f'received error when creating Showtimes table: {str(err)}')

    # ! - print Profile if house is missing
    for _p in _profiles:
        if _p.get('house') is None:
            print('***********************************************\n'
                  '|| Printing problematic profile:')
            for _key in _p.keys():
                if _key != 'seatplan':
                    print(f'{_key}: {_p[_key]}')
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

    # ! - drop index to increase UPDATE/INSERT speed
    _cursor.executescript("DROP INDEX IF EXISTS SalesHistory_indices;")

    # ! - create House records if not exist
    _houses = {_r['house'] for _r in _profiles if _r.get('house') is not None}
    for _h in _houses:
        try:
            _cursor.execute(f"INSERT INTO Houses (name) SELECT :_h "
                            "WHERE NOT EXISTS "
                            f"(SELECT 1 FROM Houses WHERE name = :_h)", {"_h": _h})
        except Exception as err:
            print(f'received error when inserting record ({_h}) to Houses table: {repr(err)}')


    # ! - update Showtimes.start_time, price
    _cursor.executemany("UPDATE Showtimes SET start_time = :start_time, price = :price"
                        " WHERE showtime_code = :showtime_code", _profiles)

    for _show in _profiles:
        _sp = SeatplanToolkit.SeatplanProcessor(_show["seatplan"])

        _op = _sp.get_occupied_seats()

        _op = list(_op)

        _house_id = int(_cursor.execute('SELECT HouseID FROM Houses WHERE name = ?', [_show['house']]).fetchone()[0])

        _cursor.execute(
            f"UPDATE Houses SET svg = ?, capacity = ? WHERE HouseID = {_house_id};",
            [_sp.export_clean_svg(), _sp.get_house_capacity()]
        )

        _cursor.executemany("INSERT INTO Seats (seat_number, HouseID, x, y) "
                            f"SELECT :seat_number, {_house_id}, :x, :y "
                            f"WHERE NOT EXISTS"
                            f" (SELECT 1 FROM Seats"
                            f" WHERE Seats.x = :x AND Seats.y = :y AND Seats.HouseID = {_house_id})", list(_op))

        _showtime_id = int(_cursor.execute('SELECT ShowtimeID FROM Showtimes WHERE showtime_code = ?',
                                           [_show['showtime_code']]).fetchone()[0])

        _cursor.execute(f"UPDATE Showtimes SET HouseID = {_house_id} WHERE ShowtimeID = {_showtime_id};")

        try:
            _cursor.executemany("INSERT OR IGNORE INTO SalesHistory (SeatID, ShowtimeID) "
                                f"SELECT SeatID, {_showtime_id} FROM Seats WHERE seat_number = :seat_number"
                                f" AND x = :x AND y = :y"
                                f" AND HouseID = {_house_id}", list(_op))
        except Exception as err:
            print(f'received error when inserting record to SalesHistory table: {str(err)}')


    _cursor.executescript("CREATE INDEX IF NOT EXISTS SalesHistory_indices ON SalesHistory (ShowtimeID);")

    _conn.commit()
    _conn.close()

    return True


if __name__ == "__main__":
    # ! - query_by accepts: "last_n_hour", "unknown_date"
    print(f'Begin: {time.ctime(time.time())}\n******************************************')
    try:
        query_by = sys.argv[1]
    except IndexError:
        query_by = "last_n_hour"

    if query_by == "last_n_hour":
        results = query_last_n_hour(last_n_hour=5)
    elif query_by == "unknown_date":
        results = query_unknown_date()
    else:
        results = query_showtimes(top=1000, by="timeslot")

    if results is not None and len(results) > 0:
        threadLocal = threading.local()
        scraper_log = []

        # ! - starts mutli-threads scraping
        shows = threads_work(results, 3)
        export_profile_to_db(_profiles=shows)

    print(f'******************************************\nEnd: {time.ctime(time.time())}')
