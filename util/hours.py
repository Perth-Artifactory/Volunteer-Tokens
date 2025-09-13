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
    """Add hours to the record for a volunteer and notify them via Slack"""

    successful = []
    failed = []

    for volunteer in changes:
        hours = changes[volunteer]
        tidyhq_id = tidyhq.map_slack_to_tidyhq(
            tidyhq_cache=tidyhq_cache, config=config, slack_id=volunteer
        )
        if not tidyhq_id:
            logging.warning(f"Could not find TidyHQ ID for Slack user {volunteer}")

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


def get_overall_statistics(
    volunteer_hours: dict, config: dict, tidyhq_cache: dict
) -> dict:
    """Calculate overall statistics across all volunteers."""

    total_hours = 0
    total_admin_hours = 0
    admin_count = 0
    hours_by_month = {}

    for tidyhq_id, volunteer_data in volunteer_hours.items():
        volunteer_total = 0

        admin = tidyhq.check_for_groups(
            contact_id=str(tidyhq_id),
            groups=config["tidyhq"]["group_ids"]["admin"],
            tidyhq_cache=tidyhq_cache,
        )

        for month_str, hours_in_month in volunteer_data["months"].items():
            # Add to monthly totals
            if month_str not in hours_by_month:
                hours_by_month[month_str] = 0
            hours_by_month[month_str] += hours_in_month

            # Add to volunteer total
            volunteer_total += hours_in_month

        if admin:
            total_admin_hours += volunteer_total
            admin_count += 1

        total_hours += volunteer_total

    total_volunteers = len(volunteer_hours)
    average_hours_per_volunteer = total_hours / total_volunteers

    # Sort months chronologically
    sorted_months = dict(sorted(hours_by_month.items(), reverse=True))

    return {
        "total_hours": total_hours,
        "total_volunteers": total_volunteers,
        "average_hours_per_volunteer": round(average_hours_per_volunteer, 1),
        "average_hours_per_volunteer_no_admin": round(
            (total_hours - total_admin_hours) / (total_volunteers - admin_count), 1
        ),
        "hours_by_month": sorted_months,
    }


def get_top_volunteers(volunteer_hours: dict, limit: int = 5) -> list:
    """Get the top volunteers by total hours."""

    volunteers_with_totals = []

    for tidyhq_id, volunteer_data in volunteer_hours.items():
        total = get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)
        if total > 0:
            volunteers_with_totals.append(
                {
                    "tidyhq_id": tidyhq_id,
                    "name": volunteer_data["name"],
                    "total_hours": total,
                }
            )

    # Sort by total hours (descending) and take top N
    volunteers_with_totals.sort(key=lambda x: x["total_hours"], reverse=True)
    return volunteers_with_totals[:limit]


def get_all_volunteers(volunteer_hours: dict) -> list:
    """Get all volunteers with hours, sorted by total hours (descending)."""

    volunteers_with_totals = []

    for tidyhq_id, volunteer_data in volunteer_hours.items():
        total = get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)
        if total > 0:
            volunteers_with_totals.append(
                {
                    "tidyhq_id": tidyhq_id,
                    "name": volunteer_data["name"],
                    "total_hours": total,
                }
            )

    # Sort by total hours (descending)
    volunteers_with_totals.sort(key=lambda x: x["total_hours"], reverse=True)
    return volunteers_with_totals


def get_non_admin_volunteers(
    volunteer_hours: dict, config: dict, tidyhq_cache: dict
) -> list:
    """Get all non-admin volunteers with hours, sorted by total hours (descending).

    Appends committee members total at the end of the list."""

    volunteers_with_totals = []
    committee = 0
    admin_groups = config["tidyhq"]["group_ids"]["admin"]

    for tidyhq_id, volunteer_data in volunteer_hours.items():
        total = get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)
        if total > 0:
            # Check if this volunteer is an admin
            is_admin = tidyhq.check_for_groups(
                contact_id=tidyhq_id,
                groups=admin_groups,
                tidyhq_cache=tidyhq_cache,
            )

            if is_admin:
                committee += total

            if not is_admin:
                volunteers_with_totals.append(
                    {
                        "tidyhq_id": tidyhq_id,
                        "name": volunteer_data["name"],
                        "total_hours": total,
                    }
                )

    # Sort by total hours (descending)
    volunteers_with_totals.sort(key=lambda x: x["total_hours"], reverse=True)

    volunteers_with_totals.append(
        {
            "tidyhq_id": "committee",
            "name": "Committee Members",
            "total_hours": committee,
        }
    )

    return volunteers_with_totals
