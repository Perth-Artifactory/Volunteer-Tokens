import logging
from copy import deepcopy as copy
from datetime import datetime, timedelta
from pprint import pprint

from editable_resources import strings
from slack import blocks, block_formatters
from util import tidyhq, misc, hours

# Set up logging
logger = logging.getLogger("slack.block_formatters")


def inject_text(block_list: list, text: str, rich_text_block=False) -> list[dict]:
    """Injects text into the last block in the block list and returns the updated list.

    Is aware of most block types and should inject in the appropriate place
    """

    block_list = copy(block_list)

    if rich_text_block:
        if "text" not in block_list[-1]["elements"][-1]:
            logger.warning(
                "Injecting text into a rich text block without a text element, skipped"
            )
            return block_list
        else:
            field_maps = {
                "broadcast": "range",
                "color": "value",
                "channel": "channel_id",
                "emoji": "name",
                "link": "url",
                "text": "text",
                "user": "user_id",
                "usergroup": "usergroup_id",
            }
            el_type = block_list[-1]["elements"][-1]["type"]
            if el_type == "date":
                logger.warning(
                    "Injecting text into a rich text date element, requires multiple fields, skipped"
                )
            elif el_type in field_maps:
                block_list[-1]["elements"][-1][field_maps[el_type]] = text
            else:
                logger.warning(
                    f"Injecting text into a rich text element of unknown type {el_type}, skipped"
                )
        return block_list

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


def add_element(
    block_list: list[dict], element: dict | list, prepend: bool = False
) -> list[dict]:
    """Adds an element or list of elements to the elements list in the last item of the block list

    Can prepend or append the element."""

    block_list = copy(block_list)
    element = copy(element)

    if "elements" in block_list[-1]:
        if prepend:
            if isinstance(element, list):
                block_list[-1]["elements"] = element + block_list[-1]["elements"]
            else:
                block_list[-1]["elements"].insert(0, element)
        else:
            if isinstance(element, list):
                block_list[-1]["elements"] += element
            else:
                block_list[-1]["elements"].append(element)
    elif "element" in block_list[-1]:
        if not block_list[-1]["element"]:
            block_list[-1]["element"] = element
        else:
            logger.warning(
                "Tried to add an element to a block that supports a single element that was already populated, skipped"
            )
    else:
        logger.warning(
            "Tried to add an element to a block that doesn't support elements, skipped"
        )
        pprint(block_list[-1])

    return block_list


def construct_rich_list(items: list) -> dict:
    """Constructs a rich text list block from a list of strings (with style/url support).

    Each item in the list should be:

    - A string, which will be added as a simple text element
    - A list, which will be treated as a list of subitems, each of which can be:
        - A string, which will be added as a simple text element
        - A list, which will be treated as [text, style, style2], where style/style2 are formatting options like "bold", "italic"
        - A dict, which will be treated as a url provided it has the keys "url": str, "text": str (optional), "style": list (optional)
    """

    li = copy(blocks.rich_text_list)

    for item in items:
        # Check item type
        if isinstance(item, str):
            section = copy(blocks.rich_text_section)

            # Add a text element to the section
            section["elements"].append(copy(blocks.rich_text_section_text))
            section["elements"][-1]["text"] = item

            li["elements"].append(section)
        elif isinstance(item, list):
            section = copy(blocks.rich_text_section)

            # We assume that the items are stored as:
            # [text] - tex, style, style2]
            for subitem in item:
                # Subitems can be a string, list or dict
                if isinstance(subitem, str):
                    section["elements"].append(copy(blocks.rich_text_section_text))
                    section["elements"][-1]["text"] = subitem
                elif isinstance(subitem, list):
                    section["elements"].append(copy(blocks.rich_text_section_text))
                    section["elements"][-1]["text"] = subitem[0]
                    # Even list subitems don't necessarily have to have styling
                    # Though if they don't, they could have also just been passed as a string
                    if len(subitem) > 1:
                        section["elements"][-1]["style"] = {}
                        for style in subitem[1:]:
                            section["elements"][-1]["style"][style] = True
                elif isinstance(subitem, dict):
                    if "url" not in subitem:
                        logger.warning(
                            "Tried to add a dict subitem to a rich text list without a url key, skipped"
                        )
                        continue

                    section["elements"].append(copy(blocks.rich_text_section_link))

                    section["elements"][-1]["url"] = subitem["url"]
                    section["elements"][-1]["text"] = subitem.get(
                        "text", subitem["url"]
                    )
                    for style in subitem.get("style", []):
                        if "style" not in section["elements"][-1]:
                            section["elements"][-1]["style"] = {}
                        section["elements"][-1]["style"][style] = True

            li["elements"].append(section)
    return li


