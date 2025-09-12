#!/usr/bin/env python3
"""
Test suite for block kit validation in generator functions.
"""

import pytest
import unittest.mock as mock
from slack import block_formatters, misc as slack_misc
from unittest.mock import patch


class TestBlockKitValidation:
    """Test that all block kit generator functions include validation."""

    def test_app_home_includes_validation(self):
        """Test that app_home calls the validation function."""
        mock_config = {
            "tidyhq": {
                "group_ids": {
                    "admin": []
                }
            }
        }
        mock_tidyhq_cache = {}
        mock_volunteer_hours = {}
        mock_rewards = {
            "monthly": {},
            "cumulative": {}
        }
        
        with patch('slack.misc.validate') as mock_validate:
            mock_validate.return_value = True
            with patch('util.tidyhq.map_slack_to_tidyhq') as mock_map:
                mock_map.return_value = "test_id"
                with patch('util.hours.get_total') as mock_total:
                    mock_total.return_value = 0
                    with patch('util.hours.get_last_month') as mock_last:
                        mock_last.return_value = 0
                        with patch('util.hours.get_current_month') as mock_current:
                            mock_current.return_value = 0
                            with patch('util.tidyhq.check_for_groups') as mock_groups:
                                mock_groups.return_value = False
                                
                                result = block_formatters.app_home(
                                    user_id="test_user",
                                    config=mock_config,
                                    tidyhq_cache=mock_tidyhq_cache,
                                    volunteer_hours=mock_volunteer_hours,
                                    rewards=mock_rewards
                                )
                                
                                # Verify validation was called with home surface
                                mock_validate.assert_called_once_with(result, surface="home")

    def test_reward_tier_includes_validation(self):
        """Test that reward_tier calls the validation function."""
        mock_reward = {
            "title": "Test Reward",
            "description": "Test Description"
        }
        
        with patch('slack.misc.validate') as mock_validate:
            mock_validate.return_value = True
            with patch('util.misc.calculate_circle_emoji') as mock_emoji:
                mock_emoji.return_value = ":circle:"
                
                result = block_formatters.reward_tier(
                    reward_definition=mock_reward,
                    required_hours=10,
                    current_hours=5
                )
                
                # Verify validation was called with message surface
                mock_validate.assert_called_once_with(result, surface="message")

    def test_reward_notification_includes_validation(self):
        """Test that reward_notification calls the validation function."""
        mock_reward = {
            "title": "Test Reward",
            "description": "Test Description"
        }
        
        with patch('slack.misc.validate') as mock_validate:
            mock_validate.return_value = True
            with patch('util.misc.calculate_circle_emoji') as mock_emoji:
                mock_emoji.return_value = ":circle:"
                
                result = block_formatters.reward_notification(
                    reward_definition=mock_reward,
                    hours=10,
                    period="January"
                )
                
                # Verify validation was called (will be called twice since it calls reward_tier)
                assert mock_validate.call_count >= 1
                # Verify the final call was with the complete result and message surface
                mock_validate.assert_called_with(result, surface="message")

    def test_modal_add_hours_includes_validation(self):
        """Test that modal_add_hours calls the validation function."""
        with patch('slack.misc.validate') as mock_validate:
            mock_validate.return_value = True
            
            result = block_formatters.modal_add_hours()
            
            # Verify validation was called with modal surface
            mock_validate.assert_called_once_with(result, surface="modal")

    def test_validation_function_exists(self):
        """Test that the validate function exists and is callable."""
        assert hasattr(slack_misc, 'validate')
        assert callable(slack_misc.validate)


if __name__ == "__main__":
    pytest.main([__file__])