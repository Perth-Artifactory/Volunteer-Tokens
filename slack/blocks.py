divider = [{"type": "divider"}]
text = [{"type": "section", "text": {"type": "mrkdwn", "text": ""}}]
context = [
    {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": ""}],
    }
]
quote = [
    {
        "type": "rich_text",
        "elements": [
            {
                "type": "rich_text_quote",
                "elements": [
                    {
                        "type": "text",
                        "text": "",
                    }
                ],
            }
        ],
    }
]
header = [{"type": "header", "text": {"type": "plain_text", "text": "", "emoji": True}}]

accessory_image = {"type": "image", "image_url": "", "alt_text": ""}

button = {"type": "button", "text": {"type": "plain_text", "text": ""}}

actions = [{"type": "actions", "block_id": "button_actions", "elements": []}]

text_question = {
    "type": "input",
    "element": {
        "type": "plain_text_input",
        "action_id": "",
        "placeholder": {"type": "plain_text", "text": "", "emoji": True},
    },
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

option = {
    "text": {"type": "plain_text", "text": "", "emoji": True},
    "value": "",
}

radio_buttons = {
    "type": "input",
    "element": {
        "type": "radio_buttons",
        "options": [],
        "action_id": "",
    },
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

static_dropdown = {
    "type": "input",
    "element": {
        "type": "static_select",
        "placeholder": {"type": "plain_text", "text": "", "emoji": True},
        "options": [],
        "action_id": "",
    },
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

external_static_dropdown = {
    "action_id": "",
    "type": "external_select",
    "placeholder": {"type": "plain_text", "text": "Select an item"},
    "min_query_length": 4,
}

multi_static_dropdown = {
    "type": "input",
    "element": {
        "type": "multi_static_select",
        "placeholder": {"type": "plain_text", "text": "", "emoji": True},
        "options": [],
        "action_id": "",
    },
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

multi_users_select = {
    "type": "input",
    "element": {
        "type": "multi_users_select",
        "placeholder": {"type": "plain_text", "text": "", "emoji": True},
        "action_id": "",
    },
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

date_select = {
    "type": "input",
    "element": {
        "type": "datepicker",
        "placeholder": {
            "type": "plain_text",
            "text": "",
            "emoji": True,
        },
        "action_id": "",
    },
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

cal_select = {
    "type": "datepicker",
    "placeholder": {"type": "plain_text", "text": ""},
}

file_input = {
    "type": "input",
    "label": {"type": "plain_text", "text": ""},
    "element": {
        "type": "file_input",
    },
}

checkboxes = {
    "type": "input",
    "element": {"type": "checkboxes", "options": []},
    "label": {
        "type": "plain_text",
        "text": "",
    },
}

image = {
    "type": "image",
    "image_url": "",
    "alt_text": "An image",
}

base_input = {
    "type": "input",
    "element": {},
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

number_input = {
    "type": "input",
    "element": {"type": "number_input", "is_decimal_allowed": False, "action_id": ""},
    "label": {"type": "plain_text", "text": "", "emoji": True},
}

base_text = {"type": "plain_text", "text": ""}

# Rich text

rich_text_container = {
    "type": "rich_text",
    "elements": [],
}

rich_text_section = {"type": "rich_text_section", "elements": []}

rich_text_list = {
    "type": "rich_text_list",
    "style": "bullet",  # or "ordered"
    "elements": [],  # list of rich_text_sections
}

rich_text_preformatted = {
    "type": "rich_text_preformatted",
    "elements": [],  # list of text elements
}

rich_text_quote = {
    "type": "rich_text_quote",
    "elements": [],  # list of text elements
}

rich_text_section_broadcast = {
    "type": "broadcast",
    "range": "",  # here, channel, everyone
}

rich_text_section_colour = {
    "type": "colour",
    "color": "",  # hex color code
}

rich_text_section_channel = {"type": "channel", "channel_id": ""}

rich_text_section_date = {
    "type": "date",
    "date": "",  # epoch timestamp
    "format": "",  # format string
}
rich_text_section_emoji = {"type": "emoji", "name": ""}

rich_text_section_link = {"type": "link", "url": ""}

rich_text_section_text = {"type": "text", "text": ""}

rich_text_section_user = {"type": "user", "user_id": ""}

rich_text_section_usergroup = {"type": "usergroup", "usergroup_id": ""}
