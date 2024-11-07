# Standard library imports
from datetime import date, timedelta
from pathlib import Path
# Third-party imports
from icalendar import Calendar


def read_ics(ics_path: Path) -> Calendar:
    """
    Read an ics file and return a Calendar object
    """
    with ics_path.open() as f:
        calendar = Calendar.from_ical(f.read())
    return calendar


def convert_ics_to_csv(cal: Calendar, csv_path: Path):
    """
    Write a Calendar to a csv file
    """
    # Write csv file
    with open(csv_path, "w") as f:
        # Column names
        f.write("Event Name,Event Start Date,Event End Date,Location, Event Description,All Day Event\n")
        for event in cal.walk("VEVENT"):
            # Remove new line characters, commas, and double spaces from the description
            description = event.get('DESCRIPTION', '').replace('\n', ' ').replace(',', '').replace('  ', ' ')

            # Handle all day events and time zones
            # Shorten all day events by one day, because in the ics file they end at 00:00 of the next day
            # All day events have type datetime.date, other dates have type datetime.datetime
            is_all_day_event = "FALSE"  # For boolean column for all day events
            start_date = event.get('DTSTART').dt
            end_date = event.get('DTEND').dt
            if type(end_date) is date:
                end_date = end_date - timedelta(days=1)
                is_all_day_event = "TRUE"
            else:
                # Remove the time zone information
                start_date = start_date.replace(tzinfo=None)
                end_date = end_date.replace(tzinfo=None)
            
            f.write(f"{event.get('SUMMARY')},{start_date},{end_date},{event.get('LOCATION')},{description},{is_all_day_event}\n")


# Place your ics file in the Downloads folder
dir_name = f"{Path.home()}/Downloads"
# Change file_name to the name of your ics file
file_name = "calendar"

cal = read_ics(Path(f"{dir_name}/{file_name}.ics"))
convert_ics_to_csv(cal, Path(f"{dir_name}/{file_name}.csv"))