def construct_rich_text(text: list) -> dict:
    """Constructs a rich text block from a list of strings (with style support)."""

    rich_text_block = copy(blocks.rich_text_section)

    for item in text:
        # Check item type
        if isinstance(item, str):
            # Add a text element to the section
            rich_text_block["elements"].append(copy(blocks.rich_text_section_text))
            rich_text_block["elements"][-1]["text"] = item
        elif isinstance(item, list):
            # We assume that the items are stored as [text, style, style2]
            for subitem in item:
                rich_text_block["elements"].append(copy(blocks.rich_text_section_text))

                # Subitems can either be a string or a list
                if isinstance(subitem, str):
                    rich_text_block["elements"][-1]["text"] = subitem
                else:
                    rich_text_block["elements"][-1]["text"] = subitem[0]
                    # Even list subitems don't necessarily have to have styling
                    # Though if they don't, they could have also just been passed as a string
                    if len(subitem) > 1:
                        rich_text_block["elements"][-1]["style"] = {}
                        for style in subitem[1:]:
                            rich_text_block["elements"][-1]["style"][style] = True
    return rich_text_block


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

    # Add an accessory button to view statistics
    block_list[-1]["accessory"] = copy(blocks.button)
    block_list[-1]["accessory"]["text"]["text"] = "View Statistics"
    block_list[-1]["accessory"]["action_id"] = "user_statistics"
    block_list[-1]["accessory"]["value"] = tidyhq_id

    # Get the user's total hours
    total_hours = hours.get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)

    # Get the user's hours for last month
    last_month_hours = hours.get_last_month(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
    )
    this_month_hours = hours.get_current_month(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
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

        # Add debt button
        admin_buttons = block_formatters.add_block(admin_buttons, blocks.button)
        admin_buttons = block_formatters.inject_text(
            block_list=admin_buttons, text="Add time debt"
        )
        admin_buttons[-1]["action_id"] = "add_debt"
        admin_buttons[-1]["value"] = tidyhq_id
        admin_buttons[-1]["style"] = "danger"

        # Add bulk add button
        admin_buttons = block_formatters.add_block(admin_buttons, blocks.button)
        admin_buttons = block_formatters.inject_text(
            block_list=admin_buttons, text="Bulk add hours"
        )
        admin_buttons[-1]["action_id"] = "bulk_add_hours"
        admin_buttons[-1]["value"] = tidyhq_id

        # Add self log button
        admin_buttons = block_formatters.add_block(admin_buttons, blocks.button)
        admin_buttons = block_formatters.inject_text(
            block_list=admin_buttons, text="Log my own hours"
        )
        admin_buttons[-1]["action_id"] = "self_log"
        admin_buttons[-1]["value"] = tidyhq_id

        # Add "View as user" button
        admin_buttons = block_formatters.add_block(admin_buttons, blocks.button)
        admin_buttons = block_formatters.inject_text(
            block_list=admin_buttons, text="View as user"
        )
        admin_buttons[-1]["action_id"] = "view_as_user"
        admin_buttons[-1]["value"] = tidyhq_id

        # Add "View Statistics" button
        admin_buttons = block_formatters.add_block(admin_buttons, blocks.button)
        admin_buttons = block_formatters.inject_text(
            block_list=admin_buttons, text="Overall Statistics"
        )
        admin_buttons[-1]["action_id"] = "admin_statistics"
        admin_buttons[-1]["value"] = tidyhq_id

        block_list = block_formatters.add_block(block_list, blocks.actions)
        block_list[-1]["elements"] = admin_buttons

    block_list = block_formatters.add_block(block_list, blocks.divider)

    # For modal version, discard everything before rewards
    if modal_version:
        block_list = []

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
            f"{emoji} {(current_hours if not achieved else required_hours):,g}/{required_hours}h"
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


def reward_notification(reward_definition: dict, hours: int, period: str) -> list[dict]:
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


def welcome_message() -> list[dict]:
    """Generate a welcome message for new users."""

    block_list = []

    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=strings.welcome_message,
    )

    return block_list


