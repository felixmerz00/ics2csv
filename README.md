# ICS to CSV Converter

This project converts `.ics` calendar files into CSV format. It processes each event in the `.ics` file and exports a structured CSV file with the following columns: `Event Name`, `Event Start Date`, `Event End Date`, `Location`, `Event Description`, and `All Day Event`.

### Features

- Converts events from an `.ics` file to a CSV file.
- Cleans up the event description by removing new lines, commas, and double spaces.
- Corrects end dates for all-day events by subtracting one day, as all-day events end at 00:00 on the next day in `.ics` files.
- Removes timezone information for non-all-day events.
- Adds a boolean `All Day Event` column to distinguish between all-day and timed events.

### Requirements

- Python 3.12.4+
- [icalendar](https://pypi.org/project/icalendar/) library

To install the `icalendar` library, run:
```bash
pip install icalendar
```
