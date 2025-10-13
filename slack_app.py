import json
import logging
import sys
from copy import deepcopy as copy
from datetime import datetime
from pprint import pprint

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.context.ack.ack import Ack as slack_ack
from slack_bolt.context.respond.respond import Respond as slack_respond
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse

from editable_resources import strings
from slack import block_formatters, blocks
from slack import misc as slack_misc
from util import tidyhq, hours


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("app.log", mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)
# Set urllib3 logging level to INFO to reduce noise when individual modules are set to debug
urllib3_logger = logging.getLogger("urllib3")
urllib3_logger.setLevel(logging.INFO)
# Set slack bolt logging level to INFO to reduce noise when individual modules are set to debug
slack_logger = logging.getLogger("slack")
slack_logger.setLevel(logging.WARN)
setup_logger = logging.getLogger("setup")
logger = logging.getLogger("slack_app")
response_logger = logging.getLogger("response")

setup_logger.info("Application starting")

# Load config
try:
    with open("config.json") as f:
        config: dict = json.load(f)
except FileNotFoundError:
    setup_logger.error(
        "config.json not found. Create it using example.config.json as a template"
    )
    sys.exit(1)


# Set up TidyHQ cache
tidyhq_cache = tidyhq.fresh_cache(config=config)
setup_logger.info(
    f"TidyHQ cache set up: {len(tidyhq_cache['contacts'])} contacts, {len(tidyhq_cache['groups'])} groups"
)
# Write cache to file
with open("cache.json", "w") as f:
    json.dump(tidyhq_cache, f, indent=4)

# Load volunteer hours

try:
    with open("hours.json") as f:
        volunteer_hours = json.load(f)
except FileNotFoundError:
    setup_logger.warning(
        "hours.json not found. Application will exit to prevent data loss."
    )
    setup_logger.warning(
        "Create a blank ({}) hours.json file if this is the first run."
    )
    sys.exit(1)

logger.info(f"Loaded volunteer hours for {len(volunteer_hours)} volunteers")

# Load reward tiers
try:
    with open("rewards.json") as f:
        rewards = json.load(f)
except FileNotFoundError:
    setup_logger.warning("rewards.json not found.")
    sys.exit(1)

# Convert reward keys to integers and sort
for reward_type in rewards:
    rewards[reward_type] = {int(k): v for k, v in rewards[reward_type].items()}
    rewards[reward_type] = dict(sorted(rewards[reward_type].items()))

logger.info(
    f"Loaded {len(rewards['monthly'])} monthly reward tiers and {len(rewards['cumulative'])} all time reward tiers"
)

# Set up slack app
app = App(token=config["slack"]["bot_token"], logger=slack_logger)

# Get the ID for our team via the API
auth_test = app.client.auth_test()
slack_team_id: str = auth_test["team_id"]  # type: ignore
slack_bot_id = auth_test["bot_id"]
slack_workspace_title = app.client.team_info()["team"]["name"]  # type: ignore

logger.info(
    f"Connected to Slack workspace '{slack_workspace_title}' as bot ID {slack_bot_id}"
)

# Function naming scheme
# ignore_ - Acknowledge the event but do nothing
# handle_ - Acknowledge the event and do something
# modal_ - Open a modal
# submodal_ - Open a submodal


# Event listener for messages that mention the bot
@app.event("app_mention")
def ignore_app_mention(ack: slack_ack) -> None:
    """Dummy function to acknowledge the mention"""
    ack()


@app.event("app_home_opened")
def handle_app_home_opened_events(body: dict) -> None:
    """Regenerate the app home when it's opened by a user"""
    user_id = body["event"]["user"]

    logger.info(f"App home opened by user {user_id}")

    global tidyhq_cache
    tidyhq_cache = tidyhq.fresh_cache(config=config, cache=tidyhq_cache)

    tidyhq_id = tidyhq.map_slack_to_tidyhq(
        tidyhq_cache=tidyhq_cache, config=config, slack_id=user_id
    )

    if tidyhq_id:
        global volunteer_hours

        # Generate new just passes back the existing data if the user already exists
        volunteer_hours = hours.generate_new(
            tidyhq_id=tidyhq_id,
            volunteer_hours=volunteer_hours,
            tidyhq_cache=tidyhq_cache,
        )

    slack_misc.push_home(
        user_id=user_id,
        config=config,
        tidyhq_cache=tidyhq_cache,
        slack_app=app,
        volunteer_hours=volunteer_hours,
        rewards=rewards,
    )


@app.action("add_hours")
def modal_add_hours(ack: slack_ack, body: dict) -> None:
    ack()

    block_list = block_formatters.modal_add_hours()

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "submit_hours",
            "title": {"type": "plain_text", "text": "Add Volunteer Hours"},
            "submit": {"type": "plain_text", "text": "Add"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": block_list,
        },
    )


