import json

# Load config
with open("config.json") as f:
    config: dict = json.load(f)

unrecognised = """Unfortunately I don't recognise you. This system is only available to members, if you think this is a mistake please contact #it."""
header = "Welcome to the volunteer token system!"
explainer = "This system allows you to track the time you've volunteered for the organisation and your progress towards specific rewards. Your contribution towards making the Artifactory the place it is is greatly appreciated!"
hours_summary = "Last month you volunteered for *{last_month}* hours. You have volunteered a total of *{total_hours}* hours since the system was implemented.\nSo far this month we've processed *{this_month}* hours of tokens for you. Remember, tokens are processed manually and make take a while to show up!"
no_active_rewards = "Unfortunately there are no active reward tiers recorded for you last month. (Remember: physical tokens are processed manually so may take a few days to appear here)"
admin_explainer = "As an admin you have some extra tools available to you below. Please use them responsibly."
add_hours_explainer = "Use this form to add hours to volunteers. Remember, if they also put a token in the box the time will be counted twice!"
