"""Time reference generation for agent system prompts.

This module provides functions to generate calendar views and relative date
cheat sheets for inclusion in agent system prompts.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import calendar


def _build_calendar_view(current_datetime: datetime, timezone: str) -> str:
    """Generate a multi-week Gregorian calendar view.
    
    Args:
        current_datetime: Timezone-aware datetime object
        timezone: IANA timezone string (e.g., "America/Los_Angeles")
    
    Returns:
        Formatted string showing calendar grid with today's date marked
    """
    # Ensure we're working in the user's timezone
    if current_datetime.tzinfo is None:
        tz = ZoneInfo(timezone)
        current_datetime = current_datetime.replace(tzinfo=tz)
    else:
        # Convert to user's timezone if needed
        tz = ZoneInfo(timezone)
        current_datetime = current_datetime.astimezone(tz)
    
    today = current_datetime.date()
    
    # Start from the Monday of the week containing today
    days_since_monday = today.weekday()  # Monday is 0
    calendar_start = today - timedelta(days=days_since_monday)
    
    # Generate 6 weeks of calendar
    lines = []
    lines.append("CALENDAR VIEW:")
    lines.append("Mon  Tue  Wed  Thu  Fri  Sat  Sun")
    
    current_date = calendar_start
    for week in range(6):
        week_days = []
        for day in range(7):
            # Format day as M/D (e.g., 1/17, 1/18)
            day_str = f"{current_date.month}/{current_date.day}"
            
            # Mark today with asterisk
            if current_date == today:
                day_str = f"{current_date.month}/{current_date.day}*"
            
            week_days.append(day_str)
            current_date += timedelta(days=1)
        
        lines.append("  ".join(week_days))
    
    lines.append("")
    lines.append("(* = today)")
    
    return "\n".join(lines)


def _build_relative_dates_cheat_sheet(current_datetime: datetime, timezone: str) -> str:
    """Generate a relative dates cheat sheet.
    
    Args:
        current_datetime: Timezone-aware datetime object
        timezone: IANA timezone string (e.g., "America/Los_Angeles")
    
    Returns:
        Formatted string with relative date expressions mapped to dates
    """
    # Ensure we're working in the user's timezone
    if current_datetime.tzinfo is None:
        tz = ZoneInfo(timezone)
        current_datetime = current_datetime.replace(tzinfo=tz)
    else:
        # Convert to user's timezone if needed
        tz = ZoneInfo(timezone)
        current_datetime = current_datetime.astimezone(tz)
    
    today = current_datetime.date()
    current_hour = current_datetime.hour
    is_early_morning = current_hour < 4
    is_weekday = today.weekday() < 5  # Monday=0 to Friday=4 are weekdays
    
    items = []
    items.append("RELATIVE DATES CHEAT SHEET:")
    
    # Helper function to format date
    def format_date(d: datetime.date) -> str:
        weekday_abbr = calendar.day_abbr[d.weekday()]
        return f"{weekday_abbr} {d.month}/{d.day}/{str(d.year)[-2:]}"
    
    # Helper function to format date range as ISO strings
    def format_date_range(start_date: datetime.date, end_date: datetime.date) -> str:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=tz)
        end_time = datetime.strptime("23:59:59", "%H:%M:%S").time()
        end_dt = datetime.combine(end_date, end_time).replace(tzinfo=tz)
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
        return f"({start_iso} to {end_iso})"
    
    # Helper function to format single day range
    def format_day_range(d: datetime.date) -> str:
        return format_date_range(d, d)
    
    # Today
    items.append(f'- "today": {format_date(today)} {format_day_range(today)}')
    
    # Tomorrow
    if is_early_morning:
        tomorrow_date = today  # User hasn't slept yet, so "tomorrow" means today
        tomorrow_note = f" (NOTE: Assuming user hasn't slept yet this night)"
    else:
        tomorrow_date = today + timedelta(days=1)
        tomorrow_note = ""
    items.append(f'- "tomorrow": {format_date(tomorrow_date)} {format_day_range(tomorrow_date)}{tomorrow_note}')
    
    # Day after tomorrow (references "tomorrow")
    if is_early_morning:
        # "Day after tomorrow" means tomorrow (next calendar day) when it's early morning
        day_after_date = today + timedelta(days=1)  # Tomorrow
        day_after_note = f" (NOTE: Assuming user hasn't slept yet this night)"
    else:
        day_after_date = tomorrow_date + timedelta(days=1)
        day_after_note = ""
    items.append(f'- "day after tomorrow" / "day after next": {format_date(day_after_date)} {format_day_range(day_after_date)}{day_after_note}')
    
    # Days of week (X in 1-7 days)
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i, day_name in enumerate(weekday_names):
        # Find next occurrence of this weekday (1-7 days ahead)
        days_ahead = (i - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # Next week's occurrence
        next_date = today + timedelta(days=days_ahead)
        items.append(f'- "{day_name}": {format_date(next_date)} {format_day_range(next_date)}')
    
    # Calculate base values: this week, this weekend, next week, next weekend
    if is_weekday:
        # Weekday case
        # "This week" = Monday to Friday of current week
        days_since_monday = today.weekday()
        this_week_start = today - timedelta(days=days_since_monday)  # Monday
        this_week_end = this_week_start + timedelta(days=4)  # Friday
        
        # "This weekend" = Upcoming Saturday-Sunday
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        this_weekend_sat = today + timedelta(days=days_until_saturday)
        this_weekend_sun = this_weekend_sat + timedelta(days=1)
        
        # "Next week" = Week following "this week" (next Monday-Friday)
        next_week_start = this_week_start + timedelta(days=7)
        next_week_end = next_week_start + timedelta(days=4)
        
        # "Next weekend" = Weekend following "this weekend"
        next_weekend_sat = this_weekend_sat + timedelta(days=7)
        next_weekend_sun = next_weekend_sat + timedelta(days=1)
    else:
        # Weekend case
        # "This week" = Monday to Friday (upcoming week, 1-6 days away)
        # If today is Saturday (5): Monday in 2 days, Friday in 6 days
        # If today is Sunday (6): Monday in 1 day, Friday in 5 days
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        this_week_start = today + timedelta(days=days_until_monday)  # Monday
        this_week_end = this_week_start + timedelta(days=4)  # Friday
        
        # "This weekend" = Current/previous Saturday-Sunday
        if today.weekday() == 5:  # Saturday
            this_weekend_sat = today
            this_weekend_sun = today + timedelta(days=1)
        else:  # Sunday
            this_weekend_sat = today - timedelta(days=1)
            this_weekend_sun = today
        
        # "Next week" = Same as "this week" (upcoming Monday-Friday)
        next_week_start = this_week_start
        next_week_end = this_week_end
        
        # "Next weekend" = Weekend following "this weekend"
        next_weekend_sat = this_weekend_sat + timedelta(days=7)
        next_weekend_sun = next_weekend_sat + timedelta(days=1)
    
    # Output "this week"
    items.append(f'- "this week": {format_date(this_week_start)} - {format_date(this_week_end)} {format_date_range(this_week_start, this_week_end)}')
    
    # Output "this weekend"
    items.append(f'- "this weekend": {format_date(this_weekend_sat)} - {format_date(this_weekend_sun)} {format_date_range(this_weekend_sat, this_weekend_sun)}')
    
    # Output "next week"
    items.append(f'- "next week": {format_date(next_week_start)} - {format_date(next_week_end)} {format_date_range(next_week_start, next_week_end)}')
    
    # Output "next weekend"
    items.append(f'- "next weekend": {format_date(next_weekend_sat)} - {format_date(next_weekend_sun)} {format_date_range(next_weekend_sat, next_weekend_sun)}')
    
    # "Next X" - depends on whether X is weekday or weekend
    for i, day_name in enumerate(weekday_names):
        if i < 5:  # Weekday (Mon-Fri)
            # Find X within "next week" range
            # Calculate days from next_week_start to this weekday
            days_from_monday = i  # Monday=0, Tuesday=1, ..., Friday=4
            next_x_date = next_week_start + timedelta(days=days_from_monday)
        else:  # Weekend (Sat-Sun)
            # Find X within "next weekend" range
            if i == 5:  # Saturday
                next_x_date = next_weekend_sat
            else:  # Sunday
                next_x_date = next_weekend_sun
        items.append(f'- "next {day_name}": {format_date(next_x_date)} {format_day_range(next_x_date)}')
    
    # "Week after next" = Week following "next week"
    week_after_next_start = next_week_start + timedelta(days=7)
    week_after_next_end = week_after_next_start + timedelta(days=4)
    items.append(f'- "week after next": {format_date(week_after_next_start)} - {format_date(week_after_next_end)} {format_date_range(week_after_next_start, week_after_next_end)}')
    
    # "Weekend after next" = Weekend following "next weekend"
    weekend_after_next_sat = next_weekend_sat + timedelta(days=7)
    weekend_after_next_sun = weekend_after_next_sat + timedelta(days=1)
    items.append(f'- "weekend after next": {format_date(weekend_after_next_sat)} - {format_date(weekend_after_next_sun)} {format_date_range(weekend_after_next_sat, weekend_after_next_sun)}')
    
    return "\n".join(items)


def generate_time_reference(current_datetime: datetime, timezone: str) -> str:
    """Generate time reference including calendar view and relative dates cheat sheet.
    
    Args:
        current_datetime: Timezone-aware datetime object
        timezone: IANA timezone string (e.g., "America/Los_Angeles")
    
    Returns:
        Formatted string containing calendar view and relative dates cheat sheet
    """
    calendar_view = _build_calendar_view(current_datetime, timezone)
    cheat_sheet = _build_relative_dates_cheat_sheet(current_datetime, timezone)
    
    return f"{cheat_sheet}"