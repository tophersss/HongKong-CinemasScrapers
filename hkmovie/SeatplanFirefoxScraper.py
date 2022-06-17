from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from fake_useragent import UserAgent
import os
import time
import re
from tenacity import retry, retry_if_exception_type, stop_after_attempt, RetryError, wait_random

from random import randint


class Terminator(Exception):
    """this breaks your function execution"""
    pass


class SeatplanScraper:
    def __init__(self, headless=True):
        self._setup(headless)
        self.refreshed = False

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
            service_log_path= _service_log_path
        )
        self.driver.set_page_load_timeout(5)
        return True

    @retry(retry=(
            retry_if_exception_type(TimeoutException) |
            retry_if_exception_type(AttributeError) |
            retry_if_exception_type(WebDriverException)
        ),
           stop=stop_after_attempt(3), wait=wait_random(min=2, max=5))
    def _get_show_details_from_page_source(self, _pattern):
        _page_src = self.driver.page_source
        _result = re.search(_pattern, _page_src)
        # print(f'Pattern = {_pattern}')
        _pos = str(_page_src).find('{response:{')
        # print(f'page src = {_page_src[_pos-50:_pos+100]}')
        if _result:
            return _result.group(1)
        else:
            return None

    @retry(retry=(
            retry_if_exception_type(TimeoutException) |
            retry_if_exception_type(AttributeError) |
            retry_if_exception_type(WebDriverException)
        ),
           stop=stop_after_attempt(5), wait=wait_random(min=2, max=5))
    def _get_show_details_from_html(self, _selector, _attribute):
        """
        Some seatplan pages may no longer be available for various reasons
        which will only display a page with 500 status code message.

        If function is used to check whether the 500 status code exists,
        return None immediately if not found;
        Else if used to check other elements,
        raise TimeoutException and keep retrying
        :return:
        """
        try:
            _element = WebDriverWait(self.driver, 10).until(
                ec.presence_of_element_located(
                    (By.CSS_SELECTOR, _selector)
                )
            )
        except TimeoutException as err:
            if _selector == 'div.mainWrapper > div > div > div > div.errorText.f.row.wrap':
                # print(repr(err))
                return None
            else:
                raise TimeoutException

        # print(f'Presence of element located: {_element}\n'
        #       f'text = {_element.text}\n'
        #       f'innerHTML = {_element.get_attribute("innerHTML")}')

        if _element:
            if _attribute == 'text':
                _result = _element.text
                if _result is None or _result == '':
                    _result = _element.get_attribute('innerHTML')

            elif _attribute == 'outerHTML':
                _result = _element.get_attribute('outerHTML')

            if _result:
                _result = str(_result).strip()
                return _result
        else:
            return None
        return None

    def scrape(self, hkmovie6_code, showtime_code):
        """
        assumptions:
            1)

        :param hkmovie6_code:
        :param showtime_code:
        :return:
        """
        try:
            _profile = dict()
            _profile["showtime_code"] = showtime_code
            _url = f"https://hkmovie6.com/movie/{hkmovie6_code}/SHOWTIME/{showtime_code}"
            t1 = time.time()
            try:
                self._load_url(_url)
            except RetryError:
                # print(f'failed to load url after 3 retries... raising Terminator')
                # raise Terminator
                raise Terminator(f'SeatplanScraper.scrape({self.driver.session_id}): failed to load {_url} after 3 retries')

            if not self.refreshed:
                time.sleep(1)
                try:
                    self._refresh()
                except RetryError:
                    raise Terminator(f'SeatplanScraper.scrape({self.driver.session_id}): failed to refresh after 3 retries')
                self.refreshed = True

            time.sleep(randint(2, 3))

            t2 = time.time()

            # try:
            #     _isRemoved = self._get_show_details_from_html('div.mainWrapper > div > div > div > div.errorText.f.row.wrap', 'outerHTML')
            #     # print(f'checking if page is removed')
            #     if _isRemoved is None:
            #         # ! - page removed error is not found, page is not removed
            #         # print(f'page is not removed, returning None')
            #         pass
            #     else:
            #         print(f'page removed\t{_url}')
            #         _isRemoved = f'{showtime_code}:\t{_isRemoved}'
            #         # time.sleep(10)
            #         # print(f'slept for 10 sec')
            #         # print(f'{_isRemoved}'
            #         return None
            # except RetryError:
            #     print(f'failed to locate 500 error meesage, raising Terminator')
            #     pass

            try:
                _seatplan = self._get_show_details_from_html('div.seatplanWrapper > svg', 'outerHTML')
            except RetryError:
                print(f'failed to load seatplan after 5 retries, raising Terminator')
                raise Terminator('SeatplanScraper.scrape(): TimeOut after five retries '
                                 f'to get seatplan from {_url}')
            # ! - add namespace to <svg> tag
            _pos = _seatplan.find('>')
            _seatplan = _seatplan[:_pos] + ' xmlns:xlink="http://www.w3.org/1999/xlink" ' + _seatplan[_pos:]
            _profile["seatplan"] = _seatplan
            t3 = time.time()

            try:
                _profile["house"] = self._get_show_details_from_html(
                    'div > div.mainWrapper > div > div > div.seatplanWrapper > '
                    'div.showDetail > div.name.f.row.wrap > div', 'text')
            except RetryError:
                raise Terminator('SeatplanScraper.scrape(): TimeOut after three retries '
                                 f'while getting on house name on {_url}')
            # _title = self._get_show_details_from_html(
            #     '#__layout > div > div.mainWrapper > div > '
            #     'div > div.seatplanWrapper > div.movieDetail > div.name.clickable'
            # )
            _price = self._get_show_details_from_page_source(
                r'{response:{show:{house:".+",starttime:\d+?,price:(\d{2,3})?,')
            if _price is None:
                _price = self._get_show_details_from_html(
                    '#__layout > div > div.mainWrapper > div > div > div.seatplanWrapper > '
                    'div.showDetail > div.timePrice > div.text.dispDesktop', 'text')
                try:
                    _price = re.search(r'\$(\d{2,3})?', _price).group(1)
                except:
                    _price = None
                    pass

            try:
                _profile["price"] = int(_price)
            except:
                _profile["price"] = None

            _start_time = self._get_show_details_from_page_source(
                r'{response:{show:{house:\"?.+\"?,starttime:(\d+)?,')
            try:
                _profile["start_time"] = int(_start_time)
            except:
                _profile["start_time"] = None

            print(f'^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^|\n'
                  f'driver: {self.driver.session_id}\n'
                  f'house: {_profile["house"]} (refreshed: {self.refreshed})\n'
                  f'start_time: {_profile["start_time"]}\n'
                  f'from {_url}\n'
                  f'_________________________________________________|')

            # print(f'=========================================\n')
            # for key in _profile.keys():
            #     if key != 'seatplan':
            #         print(f'{key}: {_profile[key]}')
            # print('...')
            return _profile
        except Terminator as terminator:
            print(f'SeatplanScraper.scrape(session_id={self.driver.session_id}) Terminator raised: \n{repr(terminator)}')
            raise Terminator(f'Terminator re-raised: {str(terminator)}')

    @retry(retry=(
            retry_if_exception_type(TimeoutException) |
            retry_if_exception_type(AttributeError) |
            retry_if_exception_type(WebDriverException)
        ),
           stop=stop_after_attempt(5), wait=wait_random(min=5, max=20))
    def _load_url(self, url):
        self.driver.get(url)
        # if randint(0, 5) == 0:
        #     print(f'\t\t==>driver {self.driver.session_id} raising Timeout for {url}')
        #     raise TimeoutException

    @retry(retry=(
            retry_if_exception_type(TimeoutException) |
            retry_if_exception_type(AttributeError) |
            retry_if_exception_type(WebDriverException)
        ),
           stop=stop_after_attempt(3), wait=wait_random(min=5, max=10))
    def _refresh(self):
        self.driver.refresh()

    @retry(retry=(retry_if_exception_type(TimeoutException) | retry_if_exception_type(TimeoutError)),
           stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
    def shuffle_user_agent(self):
        # ! - not in use
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
        print(f'tear_down() driver: {self.driver.session_id}')
        try:
            # self.driver.close()
            self.driver.quit()
            print(f'Tore down driver: {self.driver.session_id}')
        except WebDriverException as err:
            print(f'tear_down({self.driver.session_id}) error: {repr(err)}')