def modal_add_hours(
    mode: str = "admin", user_id: str = "", debt: bool = False
) -> list[dict]:
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
    if mode == "self":
        block_list[-1]["element"]["initial_users"] = [user_id]

    # Date select
    block_list = block_formatters.add_block(block_list, blocks.date_select)
    block_list[-1]["label"]["text"] = (
        "Date of volunteering" if not debt else "Date of debt incurred"
    )
    block_list[-1]["element"]["action_id"] = "date_select"
    block_list[-1]["block_id"] = "date_select"
    block_list[-1]["element"]["initial_date"] = datetime.now().strftime("%Y-%m-%d")
    block_list[-1]["element"].pop("placeholder")
    block_list[-1]["hint"] = copy(blocks.base_text)
    block_list[-1]["hint"]["text"] = (
        f"We only actually store the month and year of {'volunteering' if not debt else 'debt incurred'}, the exact day is discarded"
    )

    # Hours input
    block_list = block_formatters.add_block(block_list, blocks.number_input)
    block_list[-1]["label"]["text"] = (
        f"Number of hours {'volunteered' if not debt else 'owed'}"
    )
    block_list[-1]["element"]["action_id"] = "hours_input"
    block_list[-1]["block_id"] = "hours_input"
    block_list[-1]["element"]["min_value"] = "0"
    block_list[-1]["element"]["max_value"] = "100"
    block_list[-1]["element"]["is_decimal_allowed"] = True
    block_list[-1]["hint"] = copy(blocks.base_text)
    block_list[-1]["hint"]["text"] = (
        "These hours will be added to *all* selected volunteers. Partial hours can be entered as a decimal (e.g. 0.5 for half an hour)"
    )

    # Focus on hours input if self logging
    # This doesn't actually work for some reason, Slack seems to prefer the date field above
    if mode == "self":
        block_list[-1]["element"]["focus_on_load"] = True

    # Note input
    block_list = block_formatters.add_block(block_list, blocks.text_question)
    block_list[-1]["label"]["text"] = "Note"
    block_list[-1]["element"]["action_id"] = "note_input"
    block_list[-1]["block_id"] = "note_input"
    block_list[-1]["element"]["placeholder"]["text"] = (
        "E.g. 'Volunteered at Arduino U'" if not debt else "E.g. 'Tool training'"
    )
    block_list[-1]["optional"] = True
    block_list[-1]["hint"] = copy(blocks.base_text)
    block_list[-1]["hint"]["text"] = (
        "This note will be displayed in the committee channel and sent to the volunteer(s)"
    )

    return block_list


def modal_view_as_user() -> list[dict]:
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
        "action_id": "user_select",
    }
    user_select["label"]["text"] = "User"
    user_select["block_id"] = "user_select"

    block_list = block_formatters.add_block(block_list, user_select)

    return block_list


def modal_bulk_add_hours() -> list[dict]:
    """Generate a modal to bulk add hours from up to 10 users at a time."""

    block_list = []

    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=strings.bulk_add_explainer,
    )

    count = 1

    # add date select
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

    # Note input
    block_list = block_formatters.add_block(block_list, blocks.text_question)
    block_list[-1]["label"]["text"] = "Note"
    block_list[-1]["element"]["action_id"] = "note_input"
    block_list[-1]["block_id"] = "note_input"
    block_list[-1]["element"]["placeholder"]["text"] = "E.g. 'Volunteered at Arduino U'"
    block_list[-1]["optional"] = True
    block_list[-1]["hint"] = copy(blocks.base_text)
    block_list[-1]["hint"]["text"] = (
        "This note will be displayed in the committee channel and sent to the volunteer(s)"
    )

    while count <= 10:
        block_list = block_formatters.add_block(block_list, blocks.divider)
        block_list = block_formatters.add_block(block_list, blocks.multi_users_select)
        block_list[-1]["label"]["text"] = "Select volunteers"
        block_list[-1]["element"]["action_id"] = f"volunteer_select_{count}"
        block_list[-1]["block_id"] = f"volunteer_select_{count}"
        block_list[-1]["element"].pop("placeholder")
        block_list[-1]["optional"] = True

        block_list = block_formatters.add_block(block_list, blocks.number_input)
        block_list[-1]["label"]["text"] = "Number of hours volunteered"
        block_list[-1]["element"]["action_id"] = f"hours_input_{count}"
        block_list[-1]["block_id"] = f"hours_input_{count}"
        block_list[-1]["element"]["min_value"] = "0"
        block_list[-1]["element"]["max_value"] = "100"
        block_list[-1]["element"]["is_decimal_allowed"] = True
        block_list[-1]["hint"] = copy(blocks.base_text)
        block_list[-1]["hint"]["text"] = (
            "These hours will be added to *all* selected volunteers in this section"
        )
        block_list[-1]["optional"] = True

        count += 1

    return block_list


