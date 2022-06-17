import os
import time
from lxml import etree
import re
from itertools import zip_longest

# =====================================================================================================================|
# =====================================================================================================================|
# {| Seatplan Processor |}
#
# This Class is used to read seat plan SVG scraped by SeatplanScraper.
# It parses and transforms all seats in a seat plan to a list of dictionaries,
# which contains data as follows:
# {row_number: n, [{'x': x-coordinate, 'y': y-coordinate, 'col': column_number, 'availability', is_seat_taken}...]}
#
# This Class also contains functions that cleanse an occupied seat plan to an "unoccupied" seat plan,
# and counts the number of seats in a seat plan.
#
# Not all seats are labelled with a column number (e.g., seats for disabled),
# there used to be functions that patch the labels,
# which were later proved to be unreliable.
# Hence, x-coordinate and y-coordinate are used to identify a seat.
#
# =====================================================================================================================|
# =====================================================================================================================|


class SeatplanProcessor:
    def __init__(self, svg_string):
        self.tree = etree.fromstring(svg_string)
        self.rows = list()
        self.isSeatOrderAscending = None
        self.house_capacity = 0
        self.svg = svg_string

        self.parse_row_elements()

    def get_occupied_seats(self):
        """
        yield seats in self.rows where availability = 2;
        data produced by this function will be INSERTED INTO SalesHistory and Seats tables
        :return: generator of dictionaries, keys: seat number, x-coordinate, y-coordinate
        """
        for row in self.rows:
            row_number = row[0]['row']
            for seat in row[1]:
                if seat['availability'] == 2:
                    seat_number = row_number + str(seat['col']) if seat.get('col') is not None else None
                    x = int(round(float(seat['x'])))
                    y = int(round(float(seat['y'])))
                    yield {"seat_number": seat_number, "x": x, "y": y}

    def get_house_capacity(self):
        _cap = sum(len(_row[1]) for _row in self.rows)
        return _cap

    def walk_tree(self):
        # ! - not in use
        for _event, _element in etree.iterwalk(self.tree, events=('start', 'end')):
            if _event == 'start':
                print(f'{str(_element.text).strip() if _element.text else ""}\telement.tag: {_element.tag}\telement.attrib : {_element.attrib}')

    def export_clean_svg(self):
        """
        substitute red rectangles with green rectangles;
        product of this function will be INSERTED INTO Houses (svg)
        :return:
        """
        # < rect. *?\(255, 0, 0\). *?stroke: ?rgb\(255, 0, 0\). *? / >
        _svg = etree.tostring(self.tree, encoding='unicode', pretty_print=False)
        _svg = re.sub(
            r'(<rect.*?\()255, 0, 0(\).*?stroke: ?rgb\()255, 0, 0(\).*?/>|\).+></rect>)',
            r"\g<1>0, 255, 0\g<2>0, 255, 0\g<3>", _svg)
        _svg = re.sub(
            r'(<text.*?; ??fill ??: ??rgb\()255, 0, 0(\).*?\">)',
            r"\g<1>0, 0, 0\g<2>", _svg)
        return _svg

    def parse_row_elements(self):
        """
        flow:
            1) for each row (i.e., <g> tag) in seat plan, do:
            2) for each seat in row, do:
            3) get seat's x-coordinate, y-coordinate, availability, seat number
            4) once a row is processed, append a dict containing
                row number,
                and a list of dicts containing each seat's x-coordinate, y-coordinate, availability, column number
        assumptions:
            1) <rect> tag is always present
            2) <rect> width attribute is used to recognize seat type
                    a) width == 10: single seat
                    b) width == 25: double seat
        :return:
        """
        # (1) - loop through all rows
        _allRows = self.tree.xpath('/svg/g')
        for _row in _allRows:
            try:
                _row_number = str(_row.xpath('text[1]')[0].text).strip()
                seat_list = list()
                # (2) - loop through all columns (seats)
                _seats = _row.xpath('a')
                for _seat in _seats:
                    seat_data = dict()
                    _seat_rect = _seat.xpath('rect')[0]
                    _x = _seat_rect.attrib.get('x')
                    _y = _seat_rect.attrib.get('y')

                    # (3) - get seat width to identify single/double seat
                    _w = _seat_rect.attrib.get('width', 10)
                    if _w == '10':
                        self.house_capacity += 1
                        single_seat_data = self.parse_single_seat(_seat_rect)

                        try:
                            _seat_text = _seat.xpath('text')[0]
                            _seat_number = int(str(_seat.xpath('text')[0].text).strip())
                            single_seat_data['col'] = _seat_number

                        except IndexError:
                            # ! - if <text> tag not found under <a> tag, it might be disabled/vibratin seat
                            _seat_text, _seat_number, single_seat_data['col'] = None, None, None
                            pass
                        # ! - convert to list(dict) for seat_list extend
                        seat_data = [single_seat_data]
                    # print(f'seat data: {seat_data}\t\tseat list: {seat_list[-3:]}')
                    elif _w == '25':
                        self.house_capacity += 2
                        double_seat_data = self.parse_double_seat(_seat, _seat_rect)
                        seat_data = double_seat_data

                    seat_list.extend(seat_data)
                self.rows.append([{'row': _row_number}, seat_list])

            except IndexError:
                # ! - this exception is used to bypass the tags that represent "SCREEN"
                # ! - as "SCREEN" xpath (/svg/g/a) will be filtered by xpath search (/svg/g/text)
                pass
        return

    def parse_single_seat(self, rect):
        """
        :param rect: <a>/<rect> tag
        :return: a dict containing x-coordinate (str), y-coordinate (str), availability (int)
        """
        single_seat_dict = dict()

        _x = rect.attrib.get('x')
        _y = rect.attrib.get('y')
        single_seat_dict['x'] = _x
        single_seat_dict['y'] = _y

        _seat_style = rect.attrib.get('style')
        if _seat_style:
            single_seat_dict['availability'] = self.get_availability_from_style(_seat_style)
        else:
            single_seat_dict['availability'] = 1

        return single_seat_dict

    def parse_double_seat(self, seat, rect):
        """
        assumptions:
            1) double seat is always structured as follows:
                <a transform="rotate(degree, x, y)">
                    <rect x="?" y="?"></rect>
                    <text></text>
                    <text></text>
                <a>
        :param seat:
        :param rect:
        :return: a list of 2 dicts (i.e., two seats in double seats);
                    each dict contains x-coordinate (str), y-coordinate (str),
                    availability (int), column number (int) (e.g., 7 as in seat B7)
        """
        double_seat_dicts = [dict(), dict()]

        _x = rect.attrib.get('x')
        _y = rect.attrib.get('y')

        _seat_text = seat.xpath('text')
        for i in range(2):
            double_seat_dicts[i]['x'] = _x
            double_seat_dicts[i]['y'] = _y
            _seat_number = int(str(_seat_text[i].text).strip())
            double_seat_dicts[i]['col'] = _seat_number
            _seat_style = _seat_text[i].get('style')
            if _seat_style:
                double_seat_dicts[i]['availability'] = self.get_availability_from_style(_seat_style)
            else:
                double_seat_dicts[i]['availability'] = 1

        return double_seat_dicts

    def get_availability_from_style(self, style):
        """
        parse RGB of seat rectangle from svg style attribute
        transform to a tuple of 3 integers
        if color = red, then the seat is considered taken
        else, not taken

        :return: int; 1 (free), 2 (taken)
        """
        _rgb = re.search(r'fill: ?rgb\((\d{0,3}), ?(\d{0,3}), ?(\d{0,3})\)', style)
        if _rgb:
            _r, _g, _b = _rgb.group(1), _rgb.group(2), _rgb.group(3)
            if (_r, _g, _b) == ('255', '0', '0'):
                _availability = 2
            else:
                _availability = 1
        else:
            _availability = 1

        return _availability

    def patch_missing_column(self):
        # ! - not in use
        """
        scenarios where seat number will be missing:
            1) seat is for disabled
            2) seat is a vibrating seat
        """
        for _i, _r in enumerate(self.rows):
            for _c in _r[1]:
                _row_number = _r[0]['row']
                if _c.get('col') is None:
                    print(f'A None seat is found in Row {_row_number}')
                    _first_patch = self.fill_by_incremental_col_num(_i)
                    if not _first_patch:
                        _second_patch = self.fill_by_x_coordinate(_i)
                    break

    def fill_by_incremental_col_num(self, index_of_row):
        # ! - not in use
        """
        assumptions:
            1) columns are always in ascending order, and each column is increased by 1

        description:
            Given an ordered list of column numbers with at least one valid number and one None,
            fill all the None by increasing or decreasing from the closest valid number

            Examples: [1, 2, None, 4, None, 6, None, 8, None, None] => [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

            If success, patch self.rows directly and return True;
            If the row does not contain at least one valid column number, return False

        flow:
            1) retrieve the column numbers from the given row as a list
            2) look for first valid (non-None) number in the list
                if all are Nones, return False
            3) create a range of numbers based on the index of the first number and length of [column numbers] from (1)
                start of range = first number minus its index
                    > this will bring us the starting number, assuming the step is 1
                end of range = first number plus the remaining columns left in the list
            4) compare the filled numbers list from 3) with original list from (1)
                theoretically, they should match perfectly because the step from one column to another is 1
                if not, this may imply
                    a) the seats are not placed consecutively, because of separation by aisle, etc.
            5) update self.rows with a for-loop
        :param index_of_row: given an index of row, for example "3",
                this function will access the row in self.rows by index
        :return: If the list generated by filled numbers matches entirely to original list, return True.
                Otherwise, return False
        """
        _cols = [_c.get("col") for _c in self.rows[index_of_row][1]]
        print(f'FIRST EXTRACTED COL: {_cols}')

        # print(self.isSeatOrderAscending)
        _current_row = self.rows[index_of_row][0]["row"]
        # print(f'getting {self.rows[index_of_row][0]["row"]} by incremental fill')
        # ! - find first non-None value
        try:
            _valid_num = next(__c for __c in _cols if __c is not None)
        except StopIteration:
            # ! - except all are Nones
            _row_number = self.rows[index_of_row][0]['row']
            # print(f'all cols for row {self.rows[index_of_row][0]["row"]} are None')
            return False
        _index = _cols.index(_valid_num)
        # print(f'index to the first valid num is {_index}')
        if _valid_num - _index > 0:
            if self.isSeatOrderAscending:
                # print(f'self.isSeatOrderAscending is {self.isSeatOrderAscending}')
                _filled_cols = list(range(_valid_num - _index, len(_cols) - _index + _valid_num))
            else:
                # print(f'self.isSeatOrderAscending is {self.isSeatOrderAscending}')
                _filled_cols = list(range(_index + _valid_num, _valid_num - len(_cols) + _index, -1))
        else:
            # ! - all column numbers should be > 0, otherwise return False
            print(f'not all column numbers for row {self.rows[index_of_row][0]["row"]} > 0')
            return False

        # ! - validate whether the filled list matches entirely to the original list
        # ! - (i.e., whether the columns are indeed increased by 1 each)
        # ! - only work if original list has two non-None values
        if _col_num := self.rows[index_of_row][0]["row"] == "A":
            print(f'Current Row: {self.rows[index_of_row][0]["row"]}')
            print(f'extracted row = {_cols}')
            print(f'calculated row = {_filled_cols}')
            print(set(_filled_cols).difference(set(_cols)))
            print('===================================================================')

        _differences = [_d for _d in set(_cols).difference(set(_filled_cols)) if _d is not None]
        if len(_differences) != 0:
            # print(f'increase for each col in row {self.rows[index_of_row][0]["row"]} is not +1')
            return False

        for _n, _c in zip(_filled_cols, self.rows[index_of_row][1]):
            _c["col"] = _n

        # print(f'|| Patched row {self.rows[index_of_row][0]["row"]}')
        return True

    def fill_by_x_coordinate(self, index_of_row):
        # ! - not in use
        """
        assumptions:
            1) the gap between two <rect> elements is always 15px
            2) based on (1), if the gap between two <rects> is less than 15px (~12px), then they are on the same column
            3) rows closer to each other tend to have the same structure,
                thus the seat on the closest row will share same x-coordinate, rotation with the target seat
        flow:
            1) create two lists of numbers
                a) one of which runs from given index to first index of list
                b) another runs from given index to ending index of list
                the purpose is explained on assumption (3)
            2) loop from first seat on the row
            3) inner loop through each seats on the closest rows
            4) once the column number for first seat is acquired, run self.fill_by_incremental_col_num
            5) if (4) returns False, continue to next seat in (2); otherwise, return True for this row
        """
        if index_of_row != self.rows:
            _loop_idx = index_of_row
        else:
            _loop_idx = index_of_row - 1

        _positive_range = list(reversed(range(0, _loop_idx)))
        _negative_range = range(_loop_idx + 1, len(self.rows))

        for _target_seat in self.rows[index_of_row][1]:
            _target_seat_rotate_degree = _target_seat.get('rotate_degree', 0)
            _target_seat_rotate_x = _target_seat.get('rotate_x', 0)
            _target_seat_x = _target_seat['x']
            # print(f'current seat {_target_seat.get("col")}')
            for a, b in zip_longest(_positive_range, _negative_range):
                _a_loop = False
                _b_loop = False
                if a is not None:
                    for _ref_seat in self.rows[a][1]:
                        if _ref_seat.get('rotate_degree', 0) == _target_seat_rotate_degree and \
                                _ref_seat.get('rotate_x', 0) == _target_seat_rotate_x and \
                                _ref_seat['x'] == _target_seat_x and \
                                _ref_seat.get('col') is not None:
                            # print(
                            #     f'===a) Seat {self.rows[a][0]["row"]}{_ref_seat["col"]} has the same property as target seat:')
                            # print(f'|||> {_ref_seat}')
                            # print(f'||> {_target_seat}')
                            _target_seat['col'] = _ref_seat['col']
                            _a_loop = True
                            break
                # print(f'a loop ended')
                if _a_loop:
                    break
                if b is not None:
                    for _ref_seat in self.rows[b][1]:
                        if _ref_seat.get('rotate_degree', 0) == _target_seat_rotate_degree and \
                                _ref_seat.get('rotate_x', 0) == _target_seat_rotate_x and \
                                _ref_seat['x'] == _target_seat_x and \
                                _ref_seat.get('col') is not None:
                            # print(f'===b) Seat {self.rows[b][0]["row"]}{_ref_seat["col"]} has the same property as target seat:')
                            # print(f'|||> {_ref_seat}')
                            # print(f'||> {_target_seat}')
                            _target_seat['col'] = _ref_seat['col']
                            _b_loop = True
                            break
                # print(f'b loop ended')
                if _b_loop:
                    break

            # print(f'|| Patched row {self.rows[index_of_row][0]["row"]} by x-coordinates')
            _patch = self.fill_by_incremental_col_num(index_of_row)
            if _patch:
                return True
        return


if __name__ == "__main__":
    svg_file = 'seatplan_double_seats.svg'
    # svg_file = 'seatplan.svg'
    svg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, 'ScheduledTasks'))
    svg_list = [os.path.join(svg_path, f) for f in os.listdir(svg_path) if str(f).endswith('5.svg')]
    for svg in svg_list:
        print(f'===========\t=> Current svg: {svg}')
        with open(svg, 'rb') as f:
            lxml_as_binary = f.read()

        t0 = time.time()
        sp = SeatplanProcessor(lxml_as_binary)
        print(sp.export_clean_svg())

        t1 = time.time()


    # print(f'\n===================================\nTime spent to analyze seatplan: {t1 - t0}')