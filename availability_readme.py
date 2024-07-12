README_CONTENT = """
# Discord Timezone and Availability Bot

This Discord bot helps manage user timezones, schedules, and availability statuses within a server.

## Features

- Set and display user timezones
- Set and view user schedules
- Automatically update user statuses based on schedules and default availability
- Set default availability for weekdays and weekends
- Display all users' schedules and current times

## Commands

### For All Users

- `!set_timezone <timezone>`: Set your timezone
- `!set_status <status>`: Set your current status (green, yellow, red)
- `!set_schedule <day> <start_time> <end_time> <status>`: Set your schedule for a specific day
- `!view_schedule [user]`: View your schedule or another user's schedule
- `!view_default [user]`: View your default availability or another user's
- `!show_times`: Display current times for all users in your timezone

### For Administrators

- `!set_user_timezone <user> <timezone>`: Set the timezone for another user
- `!set_user_status <user> <status>`: Set the status for another user
- `!set_user_schedule <user> <day> <start_time> <end_time> <status>`: Set a schedule for another user
- `!clear_user_schedule <user>`: Clear another user's custom schedule and apply their default availability schedule (if set)
- `!set_user_default <user> <weekday_start> <weekday_end> <weekend_start> <weekend_end>`: Set default availability for a user

## Usage Examples

1. Set your timezone: `!set_timezone America/New_York`
2. Set your status: `!set_status green`
3. Set your schedule for Monday: `!set_schedule Monday 09:00 17:00 green`
4. View everyone's schedule: `!view_schedule`
5. Set default availability (admin only): `!set_user_default @username 09:00 17:00 10:00 15:00`
   * Note: You enter it in your own timezone and it'll be converted when you view it. * 
6. Clear a user's schedule (admin only): `!clear_user_schedule @username`
7. Show current times for all users: `!show_times`
8. Set a user's timezone (admin only): `!set_user_timezone @username America/New_York`
9. Set a user's status (admin only): `!set_user_status @username green`
"""