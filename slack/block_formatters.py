import logging
from copy import deepcopy as copy
from datetime import datetime, timedelta
from pprint import pprint

from editable_resources import strings
from slack import blocks, block_formatters
from util import tidyhq, misc, hours

# Set up logging
logger = logging.getLogger("slack.block_formatters")


def inject_text(block_list: list, text: str) -> list[dict]:
    """Injects text into the last block in the block list and returns the updated list.

    Is aware of most block types and should inject in the appropriate place
    """

    block_list = copy(block_list)
    if block_list[-1]["type"] in ["section", "header", "button"]:
        block_list[-1]["text"]["text"] = text
    elif block_list[-1]["type"] in ["context"]:
        block_list[-1]["elements"][0]["text"] = text
    elif block_list[-1]["type"] == "modal":
        block_list[-1]["title"]["text"] = text
    elif block_list[-1]["type"] == "rich_text":
        block_list[-1]["elements"][0]["elements"][0]["text"] = text

    return block_list


def add_block(block_list: list, block: dict | list) -> list[dict]:
    """Adds a block to the block list and returns the updated list.

    Performs a deep copy to avoid modifying anything in the original list.
    """
    block = copy(block)
    block_list = copy(block_list)
    if isinstance(block, list):
        block_list += block
    elif isinstance(block, dict):
        block_list.append(block)

    if len(block_list) > 100:
        logger.info(f"Block list too long {len(block_list)}/100")

    return block_list


def compress_blocks(block_list: list[dict]) -> list:
    """Compresses a list of blocks by removing dividers"""

    compressed_blocks = []

    # Remove dividers
    for block in block_list:
        if block["type"] != "divider":
            compressed_blocks.append(block)
    logging.debug(f"Blocks reduced from {len(block_list)} to {len(compressed_blocks)}")

    return compressed_blocks


def app_home(
    user_id: str,
    config: dict,
    tidyhq_cache: dict,
    volunteer_hours: dict,
    rewards: dict,
    modal_version: bool = False,
) -> list:
    """Generate the blocks for the app home view for a specified user and return it as a list of blocks."""
    # Check if the user has a Taiga account

    block_list = []
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text=strings.header
    )

    # Get the TidyHQ ID for the user
    tidyhq_id = tidyhq.map_slack_to_tidyhq(
        tidyhq_cache=tidyhq_cache, slack_id=user_id, config=config
    )

    if not tidyhq_id:
        block_list = block_formatters.add_block(block_list, blocks.text)
        block_list = block_formatters.inject_text(
            block_list=block_list, text=strings.unrecognised
        )

        return block_list

    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=strings.explainer,
    )

    # Get the user's total hours
    total_hours = hours.get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)

    # Get the user's hours for last month
    last_month_hours = hours.get_last_month(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
    )
    this_month_hours = hours.get_current_month(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
    )

    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=strings.hours_summary.format(
            last_month=last_month_hours,
            total_hours=total_hours,
            this_month=this_month_hours,
        ),
    )

    admin = tidyhq.check_for_groups(
        contact_id=tidyhq_id,
        groups=config["tidyhq"]["group_ids"]["admin"],
        tidyhq_cache=tidyhq_cache,
    )  # type: ignore

    if admin:
        block_list = block_formatters.add_block(block_list, blocks.header)
        block_list = block_formatters.inject_text(
            block_list=block_list, text="Admin tools"
        )
        block_list = block_formatters.add_block(block_list, blocks.text)
        block_list = block_formatters.inject_text(
            block_list=block_list,
            text=strings.admin_explainer,
        )

        admin_buttons = []
        admin_buttons = block_formatters.add_block(admin_buttons, blocks.button)
        admin_buttons = block_formatters.inject_text(
            block_list=admin_buttons, text="Add volunteer hours"
        )
        admin_buttons[-1]["action_id"] = "add_hours"
        admin_buttons[-1]["value"] = tidyhq_id
        admin_buttons[-1]["style"] = "primary"

        # Add "View as user" button
        admin_buttons = block_formatters.add_block(admin_buttons, blocks.button)
        admin_buttons = block_formatters.inject_text(
            block_list=admin_buttons, text="View as user"
        )
        admin_buttons[-1]["action_id"] = "view_as_user"
        admin_buttons[-1]["value"] = tidyhq_id

        block_list = block_formatters.add_block(block_list, blocks.actions)
        block_list[-1]["elements"] = admin_buttons

    block_list = block_formatters.add_block(block_list, blocks.divider)
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=f"Upcoming monthly rewards ({datetime.now().strftime('%B')})",
    )

    for reward in rewards["monthly"]:
        block_list += reward_tier(
            reward_definition=rewards["monthly"][reward],
            required_hours=reward,
            current_hours=this_month_hours,
        )

    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=f"Active monthly rewards (from {(datetime.now() - timedelta(days=30)).strftime('%B')}) - ({last_month_hours}h)",
    )

    current_count = 0
    for reward in rewards["monthly"]:
        block = reward_tier(
            reward_definition=rewards["monthly"][reward],
            required_hours=reward,
            current_hours=last_month_hours,
            active=True,
        )
        if block:
            block_list += block
            current_count += 1
    if current_count == 0:
        block_list = block_formatters.add_block(block_list, blocks.text)
        block_list = block_formatters.inject_text(
            block_list=block_list,
            text=strings.no_active_rewards,
        )

    block_list = block_formatters.add_block(block_list, blocks.divider)

    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="Lifetime rewards"
    )

    for reward in rewards["cumulative"]:
        block_list += reward_tier(
            reward_definition=rewards["cumulative"][reward],
            required_hours=reward,
            current_hours=total_hours,
        )

    # Reset block_list for modal version to exclude system explainer and admin tools
    if modal_version:
        # Create a new clean block_list with only the content we want for modal version
        modal_block_list = []
        
        # Keep the header (first block)
        modal_block_list = block_formatters.add_block(modal_block_list, block_list[0])
        
        # Find and keep the hours summary block (after header, before potential admin section)
        # Hours summary is the block with the hours_summary format
        for i, block in enumerate(block_list[1:], 1):  # Skip header
            if (block["type"] == "section" and 
                "text" in block and 
                "text" in block["text"] and
                ("total" in block["text"]["text"].lower() or 
                 "hours" in block["text"]["text"].lower())):
                modal_block_list = block_formatters.add_block(modal_block_list, block)
                break
        
        # Keep all blocks from the first divider onwards (rewards sections)
        # Find the first divider which separates user info from rewards
        divider_found = False
        for i, block in enumerate(block_list):
            if block["type"] == "divider" and not divider_found:
                divider_found = True
            if divider_found:
                modal_block_list = block_formatters.add_block(modal_block_list, block)
        
        block_list = modal_block_list

    return block_list


