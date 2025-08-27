from ics2csv import prepare_string_for_csv, remove_trailing_newline_and_space, remove_double_space


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
