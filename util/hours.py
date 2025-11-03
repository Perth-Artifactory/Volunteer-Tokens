import json
import logging
from datetime import datetime, timedelta

from util import tidyhq, rewards as rewards_util
from slack import misc as slack_misc, block_formatters

from slack_bolt import App

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


def get_volunteer_streak(tidyhq_id: int | str, volunteer_hours: dict) -> dict:
    """Get the volunteering streak for a specified TidyHQ ID."""

    tidyhq_id = str(tidyhq_id).strip()

    streaks = get_hour_streaks(volunteer_hours=volunteer_hours)

    return streaks.get(tidyhq_id, {"longest_streak": 0, "current_streak": 0})


def get_badge_streak(tidyhq_id: int | str, volunteer_hours: dict) -> dict:
    """Get the badge streak for a specified TidyHQ ID."""

    tidyhq_id = str(tidyhq_id).strip()

    badge_streaks = get_volunteer_badge_streaks(volunteer_hours=volunteer_hours)

    return badge_streaks.get(tidyhq_id, {"longest_streak": 0, "current_streak": 0})


def get_debt(tidyhq_id: int | str, volunteer_hours: dict) -> int:
    """Get the time debt for a specified TidyHQ ID.

    Debts bottom out at 0"""

    tidyhq_id = str(tidyhq_id).strip()

    if tidyhq_id not in volunteer_hours:
        return 0

    total_hours = get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)

    debt = volunteer_hours[tidyhq_id].get("debt", 0) - total_hours

    return max(debt, 0)


