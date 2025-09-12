# Volunteer Token bot

This Slack app allows volunteers to track the amount of time they spend volunteering for the organisation and whether they're eligible for any rewards.

## Install

* Application is written for Python3.12 and hasn't been tested against other versions
* Install requirements from requirements.txt
* Create Slack app using `rsc/manifest.json`
* Add emoji from `rsc` to Slack workspace
* Create `config.json` based on `config.example.json`
* Create `rewards.json` based on `rewards.example.json`
  * Rewards are split into monthly and all time
  * Title and description are required
  * Images are optional, won't be replaced with placeholder if not present
  * Claim information will be added as a sub message/context block
  * You can't have two rewards in the same category with the same hours reward.

## Running

`python3.12 slack_app.py`

### Background tasks

Run with `--cron` to pregenerate app homes to give the appearance of a faster first load. Takes quite a while on large teams so don't run more than once a day.
