# Standard library imports
from datetime import date, datetime, timedelta
from pathlib import Path
# Third-party imports
from icalendar import Calendar, Component


def read_ics(ics_path: Path) -> Calendar:
    """
    Read an ics file and return a Calendar object
    """
    with ics_path.open() as f:
        calendar = Calendar.from_ical(f.read())
    return calendar


def remove_trailing_newline_and_space(s: str):
    if s.endswith("\n"):
        return remove_trailing_newline_and_space(s[:-len("\n")])
    if s.endswith(" "):
        return remove_trailing_newline_and_space(s[:-len(" ")])
    return s


def remove_double_space(s: str):
    if s.find("  ") != -1:
        return remove_double_space(s.replace("  ", " "))
    return s


def prepare_string_for_csv(s: str):
    """
    Remove newline characters.
    Wrap quotation marks with quotation marks.
    Wrap the string with quotation marks.
    """
    s = remove_trailing_newline_and_space(s)
    s = s.replace('\n', ' ')
    s = remove_double_space(s)

    s = s.replace('\"', '\"\"\"')

    if s != "":
        s = "\"" + s + "\""

    return s


def format_temporal_information(e: Component):
    """
    Handle all day events and time zones
    Shorten all day events by one day, because in the ics file they end at 00:00 of the next day
    """
    is_all_day_event = "FALSE"
    start_date = e.get('DTSTART').dt
    end_date = e.get('DTEND').dt
    # All day events are of type date, other dates are of type datetime
    if type(end_date) is date:
        end_date = end_date - timedelta(days=1)
        is_all_day_event = "TRUE"
    else:
        # Remove the time zone information
        start_date = start_date.replace(tzinfo=None)
        end_date = end_date.replace(tzinfo=None)

    return start_date, end_date, is_all_day_event


def is_past(start_date):
    """
    Check if event is in the past.
    Precondition: For datetime, run startdt.replace(tzinfo=None) beforehand.
    """
    if type(start_date) is date:
        return start_date < date.today()
    return start_date < datetime.today()


def convert_ics_to_csv(cal: Calendar, csv_path: Path):
    """
    Write a Calendar to a csv file
    """
    # Write csv file
    with open(csv_path, "w") as f:
        # Column names
        f.write("Event Name,Event Start Date,Event End Date,Location,Event Description,All Day Event\n")
        for event in cal.walk("VEVENT"):
            title = prepare_string_for_csv(event.get('SUMMARY'))
            description = prepare_string_for_csv(event.get('DESCRIPTION', ''))
            start_date, end_date, is_all_day_event = format_temporal_information(event)

            if is_past(end_date):     # Ignore past events
                continue
            
            f.write(f"{title},{start_date},{end_date},{event.get('LOCATION')},{description},{is_all_day_event}\n")


# Place your ics file in the Downloads folder
dir_name = f"{Path.home()}/Downloads"
# Change file_name to the name of your ics file
file_name = "calendar"

c = read_ics(Path(f"{dir_name}/{file_name}.ics"))
convert_ics_to_csv(c, Path(f"{dir_name}/{file_name}.csv"))
