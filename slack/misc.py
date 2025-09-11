import json
import logging
from pprint import pprint

import jsonschema
import mistune

from slack import block_formatters
import slack_bolt as bolt
import slack_sdk.errors

# Set up logging
logger = logging.getLogger("slack.misc")
logger.setLevel(logging.INFO)


class mrkdwn_renderer(mistune.HTMLRenderer):
    def paragraph(self, text: str) -> str:
        return text + "\n"

    def heading(self, text: str, level: int) -> str:
        return f"*{text}*\n"

    def list(self, body, ordered, level: int, start=None):  # type: ignore
        return body

    def list_item(self, text: str, level: int) -> str:
        return f"• {text}\n"

    def block_quote(self, text: str) -> str:
        quoted_lines = [f"> {line}" for line in text.split("\n")[:-1]]
        return "\n".join(quoted_lines) + "\n"

    def codespan(self, text: str) -> str:
        return f"`{text}`"

    def link(self, link: str, title: str, text: str) -> str:
        return f"<{link}|{title}>"

    def strong(self, text: str) -> str:
        return f"*{text}*"

    def emphasis(self, text: str) -> str:
        return f"_{text}_"


mrkdwnconvert = mistune.create_markdown(renderer=mrkdwn_renderer())


def convert_markdown(text: str) -> str:
    """Convert normal markdown to slack markdown"""
    text = text.replace("<br>", "\n")
    result = mrkdwnconvert(text)
    result = result.strip()
    # Remove <p> tags
    result = result.replace("<p>", "").replace("</p>", "")
    return result


def validate(blocks: list, surface: str | None = "modal") -> bool:
    """Validate whether a block list is valid for a given surface type"""

    if surface not in ["modal", "home", "message", "msg"]:
        raise ValueError(f"Invalid surface type: {surface}")
    # We want our own logger for this function
    schemalogger = logging.getLogger("block-kit validator")

    if surface in ["modal", "home"] and len(blocks) > 100:
        schemalogger.error(f"Block list too long {len(blocks)}/100")
        return False
    elif surface in ["message", "msg"] and len(blocks) > 50:
        schemalogger.error(f"Block list too long {len(blocks)}/50")
        return False

    # Recursively search for all fields called "text" and ensure they don't have an empty string
    for block in blocks:
        if not check_for_empty_text(block, schemalogger):
            return False

    # Load the schema from file
    with open("block-kit-schema.json") as f:
        schema = json.load(f)

    try:
        jsonschema.validate(instance=blocks, schema=schema)
    except jsonschema.exceptions.ValidationError as e:  # type: ignore
        schemalogger.error(e)
        return False
    return True


def check_for_empty_text(block: dict, logger: logging.Logger) -> bool:
    """Recursively search for all fields called "text" and ensure they don't have an empty string

    Slack blocks with empty text fields will be kicked back with an error and this isn't caught by the schema used in validate()
    """
    for key, value in block.items():
        if key == "text" and value == "":
            logger.error(f"Empty text field found in block {block}")
            return False
        if isinstance(value, dict):
            if not check_for_empty_text(value, logger):
                return False
    return True


def push_home(
    user_id: str,
    config: dict,
    tidyhq_cache: dict,
    slack_app: bolt.App,
    volunteer_hours: dict,
    rewards: dict,
    block_list: list | None = None,
) -> bool:
    """Push the app home view to a specified user.

    Pass in a block_list to avoid regenerating the home view.
    """
    # Generate the app home view
    if block_list is None:
        block_list = block_formatters.app_home(
            user_id=user_id,
            config=config,
            tidyhq_cache=tidyhq_cache,
            volunteer_hours=volunteer_hours,
            rewards=rewards,
        )

    view = {
        "type": "home",
        "blocks": block_list,
    }

    try:
        slack_app.client.views_publish(user_id=user_id, view=view)
        logger.info(f"Set app home for {user_id} - {len(block_list)} blocks")
        return True
    except Exception as e:
        logger.error(f"Failed to push home view: {e}")
        pprint(block_list)
        return False


def name_mapper(slack_id: str, slack_app: bolt.App) -> str:
    """
    Returns the slack name(s) of a user given their ID
    """

    slack_id = slack_id.strip()

    # Catch edge cases caused by parsing
    if slack_id == "Unknown":
        return "Unknown"
    elif "No one" in slack_id:
        return "No one"
    elif slack_id == "":
        return ""

    # Check if there's multiple IDs
    if "," in slack_id:
        names = []
        for id in slack_id.split(","):
            names.append(name_mapper(id, slack_app))
        return ", ".join(names)

    try:
        user_info = slack_app.client.users_info(user=slack_id)
    except slack_sdk.errors.SlackApiError as e:  # type: ignore
        logger.error(f"Failed to get user info for {slack_id}")
        logger.error(e)
        return slack_id

    # Real name is best
    if user_info["user"].get("real_name", None):  # type: ignore
        return user_info["user"]["real_name"]  # type: ignore

    # Display is okay
    return user_info["user"]["profile"]["display_name"]  # type: ignore


def send_dm(
    slack_id: str,
    message: str,
    slack_app: bolt.App,
    blocks: list = [],
    unfurl_links: bool = False,
    unfurl_media: bool = False,
    username: str | None = None,
    photo: str | None = None,
    pin: bool = False,
) -> bool:
    """
    Send a direct message to a user including conversation creation
    """

    # Create a conversation
    try:
        conversation_id = slack_app.client.conversations_open(users=[slack_id])[
            "channel"
        ]["id"]  # type: ignore
    except slack_sdk.errors.SlackApiError as e:  # type: ignore
        logger.error(f"Failed to open conversation with {slack_id}")
        logger.error(e)
        return False

    # Photos are currently bugged for DMs
    photo = None

    # Send the message
    try:
        m = slack_app.client.chat_postMessage(
            channel=conversation_id,
            text=message,
            blocks=blocks,
            unfurl_links=unfurl_links,
            unfurl_media=unfurl_media,
            username=username,
            icon_url=photo,
        )

    except slack_sdk.errors.SlackApiError as e:  # type: ignore
        logger.error(f"Failed to send message to {slack_id}")
        logger.error(e)
        return False

    if not m["ok"]:
        logger.error(f"Failed to send message to {slack_id}")
        logger.error(m)
        return False

    if pin:
        slack_app.client.pins_add(channel=conversation_id, timestamp=m["ts"])

    logger.info(f"Sent message to {slack_id}")
    return True