def modal_statistics(
    volunteer_hours: dict, config: dict, tidyhq_cache: dict
) -> list[dict]:
    """Generate a modal showing overall volunteer statistics."""

    # Get statistics
    stats = hours.get_overall_statistics(
        volunteer_hours, config=config, tidyhq_cache=tidyhq_cache
    )
    top_volunteers = hours.get_top_volunteers(volunteer_hours)
    all_volunteers = hours.get_all_volunteers(volunteer_hours)
    volunteers_with_debt = hours.get_all_debt(volunteer_hours)
    non_admin_volunteers = hours.get_non_admin_volunteers(
        volunteer_hours, config, tidyhq_cache
    )
    badge_streak = hours.get_volunteer_badge_streaks(volunteer_hours)

    block_list = []

    # Header
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="Overall Volunteer Statistics"
    )

    block_list = block_formatters.add_block(block_list, blocks.rich_text_container)

    # Overall summary
    summary_stats = []
    summary_stats.append([["Total Hours", "bold"], f": {stats['total_hours']:,}h\n"])
    summary_stats.append(
        [["Total Volunteers", "bold"], f": {stats['total_volunteers']}\n"]
    )
    summary_stats.append(
        [
            ["Average Hours per Volunteer", "bold"],
            f": {stats['average_hours_per_volunteer']:,g}h",
            [
                f" ({stats['average_hours_per_volunteer_no_admin']:,g}h excl. committee)",
                "italic",
            ],
        ]
    )

    block_list = block_formatters.add_element(
        block_list, block_formatters.construct_rich_text(summary_stats)
    )

    # Top volunteers section (Top 5)

    block_list = block_formatters.add_block(block_list, blocks.divider)
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="🏆 Top 5 Volunteers"
    )
    block_list = block_formatters.add_block(block_list, blocks.rich_text_container)
    rich_text_elements = []

    list_items = []
    for volunteer in top_volunteers:
        list_items.append(
            [[volunteer["name"], "bold"], f" - {volunteer['total_hours']:,g} hours"]
        )

    block_list = block_formatters.add_element(
        block_list, block_formatters.construct_rich_list(list_items)
    )

    block_list[-1]["elements"][0]["style"] = "ordered"

    # Non-admin volunteers leaderboard
    block_list = block_formatters.add_block(block_list, blocks.divider)
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="👥 Volunteers (Excluding Committee)"
    )
    block_list = block_formatters.add_block(block_list, blocks.rich_text_container)
    list_items = []

    for volunteer in non_admin_volunteers:
        list_items.append(
            [
                [f"{volunteer['name']}", "bold"],
                f" - {volunteer['total_hours']:,g} hours",
            ]
        )

    block_list = block_formatters.add_element(
        block_list, block_formatters.construct_rich_list(list_items)
    )

    block_list[-1]["elements"][0]["style"] = "ordered"

    # Hours by month
    block_list = block_formatters.add_block(block_list, blocks.divider)
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="📅 Hours by Month"
    )

    block_list = block_formatters.add_block(block_list, blocks.rich_text_container)
    list_items = []

    # Trim to last 12 months
    month_items = list(stats["hours_by_month"].items())
    recent_months = month_items[:12] if len(month_items) > 12 else month_items

    for month_str, month_hours in recent_months:
        try:
            month_date = datetime.strptime(month_str, "%Y-%m")
            month_name = month_date.strftime("%B %Y")
        except ValueError:
            month_name = month_str

        list_items.append([[f"{month_name}:", "bold"], f" {month_hours:,g}h"])

    block_list = block_formatters.add_element(
        block_list, block_formatters.construct_rich_list(list_items)
    )

    # Badge streak leaderboard
    block_list = block_formatters.add_block(block_list, blocks.divider)
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="Longest :artifactory2-black: Streaks"
    )

    block_list = block_formatters.add_block(block_list, blocks.rich_text_container)
    list_items = []
    for volunteer in sorted(
        badge_streak.values(),
        key=lambda x: x["longest_streak"],
        reverse=True,
    ):
        if volunteer["longest_streak"] > 0:
            list_items.append(
                [
                    [f"{volunteer['name']}", "bold"],
                    f" - {volunteer['longest_streak']}m",
                    " :star:"
                    if volunteer["current_streak"] == volunteer["longest_streak"]
                    else " ",
                ]
            )

    block_list = block_formatters.add_element(
        block_list, block_formatters.construct_rich_list(list_items)
    )
    block_list[-1]["elements"][0]["style"] = "ordered"
    block_list = block_formatters.add_block(block_list, blocks.context)
    block_list = block_formatters.inject_text(
        block_list=block_list,
        text=":star: indicates the longest streak is still active",
    )

    # All volunteers leaderboard
    block_list = block_formatters.add_block(block_list, blocks.divider)
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="📋 Complete Leaderboard"
    )

    block_list = block_formatters.add_block(block_list, blocks.rich_text_container)
    list_items = []

    for volunteer in all_volunteers:
        linked_name = {
            "url": f"https://artifactory.tidyhq.com/contacts/{volunteer['tidyhq_id']}",
            "text": volunteer["name"],
            "style": ["bold"],
        }
        list_items.append([linked_name, f" - {volunteer['total_hours']:,g} hours"])

    block_list = block_formatters.add_element(
        block_list, block_formatters.construct_rich_list(list_items)
    )

    block_list[-1]["elements"][0]["style"] = "ordered"

    # Debt leaderboard
    block_list = block_formatters.add_block(block_list, blocks.divider)
    block_list = block_formatters.add_block(block_list, blocks.header)
    block_list = block_formatters.inject_text(
        block_list=block_list, text="⏳ Time Debt Owed"
    )

    block_list = block_formatters.add_block(block_list, blocks.rich_text_container)

    if volunteers_with_debt:
        list_items = []

        for volunteer in volunteers_with_debt:
            linked_name = {
                "url": f"<https://artifactory.tidyhq.com/contacts/{volunteer['tidyhq_id']}|{volunteer['name']}>",
                "text": volunteer["name"],
                "style": ["bold"],
            }
            list_items.append([linked_name, f" - {volunteer['total_debt']:,g}h"])

        block_list = block_formatters.add_element(
            block_list, block_formatters.construct_rich_list(list_items)
        )

    else:
        block_list = block_formatters.add_element(
            block_list,
            block_formatters.construct_rich_text(
                ["No volunteers currently have time debt. Great job everyone!"]
            ),
        )

    return block_list


