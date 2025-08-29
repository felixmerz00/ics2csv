# ICS to CSV Converter

This project converts `.ics` calendar files into CSV format. It processes each event in the `.ics` file and exports a structured CSV file with the following columns: `Event Name`, `Event Start Date`, `Event End Date`, `Location`, `Event Description`, and `All Day Event`.

### Features

- Converts events from an `.ics` file to a CSV file.
- Cleans up the event title and description by removing new lines and double spaces.
- Removes timezone information.

### Requirements

- Python 3.12.4+
- [icalendar](https://pypi.org/project/icalendar/) library

To install the `icalendar` library, run:
```bash
pip install icalendar
```