def reward_tier(
    reward_definition: dict,
    required_hours: int,
    current_hours: int,
    active: bool = False,
) -> list:
    """Takes a reward definition and the current applicable hours and returns a set of blocks describing the reward tier."""

    if active and current_hours < required_hours:
        return []

    block_list = []

    if current_hours >= required_hours:
        emoji = ":tada:"
        achieved = True
    else:
        emoji = misc.calculate_circle_emoji(count=current_hours, total=required_hours)
        achieved = False

    block_list = block_formatters.add_block(block_list, blocks.text)

    lines = []
    lines.append(f"*{reward_definition['title']}*")
    if active:
        lines[-1] += f" ({required_hours}h)"
    else:
        lines.append(
            f"{emoji} {current_hours if not achieved else required_hours}/{required_hours}h"
        )
    if not achieved:
        lines[-1] += f" - {required_hours - current_hours}h to go!"
    lines.append(f"{reward_definition['description']}")

    block_list = block_formatters.inject_text(
        block_list=block_list,
        text="\n".join(lines),
    )
    if "image" in reward_definition:
        block_list[-1]["accessory"] = copy(blocks.accessory_image)
        block_list[-1]["accessory"]["image_url"] = reward_definition["image"]

    if achieved and "claim" in reward_definition:
        block_list = block_formatters.add_block(block_list, blocks.context)
        block_list = block_formatters.inject_text(
            block_list=block_list,
            text=reward_definition["claim"],
        )

    return block_list


def reward_notification(reward_definition: dict, hours, period: str):
    """Format a reward notification message."""

    if period == "cumulative":
        text = f":tada: You've unlocked the reward: *{reward_definition['title']}* for volunteering a total of {hours} hours!\nThank you for being a part of our community, we really appreciate your time and effort!"
    else:
        text = f":tada: You've unlocked the reward: *{reward_definition['title']}* for volunteering {hours} hours in {period}!"

    block_list = []
    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=text,
    )
    block_list += reward_tier(
        reward_definition=reward_definition,
        required_hours=hours,
        current_hours=hours,
        active=True,
    )

    return block_list


def modal_add_hours():
    """Generate a modal to add hours."""

    block_list = []

    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=strings.add_hours_explainer,
    )

    # User select
    block_list = block_formatters.add_block(block_list, blocks.multi_users_select)
    block_list[-1]["label"]["text"] = "Select volunteers"
    block_list[-1]["element"]["action_id"] = "volunteer_select"
    block_list[-1]["block_id"] = "volunteer_select"
    block_list[-1]["element"].pop("placeholder")
    block_list[-1]["hint"] = copy(blocks.base_text)
    block_list[-1]["hint"]["text"] = (
        "Only volunteers who are linked to TidyHQ will actually receive hours"
    )

    # Date select
    block_list = block_formatters.add_block(block_list, blocks.date_select)
    block_list[-1]["label"]["text"] = "Date of volunteering"
    block_list[-1]["element"]["action_id"] = "date_select"
    block_list[-1]["block_id"] = "date_select"
    block_list[-1]["element"]["initial_date"] = datetime.now().strftime("%Y-%m-%d")
    block_list[-1]["element"].pop("placeholder")
    block_list[-1]["hint"] = copy(blocks.base_text)
    block_list[-1]["hint"]["text"] = (
        "We only actually store the month and year of volunteering, the exact day is discarded"
    )

    # Number input
    block_list = block_formatters.add_block(block_list, blocks.number_input)
    block_list[-1]["label"]["text"] = "Number of hours volunteered"
    block_list[-1]["element"]["action_id"] = "hours_input"
    block_list[-1]["block_id"] = "hours_input"
    block_list[-1]["element"]["min_value"] = "1"
    block_list[-1]["element"]["max_value"] = "100"
    block_list[-1]["hint"] = copy(blocks.base_text)
    block_list[-1]["hint"]["text"] = (
        "These hours will be added to *all* selected volunteers"
    )

    return block_list


def modal_view_as_user():
    """Generate a modal to select a user to view as."""

    block_list = []

    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text="Select a user to view their volunteer dashboard:",
    )

    # User select (single user)
    from slack.blocks import base_input
    user_select = copy(base_input)
    user_select["element"] = {
        "type": "users_select",
        "placeholder": {"type": "plain_text", "text": "Select a user", "emoji": True},
        "action_id": "user_select"
    }
    user_select["label"]["text"] = "User"
    user_select["block_id"] = "user_select"
    
    block_list = block_formatters.add_block(block_list, user_select)

    return block_list