@app.action("add_debt")
def modal_add_debt(ack: slack_ack, body: dict) -> None:
    ack()

    block_list = block_formatters.modal_add_hours(debt=True)

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "submit_hours_debt",
            "title": {"type": "plain_text", "text": "Add Time Debt"},
            "submit": {"type": "plain_text", "text": "Add"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": block_list,
        },
    )


@app.action("self_log")
def modal_self_log(ack: slack_ack, body: dict) -> None:
    ack()

    block_list = block_formatters.modal_add_hours(
        mode="self", user_id=body["user"]["id"]
    )

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "submit_hours",
            "title": {"type": "plain_text", "text": "Add Volunteer Hours"},
            "submit": {"type": "plain_text", "text": "Add"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": block_list,
        },
    )


@app.action("view_as_user")
def modal_view_as_user(ack: slack_ack, body: dict) -> None:
    ack()

    block_list = block_formatters.modal_view_as_user()

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "view_as_user",
            "title": {"type": "plain_text", "text": "View as User"},
            "submit": {"type": "plain_text", "text": "View"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": block_list,
        },
    )


@app.action("bulk_add_hours")
def modal_bulk_add_hours(ack: slack_ack, body: dict) -> None:
    ack()

    block_list = block_formatters.modal_bulk_add_hours()

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "submit_bulk_hours",
            "title": {"type": "plain_text", "text": "Bulk Add Volunteer Hours"},
            "submit": {"type": "plain_text", "text": "Add"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": block_list,
        },
    )


@app.view("submit_bulk_hours")
def handle_bulk_hours_submission(ack: slack_ack, body: dict) -> None:
    ack()

    global tidyhq_cache

    # Collate changes to make
    count = 1
    changes = {}

    data = body["view"]["state"]["values"]
    user_id = body["user"]["id"]

    date_raw = data["date_select"]["date_select"]["selected_date"]
    date = datetime.strptime(date_raw, "%Y-%m-%d")
    note = data["note_input"]["note_input"].get("value", "")

    while count <= 10:
        volunteers = data[f"volunteer_select_{count}"][f"volunteer_select_{count}"][
            "selected_users"
        ]
        if not volunteers:
            count += 1
            continue
        hours_volunteered = float(
            data[f"hours_input_{count}"][f"hours_input_{count}"].get("value", 0)
        )
        if not hours_volunteered:
            count += 1
            continue

        for volunteer in volunteers:
            if volunteer not in changes:
                changes[volunteer] = 0

            changes[volunteer] += hours_volunteered

        count += 1

    tidyhq_cache = hours.add_hours_with_notifications(
        changes=changes,
        tidyhq_cache=tidyhq_cache,
        volunteer_hours=volunteer_hours,
        volunteer_date=date,
        note=note,
        rewards=rewards,
        config=config,
        app=app,
        user_id=user_id,
    )


@app.view("submit_hours")
def handle_hours_submission(ack: slack_ack, body: dict) -> None:
    ack()

    global volunteer_hours, tidyhq_cache

    user_id = body["user"]["id"]

    data = body["view"]["state"]["values"]

    volunteers = data["volunteer_select"]["volunteer_select"]["selected_users"]
    hours_volunteered = float(data["hours_input"]["hours_input"]["value"])
    date_raw = data["date_select"]["date_select"]["selected_date"]
    date = datetime.strptime(date_raw, "%Y-%m-%d")
    note = data["note_input"]["note_input"].get("value", "")

    logging.info(
        f"Adding {hours_volunteered} hours on {date} for {', '.join(volunteers)} from {user_id}"
    )

    # Format data in a way hours.add_hours_with_notifications can use
    changes = {}
    for volunteer in volunteers:
        changes[volunteer] = hours_volunteered

    tidyhq_cache = hours.add_hours_with_notifications(
        changes=changes,
        tidyhq_cache=tidyhq_cache,
        volunteer_hours=volunteer_hours,
        volunteer_date=date,
        note=note,
        rewards=rewards,
        config=config,
        app=app,
        user_id=user_id,
    )


@app.view("submit_hours_debt")
def handle_debt_submission(ack: slack_ack, body: dict) -> None:
    ack()

    global volunteer_hours, tidyhq_cache

    user_id = body["user"]["id"]

    data = body["view"]["state"]["values"]

    volunteers = data["volunteer_select"]["volunteer_select"]["selected_users"]
    hours_volunteered = float(data["hours_input"]["hours_input"]["value"])
    date_raw = data["date_select"]["date_select"]["selected_date"]
    date = datetime.strptime(date_raw, "%Y-%m-%d")
    note = data["note_input"]["note_input"].get("value", "")

    logging.info(
        f"Adding {hours_volunteered} hours on {date} for {', '.join(volunteers)} from {user_id} (as debt)"
    )

    # Format data in a way hours.add_hours_with_notifications can use
    changes = {}
    for volunteer in volunteers:
        changes[volunteer] = hours_volunteered

    tidyhq_cache = hours.add_hours_with_notifications(
        changes=changes,
        tidyhq_cache=tidyhq_cache,
        volunteer_hours=volunteer_hours,
        volunteer_date=date,
        note=note,
        rewards=rewards,
        config=config,
        app=app,
        user_id=user_id,
        debt=True,
    )


