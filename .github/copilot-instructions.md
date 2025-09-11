# Volunteer Tokens Slack Bot

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

The Volunteer Tokens system is a Python 3.12 Slack app that allows volunteers to track their time spent volunteering and eligibility for rewards. The app integrates with TidyHQ for member management and provides a Slack interface for hour tracking.

## Working Effectively

### Dependencies and Setup
- **CRITICAL**: Application requires Python 3.12 exactly - has not been tested against other versions.
- Install all dependencies: `pip3 install -r requirements.txt`
- **MISSING DEPENDENCY**: Install additional required package: `pip3 install phonenumbers` (this is missing from requirements.txt but required)
- **EXTERNAL API DEPENDENCY**: Application requires TidyHQ API access which cannot be tested locally without credentials. The app will exit with "Could not reach TidyHQ" error without proper API tokens.

### Required Configuration Files
Create these files before running the application:
- `cp config.example.json config.json` - Configure Slack tokens and TidyHQ settings
- `cp rewards.example.json rewards.json` - Configure volunteer rewards structure  
- Create empty `hours.json` file: `echo '{}' > hours.json` - Volunteer hours data storage

### Application Runtime Modes
- **Normal mode**: `python3.12 slack_app.py` - Runs the Slack bot in socket mode
- **Cron mode**: `python3.12 slack_app.py --cron` - Pre-generates app homes for all workspace users

### **TIMING AND CANCELLATION WARNINGS**
- **NEVER CANCEL** cron mode operations - Can take 30+ minutes with large teams. Set timeout to 60+ minutes minimum.
- **NEVER CANCEL** TidyHQ cache operations - Fresh cache generation takes 5-15 minutes depending on member count.
- The cron mode processes every user in the Slack workspace individually, so timing scales with user count.

## Validation Scenarios

**LIMITATION**: Full validation requires external API access (Slack app tokens and TidyHQ API token) that cannot be provided in development environments.

### What Can Be Validated Locally:
- Module imports: `python3 -c "from slack import blocks; from util import hours; print('✓ Modules import successfully')"`
- Configuration structure: Verify config.json and rewards.json are valid JSON
- Python dependencies: All required packages install without errors

### What Cannot Be Validated Locally:
- **Slack integration**: Requires valid bot_token and app_token in config.json
- **TidyHQ integration**: Requires valid TidyHQ API token and internet access
- **End-to-end workflows**: Member hour tracking, reward eligibility, admin functions
- **Background cache refresh**: TidyHQ member data synchronization

## Common Tasks

### Installing and Testing Setup
```bash
# Install Python dependencies
pip3 install -r requirements.txt
pip3 install phonenumbers  # Missing from requirements.txt

# Create required config files  
cp config.example.json config.json
cp rewards.example.json rewards.json
echo '{}' > hours.json

# Test local module imports (should work)
python3 -c "from slack import blocks; from util import hours; print('✓ All modules import successfully')"

# Test application startup (will fail with TidyHQ error - this is expected)
python3.12 slack_app.py
```

### Project Structure
```
/home/runner/work/Volunteer-Tokens/Volunteer-Tokens/
├── slack_app.py              # Main application entry point
├── refresh_cache.py          # TidyHQ cache refresh utility
├── requirements.txt          # Python dependencies (incomplete - missing phonenumbers)
├── config.example.json       # Configuration template
├── rewards.example.json      # Rewards structure template
├── hours.json               # Volunteer hours data (created at runtime)
├── cache.json              # TidyHQ member cache (created at runtime)
├── slack/                  # Slack interface modules
│   ├── blocks.py          # Slack Block Kit UI components
│   ├── block_formatters.py # UI formatting logic
│   └── misc.py           # Slack utility functions
├── util/                  # Core utilities
│   ├── tidyhq.py         # TidyHQ API integration
│   ├── hours.py          # Volunteer hour tracking logic
│   └── misc.py          # General utilities
├── editable_resources/   # Configuration strings
│   └── strings.py       # UI text and messages
└── rsc/                # Resources
    ├── manifest.json   # Slack app manifest
    └── *.png          # Circle percentage emojis
```

### Key Application Components

**Main Application (`slack_app.py`)**:
- Slack event handlers for app_home_opened events
- Admin interface for manually adding volunteer hours
- Socket mode handler for real-time Slack communication

**Hour Tracking (`util/hours.py`)**:
- Volunteer hour record management
- Integration with TidyHQ member data
- Monthly and cumulative hour calculations

**TidyHQ Integration (`util/tidyhq.py`)**:
- Member management system API integration
- Contact and group data caching
- Slack user to TidyHQ member mapping

**Slack Interface (`slack/`)**:
- Block Kit UI component generation
- App home interface formatting
- Interactive button and form handling

### Configuration Structure

**config.json** (from config.example.json):
- `cache_expiry`: TidyHQ cache refresh interval in seconds
- `tidyhq.token`: TidyHQ API access token  
- `tidyhq.ids`: Slack to TidyHQ ID mappings
- `tidyhq.group_ids.admin`: TidyHQ group IDs with admin privileges
- `slack.bot_token`: Slack bot OAuth token (xoxb-)
- `slack.app_token`: Slack app-level token (xapp-)
- `slack.admin_channel`: Channel ID for admin notifications

**rewards.json** (from rewards.example.json):
- `monthly`: Hour-based rewards for monthly contributions
- `cumulative`: Hour-based rewards for total contributions
- Each reward has title, description, optional image, and optional claim instructions

### Build and Test Status
- **No traditional build process** - Python script application
- **No unit test framework** - No test files or testing infrastructure found
- **GitHub Actions**: Only SonarQube code analysis on main branch pushes (`.github/workflows/check.yml`)
- **No linting configuration** - No black, flake8, or similar tool configs found

### Common Issues and Solutions

**"ModuleNotFoundError: No module named 'phonenumbers'"**:
- Solution: `pip3 install phonenumbers` (missing from requirements.txt)

**"config.json not found"**:
- Solution: `cp config.example.json config.json`

**"hours.json not found"**:
- Solution: `echo '{}' > hours.json`  

**"Could not reach TidyHQ"**:
- Expected behavior without valid TidyHQ API credentials
- Cannot be resolved in development environment

**Application exits immediately**:
- Verify all configuration files exist (config.json, rewards.json, hours.json)  
- Ensure phonenumbers package is installed
- Check that Python 3.12 is being used

### Working with External Dependencies

This application has hard dependencies on external services that prevent full local development:

1. **Slack API**: Requires workspace-specific bot and app tokens
2. **TidyHQ API**: Requires organization-specific API token and member database access

When making changes to this codebase:
- Focus on code that can be tested in isolation (utility functions, data structures)
- Use mock data structures when testing business logic  
- Validate imports and basic functionality before deploying
- Test configuration parsing and validation logic
- Always ensure new dependencies are added to requirements.txt

### Repository Context
- **Main branch**: `main`
- **GitHub Actions**: SonarQube analysis only
- **No CI/CD pipeline** for testing or deployment
- **Socket mode**: App uses Slack's socket mode for real-time communication (no webhooks)