def modal_user_statistics(
    tidyhq_id: str, volunteer_hours: dict, header: bool = True
) -> list[dict]:
    """Generate a modal showing overall volunteer statistics for a specific user."""

    from util import hours as hours_util

    # Get the user's total hours
    total_hours = hours.get_total(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)

    # Get the user's hours for last month
    last_month_hours = hours.get_last_month(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
    )
    this_month_hours = hours.get_current_month(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
    )

    # Get the user's time debt
    debt = hours_util.get_debt(tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours)

    # Get streak information
    streak = hours_util.get_volunteer_streak(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
    )
    badge_streak = hours_util.get_badge_streak(
        tidyhq_id=tidyhq_id, volunteer_hours=volunteer_hours
    )

    block_list = []
    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(
        block_list=block_list, text=strings.stats_explainer
    )
    block_list = block_formatters.add_block(block_list, blocks.divider)

    if not header:
        block_list = []

    stat_str = ""
    stat_str += f"*Total Hours Volunteered:* {total_hours:,g}h\n"
    if debt > 0:
        stat_str += f"*Time Debt:* {debt:,g}h (This is the amount of volunteering time you owe to the organisation in exchange for things like tool training)\n"
    stat_str += f"*Hours Last Month:* {last_month_hours:,g}h\n"
    stat_str += f"*Hours This Month:* {this_month_hours:,g}h\n"
    if streak["current_streak"] == streak["longest_streak"]:
        stat_str += f"*Current Monthly Streak:* {streak['current_streak']} months (Your longest yet!)\n"
    else:
        stat_str += f"*Current Monthly Streak:* {streak['current_streak']} months\n"
        stat_str += f"*Longest Monthly Streak:* {streak['longest_streak']} months\n"
    if badge_streak["longest_streak"] > 0:
        if badge_streak["current_streak"] == badge_streak["longest_streak"]:
            stat_str += f"*Current :artifactory2-black: Streak:* {badge_streak['current_streak']} months (Your longest yet!)\n"
        else:
            stat_str += f"*Current :artifactory2-black: Streak:* {badge_streak['current_streak']} months\n"
            stat_str += f"*Longest :artifactory2-black: Streak:* {badge_streak['longest_streak']} months\n"
    else:
        stat_str += "*:artifactory2-black: Streaks:* You haven't earned a :artifactory2-black: badge yet. Volunteer for at least 10 hours in a single month to unlock it!\n"

    block_list = block_formatters.add_block(block_list, blocks.text)
    block_list = block_formatters.inject_text(block_list=block_list, text=stat_str)

    return block_list