@app.action("admin_statistics")
def modal_admin_statistics(ack: slack_ack, body: dict) -> None:
    ack()

    block_list = block_formatters.modal_statistics(
        volunteer_hours, config, tidyhq_cache
    )

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "Volunteer Statistics"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": block_list,
        },
    )


@app.action("user_statistics")
def modal_user_statistics(ack: slack_ack, body: dict) -> None:
    ack()

    # Get the tidyhq id from the button value
    tidyhq_id = body["actions"][0]["value"]

    block_list = block_formatters.modal_user_statistics(
        tidyhq_id=tidyhq_id,
        volunteer_hours=volunteer_hours,
    )

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "Volunteering Stats"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": block_list,
        },
    )


@app.view("view_as_user")
def handle_view_as_user_selection(ack: slack_ack, body: dict) -> None:
    ack()

    user_id = body["user"]["id"]

    try:
        data = body["view"]["state"]["values"]

        # Get the selected user
        selected_user_id = data["user_select"]["user_select"]["selected_user"]

        if not selected_user_id:
            logging.error(f"No user selected by admin {user_id}")
            return

        logging.info(f"Admin {user_id} viewing as user {selected_user_id}")

        # Generate the statistic blocks for the selected user
        tidyhq_id = tidyhq.map_slack_to_tidyhq(
            tidyhq_cache=tidyhq_cache, config=config, slack_id=selected_user_id
        )

        stat_blocks = []
        if tidyhq_id:
            stat_blocks = block_formatters.modal_user_statistics(
                tidyhq_id=tidyhq_id,
                volunteer_hours=volunteer_hours,
                header=False,
            )

        # Generate the reward blocks for the selected user
        reward_blocks = block_formatters.app_home(
            user_id=selected_user_id,
            config=config,
            tidyhq_cache=tidyhq_cache,
            volunteer_hours=volunteer_hours,
            rewards=rewards,
            modal_version=True,
        )

        # Get user name for modal title
        user_name = slack_misc.name_mapper(slack_id=selected_user_id, slack_app=app)

        # Trim the title to 24 characters if it's too long
        if len(user_name) > 24:
            user_name = user_name[:21] + "..."

        # Open a new modal with the user's dashboard
        app.client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": user_name},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": stat_blocks + blocks.divider + reward_blocks,
            },
        )

    except Exception as e:
        logging.error(f"Error in view as user modal: {e}")


# Listen for messages in the training channel
@app.event("message")
def handle_training_tracker_messages(ack, body: dict) -> None:
    ack()

    global volunteer_hours, tidyhq_cache

    # Limit to only messages with the correct metadata
    if "metadata" not in body["event"]:
        return

    # Training additions
    if body["event"]["metadata"].get("event_type") == "training_add":
        # Limit to messages for the right group ID
        if body["event"]["metadata"]["event_payload"].get("machine") != str(
            config["tidyhq"]["trigger_group"]
        ):
            return

        logging.info("Training log message received")

        block_list = block_formatters.welcome_message()

        # Get the slack ID of the user based on their tidyhq ID
        tidyhq_id = body["event"]["metadata"]["event_payload"].get("operator")
        slack_id = tidyhq.map_tidyhq_to_slack(
            tidyhq_cache=tidyhq_cache, config=config, contact_id=tidyhq_id
        )

        if slack_id:
            # Send welcome message to user
            slack_misc.send_dm(
                slack_id=slack_id,
                blocks=block_list,
                slack_app=app,
                message="Welcome to the volunteer token system!",
            )

            # Send a threaded message to the training channel confirming the message was sent
            app.client.chat_postMessage(
                channel=config["slack"].get("training_channel"),
                text=f"Welcome message sent to <@{slack_id}>",
                thread_ts=body["event"].get("ts"),
            )

    # Debt additions
    if body["event"]["metadata"].get("event_type") == "time_debt":
        logging.info("Time debt log message received")

        tidyhq_id = body["event"]["metadata"]["event_payload"].get("tidyhq_id")
        slack_id = body["event"]["metadata"]["event_payload"].get("slack_id")
        trainer = body["event"]["metadata"]["event_payload"].get("trainer")

        if not slack_id:
            slack_id = tidyhq.map_tidyhq_to_slack(
                tidyhq_cache=tidyhq_cache, config=config, contact_id=tidyhq_id
            )

        debt = float(body["event"]["metadata"]["event_payload"].get("hours", 0))

        if slack_id:
            changes = {slack_id: debt}

            tidyhq_cache = hours.add_hours_with_notifications(
                changes=changes,
                tidyhq_cache=tidyhq_cache,
                volunteer_hours=volunteer_hours,
                volunteer_date=datetime.now(),
                note="Training Tracker",
                rewards=rewards,
                config=config,
                app=app,
                user_id=trainer,
                debt=True,
                send_to_channel=False,
            )

            # Send a threaded message to the training channel confirming the message was processed
            volunteer_date = datetime.now()
            app.client.chat_postMessage(
                channel=config["slack"].get("admin_channel"),
                text=f":chart_with_downwards_trend: <@{trainer}> added debt for {volunteer_date.strftime('%B')}: <@{slack_id}> ({debt}h)\n(Note: Training Tracker)",
                thread_ts=body["event"].get("ts"),
                reply_broadcast=True,
            )

        else:
            app.client.chat_postMessage(
                channel=config["slack"].get("admin_channel"),
                text=f":warning: Could not add {debt}h to user, they're not registered on TidyHQ or they're not linked. (Attempted by <@{trainer}>)",
                thread_ts=body["event"].get("ts"),
                reply_broadcast=True,
            )