def add_hours(
    tidyhq_id: int | str,
    volunteer_hours: dict,
    hours_volunteered: int,
    volunteer_date: datetime,
    tidyhq_cache: dict,
    debt: bool = False,
) -> dict:
    """Add hours to the record for a volunteer"""

    volunteer_hours = generate_new(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours, tidyhq_cache=tidyhq_cache
    )

    if debt:
        volunteer_hours[tidyhq_id]["debt"] = (
            volunteer_hours[tidyhq_id].get("debt", 0) + hours_volunteered
        )
    else:
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
    note: str,
    rewards: dict,
    config: dict,
    app: App,
    user_id: str,
    debt: bool = False,
    send_to_channel: bool = True,
) -> dict:
    """Add hours to the record for a volunteer and notify them via Slack

    Returns the tidyhq_cache (potentially refreshed if users were not found)
    """

    successful = []
    failed = []
    cache_refreshed = False

    # Check whether the volunteering date is at most four months old
    # For anything older than that we append the year to the notifications instead of just month

    year_str = ""
    if volunteer_date < datetime.now() - timedelta(days=122):
        year_str = f" ({volunteer_date.year})"

    for volunteer in changes:
        hours = changes[volunteer]
        tidyhq_id = tidyhq.map_slack_to_tidyhq(
            tidyhq_cache=tidyhq_cache, config=config, slack_id=volunteer
        )
        if not tidyhq_id:
            # If we haven't refreshed the cache yet, try refreshing it first
            if not cache_refreshed:
                logging.info(
                    f"Could not find TidyHQ ID for Slack user {volunteer}, refreshing cache"
                )
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
            logging.warning(
                f"Could not find TidyHQ ID for Slack user {volunteer} even after cache refresh"
            )

            failed.append(volunteer)
            continue

        # Figure out if this addition unlocked any rewards
        # Monthly

        # Get the hours for the month in question
        current_hours = get_specific_month(
            tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours, month=volunteer_date
        )

        # Skip reward checks if we're adding debt
        if not debt:
            for reward in rewards["monthly"]:
                if current_hours < reward <= current_hours + hours:
                    # Let the volunteer know
                    slack_misc.send_dm(
                        slack_id=volunteer,
                        slack_app=app,
                        message=f"Congratulations! You've unlocked the monthly reward: *{rewards['monthly'][reward]['title']}* for volunteering {reward} hours in {volunteer_date.strftime('%B')}{year_str}!",
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
                            text=f":tada: <@{volunteer}> has unlocked the monthly reward: *{rewards['monthly'][reward]['title']}* for volunteering {reward} hours in {volunteer_date.strftime('%B')}{year_str}!",
                        )

                    # Check if there's a reward function to call
                    if "function" in rewards["monthly"][reward]:
                        reward_func = rewards_util.get_reward_function(
                            rewards["monthly"][reward]["function"]
                        )
                        if reward_func:
                            try:
                                reward_outcome = reward_func(
                                    tidyhq_id=tidyhq_id,
                                    timestamp=volunteer_date,
                                    tidyhq_cache=tidyhq_cache,
                                    config=config,
                                )
                            except Exception as e:
                                logging.error(
                                    f"Reward function {rewards['monthly'][reward]['function']} failed for TidyHQ ID {tidyhq_id}: {e}"
                                )
                                reward_outcome = False

                            if not reward_outcome:
                                logging.error(
                                    f"Reward function {rewards['monthly'][reward]['function']} failed for TidyHQ ID {tidyhq_id}"
                                )

                                # Let the admin channel know
                                if "admin_channel" in config["slack"]:
                                    app.client.chat_postMessage(
                                        channel=config["slack"]["admin_channel"],
                                        text=f":warning: Reward function *{rewards['monthly'][reward]['function']}* failed for <@{volunteer}> (TidyHQ ID {tidyhq_id})",
                                    )

            # Cumulative
            current_hours = get_total(
                tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
            )
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

                    # Check if there's a reward function to call
                    if "function" in rewards["cumulative"][reward]:
                        reward_func = rewards_util.get_reward_function(
                            rewards["cumulative"][reward]["function"]
                        )
                        if reward_func:
                            try:
                                reward_outcome = reward_func(
                                    tidyhq_id=tidyhq_id,
                                    timestamp=volunteer_date,
                                    tidyhq_cache=tidyhq_cache,
                                    config=config,
                                )
                            except Exception as e:
                                logging.error(
                                    f"Reward function {rewards['cumulative'][reward]['function']} failed for TidyHQ ID {tidyhq_id}: {e}"
                                )
                                reward_outcome = False

                            if not reward_outcome:
                                logging.error(
                                    f"Reward function {rewards['cumulative'][reward]['function']} failed for TidyHQ ID {tidyhq_id}"
                                )

                                # Let the admin channel know
                                if "admin_channel" in config["slack"]:
                                    app.client.chat_postMessage(
                                        channel=config["slack"]["admin_channel"],
                                        text=f":warning: Reward function *{rewards['cumulative'][reward]['function']}* failed for <@{volunteer}> (TidyHQ ID {tidyhq_id})",
                                    )

        volunteer_hours = add_hours(
            tidyhq_id=tidyhq_id,
            volunteer_date=volunteer_date,
            hours_volunteered=hours,
            volunteer_hours=volunteer_hours,
            tidyhq_cache=tidyhq_cache,
            debt=debt,
        )

        logging.info(
            f"Added {hours} hours on {volunteer_date} for TidyHQ ID {tidyhq_id} (Slack ID {volunteer}) {'(Note: ' + note + ')' if note else ''} {'as debt' if debt else ''}"
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
        note_add = f' with the note "{note}"' if note else ""

        # No need to @ the person if they're the one adding time
        address = "<@{user_id}>" if volunteer != user_id else "You"

        if debt:
            message = f"{address} added {h_format(hours)} of time debt against your profile for {volunteer_date.strftime('%B')}{year_str}{note_add}."
            current_debt = get_debt(
                tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
            )
            if current_debt > 0:
                message += f" You now have a total time debt of {h_format(current_debt)}. Please remember to repay this debt by volunteering before undertaking further training."
        else:
            message = f"{address} added {h_format(hours)} against your profile for {volunteer_date.strftime('%B')}{year_str}{note_add}. Thank you for helping out!{"\nThere's no need to add tokens to the tub for these hours, they're already recorded." if volunteer != user_id else ''}"

        slack_misc.send_dm(
            slack_id=volunteer,
            slack_app=app,
            message=message,
        )

    # Let the admin channel know how we went
    note_add = f"\nNote: {note}" if note else ""

    if successful and send_to_channel:
        user_list = ""
        for volunteer in successful:
            user_list += f", <@{volunteer}> ({h_format(changes[volunteer])})"
        user_list = user_list[2:]

        app.client.chat_postMessage(
            channel=config["slack"]["admin_channel"],
            text=f"{':chart_with_downwards_trend:' if debt else ':chart_with_upwards_trend:'} <@{user_id}> added {'debt' if debt else 'hours'} for {volunteer_date.strftime('%B')}{year_str}: {user_list}{note_add}",
        )

    if failed:
        for volunteer in failed:
            m = app.client.chat_postMessage(
                channel=config["slack"]["admin_channel"],
                text=f":warning: Could not add {changes[volunteer]:,g}h to <@{volunteer}>, they're not registered on TidyHQ or they're not linked. (Attempted by <@{user_id}>){note_add}",
            )
            app.client.pins_add(
                channel=config["slack"]["admin_channel"], timestamp=m["ts"]
            )

    return tidyhq_cache


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


def get_all_debt(volunteer_hours: dict) -> list:
    """Get all volunteers with time debt, sorted by total debt (descending)."""

    volunteers_with_debt = []

    for tidyhq_id, volunteer_data in volunteer_hours.items():
        total_hours = get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)
        debt = volunteer_data.get("debt", 0)
        if debt > total_hours:
            volunteers_with_debt.append(
                {
                    "tidyhq_id": tidyhq_id,
                    "name": volunteer_data["name"],
                    "total_debt": debt,
                }
            )

    # Sort by total debt (descending)
    volunteers_with_debt.sort(key=lambda x: x["total_debt"], reverse=True)
    return volunteers_with_debt


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


