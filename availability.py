import discord
from discord.ext import commands
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sqlite3
from config import AVAILABILITY_DISCORD_TOKEN
from tabulate import tabulate
from datetime import datetime
from config import AVAILABILITY_USER_STATUS_UPDATE_DELAY

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
conn = sqlite3.connect('user_data.db')
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        timezone TEXT,
        status TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS schedule (
        user_id INTEGER,
        day TEXT,
        start_time TIME,
        end_time TIME,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS default_availability (
        user_id INTEGER PRIMARY KEY,
        weekday_start TIME,
        weekday_end TIME,
        weekend_start TIME,
        weekend_end TIME,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
''')
conn.commit()


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    scheduler.start()


@bot.event
async def on_command_error(ctx, error):
    print(f"An error occurred: {error}")
    await ctx.send(f"An error occurred in the availability app: {error}")


@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')


@bot.command()
async def set_timezone(ctx, timezone: str):
    try:
        pytz.timezone(timezone)
        cursor.execute('INSERT OR REPLACE INTO users (user_id, timezone) VALUES (?, ?)', (ctx.author.id, timezone))
        conn.commit()
        await ctx.send(f'Timezone set to {timezone}')
    except pytz.exceptions.UnknownTimeZoneError:
        await ctx.send('Invalid timezone. Please use a valid timezone from the pytz library.')


@bot.command()
async def set_status(ctx, status: str):
    if status.lower() not in ['green', 'yellow', 'red']:
        await ctx.send('Invalid status. Please use green, yellow, or red.')
        return

    cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (status.lower(), ctx.author.id))
    conn.commit()
    await ctx.send(f'Status set to {status}')


@bot.command()
async def set_schedule(ctx, day: str, start_time: str, end_time: str, status: str):
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    day = day.lower()
    if day not in days:
        await ctx.send("Invalid day. Please use Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday.")
        return

    try:
        start = datetime.strptime(start_time, "%H:%M").time()
        end = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        await ctx.send("Invalid time format. Please use HH:MM for start and end times.")
        return

    if status.lower() not in ['green', 'yellow', 'red']:
        await ctx.send("Invalid status. Please use green, yellow, or red.")
        return

    # Convert time objects to strings
    start_str = start.strftime("%H:%M")
    end_str = end.strftime("%H:%M")

    cursor.execute(
        'INSERT OR REPLACE INTO schedule (user_id, day, start_time, end_time, status) VALUES (?, ?, ?, ?, ?)',
        (ctx.author.id, day, start_str, end_str, status.lower()))
    conn.commit()
    await ctx.send(f"Schedule set for {day.capitalize()} from {start_time} to {end_time} with status {status}")


@bot.command()
async def show_times(ctx):
    # Get the requesting user's timezone
    cursor.execute('SELECT timezone FROM users WHERE user_id = ?', (ctx.author.id,))
    result = cursor.fetchone()
    if not result:
        await ctx.send("Please set your timezone first using !set_timezone")
        return

    # Get all users' data
    cursor.execute('SELECT user_id, timezone, status FROM users')
    all_users = cursor.fetchall()

    # Prepare data for the table
    table_data = []
    for user_id, timezone_str, status in all_users:
        member = ctx.guild.get_member(user_id)
        if member:
            user_tz = pytz.timezone(timezone_str)
            user_time = datetime.now(user_tz)
            table_data.append([
                member.name,
                user_time.strftime('%I:%M %p'),
                timezone_str,
                status.upper() if status else 'N/A'
            ])

    # Create and send the table
    headers = ['User', 'Local Time', 'Timezone', 'Status']
    table = tabulate(table_data, headers=headers, tablefmt='grid')
    await ctx.send(f"```\nCurrent times:\n{table}\n```")


@bot.command()
async def view_schedule(ctx, user: discord.Member = None):
    # Get the requesting user's timezone
    cursor.execute('SELECT timezone FROM users WHERE user_id = ?', (ctx.author.id,))
    requester_tz_str = cursor.fetchone()
    if not requester_tz_str:
        await ctx.send("Please set your timezone first using !set_timezone")
        return
    requester_tz = pytz.timezone(requester_tz_str[0])

    if user:
        # View schedule for a specific user
        cursor.execute('SELECT timezone FROM users WHERE user_id = ?', (user.id,))
        user_tz_str = cursor.fetchone()
        if not user_tz_str:
            await ctx.send(f"{user.name} has not set their timezone.")
            return
        user_tz = pytz.timezone(user_tz_str[0])

        cursor.execute('''
            SELECT day, start_time, end_time, status 
            FROM schedule 
            WHERE user_id = ?
        ''', (user.id,))
        schedule = cursor.fetchall()

        if not schedule:
            await ctx.send(f"{user.name} has no scheduled statuses.")
            return

        schedule_text = f"             {user.name}'s schedule\n            Yours      | {user.name}'s:"

        # Sort the schedule by day
        schedule.sort(key=lambda x: day_sort_key(x[0]))

        current_day = None
        for day, start, end, status in schedule:
            if day != current_day:
                schedule_text += f"\n{day.capitalize():<9}"
                current_day = day

            start_time = datetime.strptime(start, "%H:%M").replace(tzinfo=user_tz)
            end_time = datetime.strptime(end, "%H:%M").replace(tzinfo=user_tz)
            converted_start = start_time.astimezone(requester_tz).strftime("%H:%M")
            converted_end = end_time.astimezone(requester_tz).strftime("%H:%M")

            schedule_text += f" {converted_start}-{converted_end} | {start}-{end}: {status.upper()}"

        await ctx.send(f"```{schedule_text}```")
    else:
        # View schedule for all users
        cursor.execute('SELECT user_id, timezone FROM users')
        all_users = cursor.fetchall()

        all_schedules = []
        for user_id, user_tz_str in all_users:
            user_tz = pytz.timezone(user_tz_str)
            member = ctx.guild.get_member(user_id)
            user_name = member.name if member else f"User ID: {user_id}"

            cursor.execute('''
                SELECT day, start_time, end_time, status
                FROM schedule
                WHERE user_id = ?
            ''', (user_id,))
            user_schedule = cursor.fetchall()

            if user_schedule:
                schedule_text = f"\n             {user_name}'s schedule\n            Your      | {user_name}'s:"

                # Sort the user's schedule by day
                user_schedule.sort(key=lambda x: day_sort_key(x[0]))

                current_day = None
                for day, start, end, status in user_schedule:
                    if day != current_day:
                        schedule_text += f"\n{day.capitalize():<9}"
                        current_day = day

                    start_time = datetime.strptime(start, "%H:%M").replace(tzinfo=user_tz)
                    end_time = datetime.strptime(end, "%H:%M").replace(tzinfo=user_tz)
                    converted_start = start_time.astimezone(requester_tz).strftime("%H:%M")
                    converted_end = end_time.astimezone(requester_tz).strftime("%H:%M")

                    schedule_text += f" {converted_start}-{converted_end} | {start}-{end}: {status.upper()}"

                all_schedules.append(schedule_text)
            else:
                all_schedules.append(f"{user_name} has no scheduled statuses.\n")

        # Send schedules in chunks to avoid Discord's message length limit
        schedules_text = "\n".join(all_schedules)
        chunks = [schedules_text[i:i + 1900] for i in range(0, len(schedules_text), 1900)]
        for chunk in chunks:
            await ctx.send(f"```\n{chunk}\n```")


@bot.command()
@commands.has_permissions(administrator=True)
async def set_user_schedule(ctx, user: discord.Member, day: str, start_time: str, end_time: str, status: str):
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    day = day.lower()
    if day not in days:
        await ctx.send("Invalid day. Please use Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday.")
        return

    try:
        start = datetime.strptime(start_time, "%H:%M").time()
        end = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        await ctx.send("Invalid time format. Please use HH:MM for start and end times.")
        return

    if status.lower() not in ['green', 'yellow', 'red']:
        await ctx.send("Invalid status. Please use green, yellow, or red.")
        return

    start_str = start.strftime("%H:%M")
    end_str = end.strftime("%H:%M")

    cursor.execute(
        'INSERT OR REPLACE INTO schedule (user_id, day, start_time, end_time, status) VALUES (?, ?, ?, ?, ?)',
        (user.id, day, start_str, end_str, status.lower()))
    conn.commit()
    await ctx.send(
        f"Schedule set for {user.name} on {day.capitalize()} from {start_time} to {end_time} with status {status}")


@bot.command()
@commands.has_permissions(administrator=True)
async def clear_user_schedule(ctx, user: discord.Member):
    # Clear the custom schedule
    cursor.execute('DELETE FROM schedule WHERE user_id = ?', (user.id,))

    # Get the default availability
    cursor.execute(
        'SELECT weekday_start, weekday_end, weekend_start, weekend_end FROM default_availability WHERE user_id = ?',
        (user.id,))
    default_availability = cursor.fetchone()

    if default_availability:
        weekday_start, weekday_end, weekend_start, weekend_end = default_availability
        # Set default schedule for weekdays
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
            cursor.execute('INSERT INTO schedule (user_id, day, start_time, end_time, status) VALUES (?, ?, ?, ?, ?)',
                           (user.id, day, weekday_start, weekday_end, 'green'))
        # Set default schedule for weekends
        for day in ['saturday', 'sunday']:
            cursor.execute('INSERT INTO schedule (user_id, day, start_time, end_time, status) VALUES (?, ?, ?, ?, ?)',
                           (user.id, day, weekend_start, weekend_end, 'green'))
        await ctx.send(f"Schedule cleared for {user.name} and reset to default availability.")
    else:
        await ctx.send(f"Schedule cleared for {user.name}. No default availability set.")

    conn.commit()


@bot.command()
@commands.has_permissions(administrator=True)
async def set_user_default(
        ctx,
        user: discord.Member,
        weekday_start: str,
        weekday_end: str,
        weekend_start: str,
        weekend_end: str):
    try:
        weekday_start_time = datetime.strptime(weekday_start, "%H:%M").time().strftime("%H:%M")
        weekday_end_time = datetime.strptime(weekday_end, "%H:%M").time().strftime("%H:%M")
        weekend_start_time = datetime.strptime(weekend_start, "%H:%M").time().strftime("%H:%M")
        weekend_end_time = datetime.strptime(weekend_end, "%H:%M").time().strftime("%H:%M")
    except ValueError:
        await ctx.send("Invalid time format. Please use HH:MM for all times.")
        return

    cursor.execute('''
        INSERT OR REPLACE INTO default_availability 
        (user_id, weekday_start, weekday_end, weekend_start, weekend_end) 
        VALUES (?, ?, ?, ?, ?)
    ''', (user.id, weekday_start_time, weekday_end_time, weekend_start_time, weekend_end_time))
    conn.commit()
    await ctx.send(f"Default availability set for {user.name}:\n"
                   f"Weekdays: {weekday_start}-{weekday_end}\n"
                   f"Weekends: {weekend_start}-{weekend_end}")


@bot.command()
async def view_default(ctx, user: discord.Member = None):
    if user is None:
        user = ctx.author

    cursor.execute(
        'SELECT weekday_start, weekday_end, weekend_start, weekend_end '
        'FROM default_availability '
        'WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()

    if result:
        weekday_start, weekday_end, weekend_start, weekend_end = result
        await ctx.send(f"{user.name}'s default availability:\n"
                       f"Weekdays: {weekday_start} - {weekday_end}\n"
                       f"Weekends: {weekend_start} - {weekend_end}")
    else:
        await ctx.send(f"{user.name} has no default availability set.")


@bot.command()
@commands.has_permissions(administrator=True)
async def set_user_timezone(ctx, user: discord.Member, timezone: str):
    try:
        pytz.timezone(timezone)
        cursor.execute('INSERT OR REPLACE INTO users (user_id, timezone) VALUES (?, ?)', (user.id, timezone))
        conn.commit()
        await ctx.send(f'Timezone for {user.name} set to {timezone}')
    except pytz.exceptions.UnknownTimeZoneError:
        await ctx.send('Invalid timezone. Please use a valid timezone from the pytz library.')


@bot.command()
@commands.has_permissions(administrator=True)
async def set_user_status(ctx, user: discord.Member, status: str):
    if status.lower() not in ['green', 'yellow', 'red']:
        await ctx.send('Invalid status. Please use green, yellow, or red.')
        return

    cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (status.lower(), user.id))
    conn.commit()
    await ctx.send(f'Status for {user.name} set to {status}')
    # If you have a function to update nicknames, call it here
    # await update_nickname(user)


async def update_user_status():
    now = datetime.now()
    current_day = now.strftime('%A').lower()
    current_time = now.strftime("%H:%M")
    is_weekend = current_day in ['saturday', 'sunday']

    cursor.execute('''
        SELECT users.user_id, 
               COALESCE(schedule.status, 
                        CASE 
                            WHEN ? BETWEEN default_availability.weekend_start 
                                AND default_availability.weekend_end 
                                AND ? 
                            THEN 'green'
                            WHEN ? BETWEEN default_availability.weekday_start 
                                AND default_availability.weekday_end 
                                AND NOT ?
                            THEN 'green'
                            ELSE 'red'
                        END) as status
        FROM users
        LEFT JOIN schedule ON users.user_id = schedule.user_id
            AND schedule.day = ? AND schedule.start_time <= ? AND schedule.end_time > ?
        LEFT JOIN default_availability ON users.user_id = default_availability.user_id
        WHERE schedule.status IS NOT NULL OR default_availability.weekday_start IS NOT NULL
    ''', (current_time, is_weekend, current_time, is_weekend, current_day, current_time, current_time))
    current_statuses = cursor.fetchall()

    for user_id, status in current_statuses:
        cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (status, user_id))
    conn.commit()


def day_sort_key(day):
    days_order = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    return days_order.get(day.lower(), 7)


scheduler = AsyncIOScheduler()

scheduler.add_job(update_user_status, 'interval', seconds=AVAILABILITY_USER_STATUS_UPDATE_DELAY)

bot.run(AVAILABILITY_DISCORD_TOKEN)
