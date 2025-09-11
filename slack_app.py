import importlib
import json
import logging
import re
import sys
import time
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
    setup_logger.warning("hours.json not found.")
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


# Event listener for direct messages to the bot
@app.event("message")
def ignore_message(ack: slack_ack) -> None:
    """Ignore messages sent to the bot"""
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
def modal_add_hours(ack, body):
    ack()

    blocks = block_formatters.modal_add_hours()

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "submit_hours",
            "title": {"type": "plain_text", "text": "Add Volunteer Hours"},
            "submit": {"type": "plain_text", "text": "Add"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": blocks,
        },
    )


@app.view("submit_hours")
def handle_hours_submission(ack, body):
    ack()
    # pprint(body)

    global volunteer_hours

    user_id = body["user"]["id"]

    data = body["view"]["state"]["values"]

    volunteers = data["volunteer_select"]["volunteer_select"]["selected_users"]
    hours_volunteered = int(data["hours_input"]["hours_input"]["value"])
    date_raw = data["date_select"]["date_select"]["selected_date"]
    date = datetime.strptime(date_raw, "%Y-%m-%d")

    logging.info(
        f"Adding {hours_volunteered} hours on {date} for {', '.join(volunteers)} from {user_id}"
    )

    successful = []
    failed = []

    for volunteer in volunteers:
        tidyhq_id = tidyhq.map_slack_to_tidyhq(
            tidyhq_cache=tidyhq_cache, config=config, slack_id=volunteer
        )
        if not tidyhq_id:
            logging.warning(f"Could not find TidyHQ ID for Slack user {volunteer}")

            # Let the admin know
            failed.append(volunteer)
            continue

        volunteer_hours = hours.add_hours(
            tidyhq_id=tidyhq_id,
            volunteer_date=date,
            hours_volunteered=hours_volunteered,
            volunteer_hours=volunteer_hours,
            tidyhq_cache=tidyhq_cache,
        )

        logging.info(
            f"Added {hours_volunteered} hours on {date} for TidyHQ ID {tidyhq_id} (Slack ID {volunteer})"
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
            message=f"<@{user_id}> added {volunteer_hours}h against your profile for {date.strftime('%B')}. Thank you for helping out!\nThere's no need to add tokens to the tub for these hours, they're already recorded.",
        )

    # Let the admin know how we went
    if successful:
        user_list = ""
        for volunteer in successful:
            user_list += ", <@{volunteer}>"
        user_list = user_list[2:]
        slack_misc.send_dm(
            slack_id=user_id,
            slack_app=app,
            message=f"Added {hours_volunteered}h to {user_list}.",
        )
    if failed:
        user_list = ""
        for volunteer in failed:
            user_list += ", <@{volunteer}>"
        user_list = user_list[2:]
        slack_misc.send_dm(
            slack_id=user_id,
            slack_app=app,
            message=f"Could not add {hours_volunteered}h to {user_list}, they're not registered on TidyHQ or they're not linked.",
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
                private_metadata=None,
                volunteer_hours=volunteer_hours,
                rewards=rewards,
            )
        if tidyhq_id:
            block_list = block_formatters.app_home(
                user_id=user_id,
                config=config,
                tidyhq_cache=tidyhq_cache,
                private_metadata=None,
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

    private_metadata = None

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
                    private_metadata=private_metadata,
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