def get_hour_streaks(volunteer_hours: dict) -> dict:
    """Calculate volunteering streaks for each volunteer."""

    streaks = {}

    for tidyhq_id, volunteer_data in volunteer_hours.items():
        months = sorted(volunteer_data["months"].keys())
        longest_streak = 0
        current_streak = 0
        previous_month = None

        for month_str in months:
            if volunteer_data["months"][month_str] > 0:
                month_date = datetime.strptime(month_str, "%Y-%m")
                if previous_month:
                    # Check if this month is consecutive to the previous month
                    if (
                        month_date.year == previous_month.year
                        and month_date.month == previous_month.month + 1
                    ) or (
                        month_date.year == previous_month.year + 1
                        and month_date.month == 1
                        and previous_month.month == 12
                    ):
                        current_streak += 1
                    else:
                        current_streak = 1
                else:
                    current_streak = 1

                previous_month = month_date

                if current_streak > longest_streak:
                    longest_streak = current_streak
            else:
                current_streak = 0
                previous_month = None

        streaks[tidyhq_id] = {
            "name": volunteer_data["name"],
            "longest_streak": longest_streak,
            "current_streak": current_streak,
        }

    return streaks


def get_volunteer_badge_streaks(volunteer_hours: dict) -> dict:
    """Calculate badge streaks for each volunteer.

    A badge streak is defined as having volunteered at least ten hours in a month.
    """

    badge_streaks = {}

    for tidyhq_id, volunteer_data in volunteer_hours.items():
        months = sorted(volunteer_data["months"].keys())
        longest_badge_streak = 0
        current_badge_streak = 0
        previous_month = None

        for month_str in months:
            if volunteer_data["months"][month_str] >= 10:
                month_date = datetime.strptime(month_str, "%Y-%m")
                if previous_month:
                    # Check if this month is consecutive to the previous month
                    if (
                        month_date.year == previous_month.year
                        and month_date.month == previous_month.month + 1
                    ) or (
                        month_date.year == previous_month.year + 1
                        and month_date.month == 1
                        and previous_month.month == 12
                    ):
                        current_badge_streak += 1
                    else:
                        current_badge_streak = 1
                else:
                    current_badge_streak = 1

                previous_month = month_date

                if current_badge_streak > longest_badge_streak:
                    longest_badge_streak = current_badge_streak
            else:
                current_badge_streak = 0
                previous_month = None

        badge_streaks[tidyhq_id] = {
            "name": volunteer_data["name"],
            "longest_streak": longest_badge_streak,
            "current_streak": current_badge_streak,
        }

    return badge_streaks


def h_format(hours: int | float) -> str:
    """Format hours with 'h'/'m' suffix as appropriate"""

    if hours > 1:
        return f"{hours:,g}h"
    return f"{round(int(hours * 60), 0):,g}m"
