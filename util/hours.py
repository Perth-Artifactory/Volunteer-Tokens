import json
import logging
from datetime import datetime, timedelta

from util import tidyhq

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


def generate_new(
    tidyhq_id: int | str, volunteer_hours: dict, tidyhq_cache: dict
) -> dict:
    """Generate a new hours entry for a specified TidyHQ ID."""

    tidyhq_id = str(tidyhq_id).strip()

    if tidyhq_id in volunteer_hours:
        return volunteer_hours

    tidyhq_contact = tidyhq.get_contact(
        contact_id=str(tidyhq_id), tidyhq_cache=tidyhq_cache
    )

    if not tidyhq_contact:
        logging.error(f"Failed to find TidyHQ contact for ID {tidyhq_id}")
        return volunteer_hours

    volunteer_hours[tidyhq_id] = {
        "name": tidyhq.format_contact(contact=tidyhq_contact),
        "months": {},
    }

    with open("hours.json", "w") as f:
        json.dump(volunteer_hours, f, indent=4)

    return volunteer_hours


def get_total(tidyhq_id: int | str, volunteer_hours: dict) -> int:
    """Get the total hours for a specified TidyHQ ID."""

    tidyhq_id = str(tidyhq_id).strip()

    if tidyhq_id not in volunteer_hours:
        return 0

    total_hours = 0

    for monthly_hours in volunteer_hours[tidyhq_id]["months"].values():
        total_hours += monthly_hours

    return total_hours


def get_specific_month(
    tidyhq_id: int | str, volunteer_hours: dict, month: datetime
) -> int:
    """Get the hours for a specified month for a specified TidyHQ ID."""

    tidyhq_id = str(tidyhq_id).strip()

    if tidyhq_id not in volunteer_hours:
        return 0

    month_str = month.strftime("%Y-%m")

    return volunteer_hours[tidyhq_id]["months"].get(month_str, 0)


def get_last_month(tidyhq_id: int | str, volunteer_hours: dict) -> int:
    """Get the hours for last month for a specified TidyHQ ID."""

    return get_specific_month(
        tidyhq_id=tidyhq_id,
        volunteer_hours=volunteer_hours,
        month=datetime.now() - timedelta(days=30),
    )


def get_current_month(tidyhq_id: int | str, volunteer_hours: dict) -> int:
    """Get the hours for the current month for a specified TidyHQ ID."""

    return get_specific_month(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours, month=datetime.now()
    )


def add_hours(
    tidyhq_id: int | str,
    volunteer_hours: dict,
    hours_volunteered: int,
    volunteer_date: datetime,
    tidyhq_cache: dict,
) -> dict:
    """Add hours to the record for a volunteer"""

    volunteer_hours = generate_new(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours, tidyhq_cache=tidyhq_cache
    )

    # Add a record for the current month if not present
    record_str = volunteer_date.strftime(format="%Y-%m")

    if record_str not in volunteer_hours[tidyhq_id]["months"]:
        volunteer_hours[tidyhq_id]["months"][record_str] = 0

    volunteer_hours[tidyhq_id]["months"][record_str] += hours_volunteered

    # Save the hours back to file
    with open("hours.json", "w") as f:
        json.dump(volunteer_hours, f, indent=4)

    return volunteer_hours
