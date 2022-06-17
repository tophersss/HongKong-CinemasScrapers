import os
from seleniumwire import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from fake_useragent import UserAgent
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
import random
import orjson
import re
import time
from tenacity import retry, retry_if_exception_type, stop_after_attempt, RetryError, wait_random

# ! - todo: https://medium.com/c%C3%B3digo-ecuador/python-multithreading-vs-multiprocessing-web-scrape-stock-price-history-faster-b72827601cf6
# ! - todo: https://medium.com/drunk-wis/python-selenium-webdriver-page-object-model-design-pattern-%E7%9A%84%E4%B8%80%E4%BA%9B%E6%83%B3%E6%B3%95-6d8cc0e156a6


class NoButtonError(Exception):
    """raised when no button is found, which implies either TimeOut or movie being unavailable"""
    pass


class Terminator(Exception):
    """this terminates your function. use when a final wrap-up is needed"""
    pass


class ShowtimeScraper:
    def __init__(self, headless=True):
        self._setup(headless)
        self.hkmovie6_code = None
        self.secret_codes = None
        self.received_response_ts = list()
        self.num_of_resp = 0

    def _setup(self, headless):
        _firefox_options = webdriver.FirefoxOptions()
        _firefox_profile = FirefoxProfile()
        _ua = UserAgent()
        _firefox_profile.set_preference("general.useragent.override", _ua.random)
        if headless:
            _firefox_options.add_argument('--headless')

        _driver_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, r'plug-ins\geckodriver.exe'))
        _service_log_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, r'plug-ins\geckodriver.log'))

        self.driver = webdriver.Firefox(
            executable_path=_driver_path,
            options=_firefox_options,
            firefox_profile=_firefox_profile,
            service_log_path=_service_log_path
        )
        self.driver.set_page_load_timeout(20)
        return True

    def scrape(self, hkmovie6_code):
        try:
            self.num_of_resp = 0
            self.hkmovie6_code = hkmovie6_code
            _url = self._generate_url()
            _time0 = time.time()
            try:
                self._load_url(_url)
            except RetryError:
                raise Terminator(f'failed to load {_url} after 3 retries')
            _time1 = time.time()
            try:
                date_btns = self._find_date_buttons()
            except RetryError:
                raise Terminator(f'failed to find buttons on {_url} after 3 retries')
            except NoButtonError:
                raise Terminator(f'failed to find buttons on {_url} as movie is not showing in theatre')
            _time2 = time.time()
            if date_btns is not None:
                for btn in date_btns:
                    self._click(btn)
            # ! - wait for request.response
            time.sleep(2)
            try:
                secret_codes = self._fetch_secret_response()
            except Exception as err:
                raise Terminator(f'ShowtimeScraper.scrape(): {_url}: {repr(err)}')
            else:
                self.secret_codes = secret_codes
                return {'movie_code': self.hkmovie6_code, 'secret_codes': list(self.secret_codes)}
        except Terminator:
            print(repr(Terminator))
        finally:
            if self.num_of_resp > 0:
                print(
                    f'|| Scraped {self.num_of_resp} responses on {_url}')
                print('...')
            del self.driver.requests
            print(f'responses deleted for {self.hkmovie6_code}')

    def _generate_url(self):
        # ! - Expect the url structure to be always the same
        _url = f'https://hkmovie6.com/movie/{self.hkmovie6_code}/SHOWTIME'
        return _url

    @retry(retry=retry_if_exception_type(TimeoutException), stop=stop_after_attempt(3), wait=wait_random(min=3, max=5))
    def _load_url(self, url):
        self.driver.get(url)

    @retry(retry=retry_if_exception_type(TimeoutException), stop=stop_after_attempt(2), wait=wait_random(min=1, max=2))
    def _find_date_buttons(self):
        try:
            _all_btns = WebDriverWait(self.driver, 5).until(
                ec.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    "div.showDates > div.swiper-container-horizontal > div.swiper-wrapper > div.swiper-slide.dateCell"))
            )
        except TimeoutException:
            print(f'timed out when finding date buttons')
        else:
            if len(_all_btns) == 0:
                # ! - error, or movie will not be showing in Theatre
                raise NoButtonError('Movie is not showing in theaters')
            elif len(_all_btns) == 1:
                # ! - if button is default active date, return
                return None
            else:
                # ! - return 2nd to last buttons, as the 1st button (default active date) needs not be clicked
                return _all_btns[1:]

    def _click(self, element):
        try:
            # ! - click using JavaScript, as element.click() cannot bypass overlay element
            self.driver.execute_script("arguments[0].click();", element)
            time.sleep(random.randint(0, 3))
            return True
        except Exception as err:
            print(f'SecretResponseScraper.click(): An error occurred on https://hkmovie6.com/movie/{self.hkmovie6_code}/SHOWTIME: {str(err)}')

    def _fetch_secret_response(self):
        try:
            for request in self.driver.requests:
                # print(f'url: {request.url}\tcontent-length: {request.response.headers["content-length"]}\tdate: {request.response.headers["date"]}')
                # print(f'CONCAT_KEYS = {str(request.response.headers["content-length"]) + "_" + request.response.headers["date"]}')
                if request.response:
                    if request.response.headers['content-type']:
                        if 'grpc' in request.response.headers['content-type']:
                            # print(f'QUALIFIED: url: {request.url}\tcontent-length: {request.response.headers["content-length"]}\tdate: {request.response.headers["date"]}')
                            # print('=====================================================')
                            secret_codes = self._regex_showtime_code(request.response.body.decode('latin-1'))
                            self.num_of_resp += 1
                            if secret_codes:
                                yield from secret_codes
                            else:
                                pass
        except Exception as err:
            print(f'SecretResponseScraper.fetch_secret_response(): An error occurred: {str(err)}')

    def _regex_showtime_code(self, body):
        try:
            results = re.findall(r"\*\$(.{8}-.{4}-.{4}-.{4}-.{12})2", body)
            if results:
                return results
            else:
                return False
        except Exception as err:
            print(f'SecretResponseScraper.regex_showtime_code(): An error occurred: {str(err)}')

    def _secret_codes_to_txt(self):
        # ! - not in use
        try:
            if self.secret_codes:
                txt_file = os.path.join(os.path.dirname(__file__), r'hkmovie\secret_codes.txt')
                with open(txt_file, 'a') as f:
                    # f.write(f'Current movie: {self.hkmovie6_code}\n')
                    for code in self.secret_codes:
                        f.write(str(code) + '\n')
        except Exception as err:
            print(f'SecretResponseScraper._secret_codes_to_txt(): An error occurred: {str(err)}')

    def _secret_codes_to_json(self):
        # ! - not in use
        try:
            if self.secret_codes:
                _secret_json = {
                    'movie_code': self.hkmovie6_code,
                    'secret_codes': list(self.secret_codes)
                }
                _json_file = os.path.join(os.path.dirname(__file__), r'hkmovie\secret_codes.json')
                _output = orjson.dumps(_secret_json)
                with open(_json_file, 'wb') as f:
                    f.write(_output)
        except Exception as err:
            print(f'SecretResponseScraper._secret_codes_to_txt(): An error occurred: {str(err)}')

    @retry(retry=retry_if_exception_type(TimeoutException), stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
    def shuffle_user_agent(self):
        # ! -not in use
        """
        User Agent for GeckoDriver cannot be changed at runtime. Read more:
        https://piprogramming.org/articles/How-to-change-the-User-Agent-AT-and-BEFORE-Runtime-using-Selenium-in-Python-0000000026.html
        :return:
        """
        # _ua = UserAgent()
        #
        # _script = 'var prefs = Components.classes["@mozilla.org/preferences-service;1"]'
        # _script += '.getService(Components.interfaces.nsIPrefBranch);'
        # _script += '\n'
        # _script += 'prefs.setBoolPref(arguments[0], arguments[1]);'
        #
        # self.driver.execute_script(_script, _ua.random)
        pass

    def tear_down(self):
        self.driver.close()
        self.driver.quit()

    def action(self, url):
        self._load_url(url)
        _t0 = time.time()
        html = self.driver.page_source
        _t1 = time.time()
        self.tear_down()
        print(f'\n====================Time spent to load html: {_t1 - _t0}')
        return html