# The cron mode renders the app home for every user in the workspace and resets filters
if "--cron" in sys.argv:
    # Update homes for all slack users
    logger.info("Updating homes for all users")

    # Get a list of all users from slack
    slack_response = app.client.users_list()
    slack_users = []
    while slack_response.data.get("response_metadata", {}).get("next_cursor"):  # type: ignore
        slack_users += slack_response.data["members"]  # type: ignore
        slack_response = app.client.users_list(
            cursor=slack_response.data["response_metadata"]["next_cursor"]  # type: ignore
        )
    slack_users += slack_response.data["members"]  # type: ignore

    users = []

    # Convert slack response to list of users since it comes as an odd iterable
    for user in slack_users:
        if user["is_bot"] or user["deleted"]:
            continue
        users.append(user)
    logger.info(f"Found {len(users)} users")

    x = 1

    home_no_tidyhq = None

    updates = {}

    def gen_home(user_id: str, x: int, home_no_tidyhq: list) -> tuple[str, list]:
        tidyhq_id = tidyhq.map_slack_to_tidyhq(
            tidyhq_cache=tidyhq_cache, config=config, slack_id=user_id
        )
        if not tidyhq_id and not home_no_tidyhq:
            home_no_tidyhq = block_formatters.app_home(
                user_id=user_id,
                config=config,
                tidyhq_cache=tidyhq_cache,
                volunteer_hours=volunteer_hours,
                rewards=rewards,
            )
        if tidyhq_id:
            block_list = block_formatters.app_home(
                user_id=user_id,
                config=config,
                tidyhq_cache=tidyhq_cache,
                volunteer_hours=volunteer_hours,
                rewards=rewards,
            )
            logger.info(
                f"{x}/{len(users)} {user_id}: Generating home for user {tidyhq_id}"
            )
        else:
            block_list = home_no_tidyhq
            logger.info(
                f"{x}/{len(users)} {user_id}: Generating generalised home for non-TidyHQ user"
            )
        return user_id, block_list

    x = 1
    user_id, home_no_tidyhq = gen_home(users[2]["id"], x, [])

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = []
        for user in users:
            user_id = user["id"]
            futures.append(
                executor.submit(
                    gen_home,
                    user_id=user_id,
                    x=x,
                    home_no_tidyhq=home_no_tidyhq,
                )
            )
            x += 1

        for future in as_completed(futures):
            try:
                user_id, block_list = future.result()
                updates[user_id] = block_list
                logger.info(f"Generated app home for {user_id}")
            except Exception as e:
                logger.error(f"Error updating home: {e}")

    x = 1

    input("Ready for next step...")

    threads = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for user_id in updates:
            print(len(updates[user_id]))
            futures.append(
                executor.submit(
                    slack_misc.push_home,
                    config=config,
                    tidyhq_cache=tidyhq_cache,
                    slack_app=app,
                    block_list=updates[user_id],
                    user_id=user_id,
                    volunteer_hours=volunteer_hours,
                    rewards=rewards,
                )
            )

        for future in as_completed(futures):
            try:
                future.result()
                x += 1
                logger.info(f"Updated home for {user_id} ({x}/{len(users)})")
            except Exception as e:
                logger.error(f"Error updating home: {e}")

    logger.info(f"All homes updated ({x - 1})")
    sys.exit(0)


# Start the app
if __name__ == "__main__":
    handler = SocketModeHandler(app, config["slack"]["app_token"])
    handler.start()
