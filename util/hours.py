import json
import logging
from datetime import datetime, timedelta

from util import tidyhq
from slack import misc as slack_misc, block_formatters

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


def add_hours_with_notifications(
    changes: dict,
    tidyhq_cache: dict,
    volunteer_hours: dict,
    volunteer_date: datetime,
    rewards: dict,
    config: dict,
    app,
    user_id: str,
):
    """Add hours to the record for a volunteer and notify them via Slack
    
    Returns the tidyhq_cache (potentially refreshed if users were not found)
    """

    successful = []
    failed = []
    cache_refreshed = False

    for volunteer in changes:
        hours = changes[volunteer]
        tidyhq_id = tidyhq.map_slack_to_tidyhq(
            tidyhq_cache=tidyhq_cache, config=config, slack_id=volunteer
        )
        if not tidyhq_id:
            # If we haven't refreshed the cache yet, try refreshing it first
            if not cache_refreshed:
                logging.info(f"Could not find TidyHQ ID for Slack user {volunteer}, refreshing cache")
                tidyhq_cache = tidyhq.fresh_cache(config=config, force=True)
                cache_refreshed = True
                
                # Write the fresh cache to file to make it the global copy
                with open("cache.json", "w") as f:
                    json.dump(tidyhq_cache, f, indent=4)
                
                # Try mapping again with the fresh cache
                tidyhq_id = tidyhq.map_slack_to_tidyhq(
                    tidyhq_cache=tidyhq_cache, config=config, slack_id=volunteer
                )
        
        if not tidyhq_id:
            logging.warning(f"Could not find TidyHQ ID for Slack user {volunteer} even after cache refresh")

            failed.append(volunteer)
            continue

        # Figure out if this addition unlocked any rewards
        # Monthly

        # Get the hours for the month in question
        current_hours = get_specific_month(
            tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours, month=volunteer_date
        )

        for reward in rewards["monthly"]:
            if current_hours < reward <= current_hours + hours:
                # Let the volunteer know
                slack_misc.send_dm(
                    slack_id=volunteer,
                    slack_app=app,
                    message=f"Congratulations! You've unlocked the monthly reward: *{rewards['monthly'][reward]['title']}* for volunteering {reward} hours in {volunteer_date.strftime('%B')}!",
                    blocks=block_formatters.reward_notification(
                        reward_definition=rewards["monthly"][reward],
                        hours=reward,
                        period=volunteer_date.strftime("%B"),
                    ),
                )
                # Let the admin channel know
                if "admin_channel" in config["slack"]:
                    app.client.chat_postMessage(
                        channel=config["slack"]["admin_channel"],
                        text=f":tada: <@{volunteer}> has unlocked the monthly reward: *{rewards['monthly'][reward]['title']}* for volunteering {reward} hours in {volunteer_date.strftime('%B')}!",
                    )

        # Cumulative
        current_hours = get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)
        for reward in rewards["cumulative"]:
            if current_hours < reward <= current_hours + hours:
                # Let the volunteer know
                slack_misc.send_dm(
                    slack_id=volunteer,
                    slack_app=app,
                    message=f"Congratulations! You've unlocked the lifetime reward: *{rewards['cumulative'][reward]['title']}* for volunteering a total of {reward} hours!",
                    blocks=block_formatters.reward_notification(
                        reward_definition=rewards["cumulative"][reward],
                        hours=reward,
                        period="cumulative",
                    ),
                )

                # Let the admin channel know
                if "admin_channel" in config["slack"]:
                    app.client.chat_postMessage(
                        channel=config["slack"]["admin_channel"],
                        text=f":tada: <@{volunteer}> has unlocked the lifetime reward: *{rewards['cumulative'][reward]['title']}* for volunteering a total of {reward} hours!",
                    )

        volunteer_hours = add_hours(
            tidyhq_id=tidyhq_id,
            volunteer_date=volunteer_date,
            hours_volunteered=hours,
            volunteer_hours=volunteer_hours,
            tidyhq_cache=tidyhq_cache,
        )

        logging.info(
            f"Added {hours} hours on {volunteer_date} for TidyHQ ID {tidyhq_id} (Slack ID {volunteer})"
        )

        slack_misc.push_home(
            user_id=volunteer,
            config=config,
            tidyhq_cache=tidyhq_cache,
            slack_app=app,
            volunteer_hours=volunteer_hours,
            rewards=rewards,
        )

        successful.append(volunteer)

        # Let the volunteer know
        slack_misc.send_dm(
            slack_id=volunteer,
            slack_app=app,
            message=f"<@{user_id}> added {hours}h against your profile for {volunteer_date.strftime('%B')}. Thank you for helping out!\nThere's no need to add tokens to the tub for these hours, they're already recorded.",
        )

    # Let the admin channel know how we went
    if successful:
        user_list = ""
        for volunteer in successful:
            user_list += f", <@{volunteer}> ({changes[volunteer]}h)"
        user_list = user_list[2:]

        app.client.chat_postMessage(
            channel=config["slack"]["admin_channel"],
            text=f":white_check_mark: <@{user_id}> added hours for {volunteer_date.strftime('%B')}: {user_list}",
        )

    if failed:
        for volunteer in failed:
            m = app.client.chat_postMessage(
                channel=config["slack"]["admin_channel"],
                text=f":warning: Could not add {changes[volunteer]}h to <@{volunteer}>, they're not registered on TidyHQ or they're not linked. (Attempted by <@{user_id}>)",
            )
            app.client.pins_add(
                channel=config["slack"]["admin_channel"], timestamp=m["ts"]
            )
    
    return tidyhq_cache
