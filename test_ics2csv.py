# Standard library imports
from pathlib import Path
# Third-party imports
# Project imports
from ics2csv import is_past, prepare_string_for_csv, read_ics, remove_double_space, remove_trailing_newline_and_space
from icalendar import Calendar, Component


def test_remove_zero_trailing_newline():
    s = "hello"
    actual = remove_trailing_newline_and_space(s)
    expected = "hello"
    assert actual == expected


def test_remove_three_trailing_newline():
    s = "hello\n\n\n"
    actual = remove_trailing_newline_and_space(s)
    expected = "hello"
    assert actual == expected


def test_remove_one_trailing_space():
    s = "hello "
    actual = remove_trailing_newline_and_space(s)
    expected = "hello"
    assert actual == expected


def test_remove_zero_double_space():
    s = "hello friend"
    actual = remove_double_space(s)
    expected = "hello friend"
    assert actual == expected


def test_remove_one_double_space():
    s = "hello  friend"
    actual = remove_double_space(s)
    expected = "hello friend"
    assert actual == expected


def test_remove_two_double_space():
    s = "hello   friend"
    actual = remove_double_space(s)
    expected = "hello friend"
    assert actual == expected


def test_replace_quotation_mark():
    s = "hello \"friend\""
    actual = s.replace('\"', '\"\"\"')
    expected = "hello \"\"\"friend\"\"\""
    assert actual == expected


def test_prepare_rich_string_for_csv():
    s = "hello \n   \"friend\"\n\n"
    actual = prepare_string_for_csv(s)
    expected = "\"hello \"\"\"friend\"\"\"\""
    assert actual == expected


def test_prepare_empty_string_for_csv():
    s = ""
    actual = prepare_string_for_csv(s)
    expected = ""
    assert actual == expected


def test_is_past_date_false():
    event = read_ics(Path("data/tests/input/past_event_false_allday.ics")).events[0]
    actual = is_past(event.get('DTEND').dt)
    expected = False
    assert actual == expected


def test_is_date_past_true():
    event = read_ics(Path("data/tests/input/past_event_true_allday.ics")).events[0]
    actual = is_past(event.get('DTEND').dt)
    expected = True
    assert actual == expected


def test_is_past_datetime_false():
    event = read_ics(Path("data/tests/input/past_event_false.ics")).events[0]
    actual = is_past(event.get('DTEND').dt.replace(tzinfo=None))
    expected = False
    assert actual == expected


def test_is_date_pasttime_true():
    event = read_ics(Path("data/tests/input/past_event_true.ics")).events[0]
    actual = is_past(event.get('DTEND').dt.replace(tzinfo=None))
    expected = True
    assert actual == expected
