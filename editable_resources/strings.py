import json

# Load config
with open("config.json") as f:
    config: dict = json.load(f)

unrecognised = """Unfortunately I don't recognise you. This system is only available to members, if you think this is a mistake please contact #it."""
header = "Welcome to the volunteer token system!"
explainer = "This system allows you to track the time you've volunteered for the organisation and your progress towards specific rewards. Your contribution towards making the Artifactory the place it is and is greatly appreciated!"
stats_explainer = "Every hour you contribute to our community is valuable and appreciated. Whether it's a one-off event or a regular commitment, your time helps us thrive. Here are some statistics about your volunteering journey so far."
no_active_rewards = "Unfortunately there are no active reward tiers recorded for you last month. (Remember: physical tokens are processed manually so may take a few days to appear here)"
admin_explainer = "As an admin you have some extra tools available to you below. Please use them responsibly."
add_hours_explainer = "Use this form to add hours to volunteers. Remember, if they also put a token in the box the time will be counted twice!"
bulk_add_explainer = "Use this form to bulk add various numbers of hours to volunteers. Primarily intended for use when processing an event or the token box."
