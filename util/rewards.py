from typing import Callable
from util import tidyhq
from datetime import datetime

# Set up logging
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_reward_function(name: str) -> Callable | None:
    """Returns the function associated with a reward name."""
    reward_map = {"volunteer_badge": volunteer_badge}

    func = reward_map.get(name)

    if func:
        logger.info(f"Found reward function for {name}")
    else:
        logger.warning(f"No reward function found for {name}")

    return func


def volunteer_badge(
    tidyhq_id: str, timestamp: datetime, tidyhq_cache: dict, config: dict
) -> bool:
    """Sets a volunteer badge for a TidyHQ contact."""

    # Since we're going to be writing data back to TidyHQ based on the existing data the cache must be live
    # This helps us preserve the most up-to-date information rather than overwriting it with stale data

    field = tidyhq.get_custom_field(
        config=config,
        cache=tidyhq_cache,
        contact_id=tidyhq_id,
        field_map_name="volunteer",
        live=True,
    )

    field_str: str = ""
    if field:
        print("Found existing volunteer field")
        field_str = field.get("value", "")
        print(field_str)

    # Dates are stored in a comma separated list of YYMM

    already_badged = False

    # Parse the existing field value
    existing_dates = []
    for date_str in field_str.split(","):
        if not date_str:
            continue
        date = datetime.strptime(date_str.strip(), "%y%m")
        existing_dates.append(date)

        # Check the year/month against the provided timestamp
        if date.year == timestamp.year and date.month == timestamp.month:
            already_badged = True

    if not already_badged:
        # Add the new date
        existing_dates.append(timestamp)

        # Sort the dates
        existing_dates.sort()

        # Convert back to YYMM format
        new_field_str = ",".join([date.strftime("%y%m") for date in existing_dates])

        # Update the contact
        logger.info(f"Updating volunteer badge for {tidyhq_id}")
        logger.info("From: " + field_str)
        logger.info("To:   " + new_field_str)
        return tidyhq.set_custom_field(
            contact_id=tidyhq_id,
            value=new_field_str,
            field_map_name="volunteer",
            config=config,
        )

    logger.info(f"Volunteer badge already set for {tidyhq_id} for this month")
    return True
