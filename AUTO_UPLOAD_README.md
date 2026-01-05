# Auto-Upload to GitHub

## What It Does

Automatically commits and pushes your code changes to GitHub every day at 6:00 AM.

**Important**: Only commits if you've made actual changes. No fake or empty commits.

## How It Works

1. **Runs at 6 AM daily** via cron job
2. **Checks for changes** using `git status`
3. **If changes exist**:
   - Adds all changes
   - Commits with message "Daily update - YYYY-MM-DD"
   - Pushes to GitHub
4. **If no changes**: Does nothing

## Setup Complete

✅ Script created: `auto_uploader.py`
✅ Cron job installed: Runs at 6:00 AM daily
✅ Logs to: `auto_upload.log`

## Manual Testing

Test the script anytime:
```bash
cd "/Volumes/X9 Pro/Resume Project/WATCH/Trikal-Drsti"
python3 auto_uploader.py
```

## View Logs

Check what the script has done:
```bash
tail -20 "/Volumes/X9 Pro/Resume Project/WATCH/Trikal-Drsti/auto_upload.log"
```

## View Cron Schedule

See when it's scheduled to run:
```bash
crontab -l | grep auto_uploader
```

Output:
```
0 6 * * * /usr/bin/python3 "/Volumes/X9.../auto_uploader.py"
```

## Remove Cron Job (if needed)

To stop auto-uploads:
```bash
crontab -l | grep -v "auto_uploader" | crontab -
```

## How Cron Works

- `0 6 * * *` means:
  - Minute: 0 (at the top of the hour)
  - Hour: 6 (6 AM)
  - Day: * (every day)
  - Month: * (every month)
  - Weekday: * (every day of week)

## Important Notes

1. **Your Mac must be awake at 6 AM** for cron to run
2. **Changes are only committed if they exist** - no fake commits
3. **All logs are saved** to `auto_upload.log` for tracking
4. **Script checks both 'main' and 'master' branches** automatically

## Troubleshooting

### Cron not running?

Check if cron has permission:
```bash
# On macOS, you may need to give Terminal "Full Disk Access"
# Settings > Privacy & Security > Full Disk Access > Add Terminal
```

### Want different time?

Edit cron schedule:
```bash
crontab -e
```

Examples:
- `0 9 * * *` - 9 AM daily
- `0 6 * * 1-5` - 6 AM on weekdays only
- `0 */6 * * *` - Every 6 hours

### View last run:

```bash
tail -5 auto_upload.log
```

## What Gets Committed

Everything you've changed:
- New files
- Modified files  
- Deleted files
- Configuration changes

Excluded (from `.gitignore`):
- `__pycache__/`
- `*.pyc`
- `venv/`
- `node_modules/`
- `uploads/` (uploaded data files)
# Test - Mon Jan  5 13:21:04 IST 2026
