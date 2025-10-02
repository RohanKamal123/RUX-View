import os
import json
import csv
import sys
from datetime import datetime

def parse_activity_log(txt_file):
    entries = []
    if not os.path.exists(txt_file):
        return entries
    with open(txt_file, "r") as f:
        for line in f:
            if "App:" in line:
                try:
                    ts_str = line.split("]")[0].strip("[")
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    app = line.split("App: '")[1].split("'")[0]
                    window = line.split("Window: '")[1].split("'")[0]
                    keys = int(line.split("Keys: ")[1].split("|")[0].strip())
                    clicks = int(line.split("Clicks: ")[1].split("|")[0].strip())
                    movements = int(line.split("Movements: ")[1].split("|")[0].strip())
                    idle = "True" in line
                    entries.append({"timestamp": ts, "app": app, "window": window,
                                    "keys": keys, "clicks": clicks, "movements": movements, "idle": idle})
                except (IndexError, ValueError) as e:
                    print(f"Skipping malformed activity log line: {line.strip()} - Error: {e}")
    return entries

def parse_screenshot_log(json_file):
    entries = []
    if not os.path.exists(json_file):
        return entries
    with open(json_file, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                ts = datetime.fromisoformat(data["timestamp"])
                entries.append({"timestamp": ts, "screenshot": data["screenshot"], "reason": data.get("reason", "")})
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Skipping malformed screenshot log line: {line.strip()} - Error: {e}")
    return entries

def merge_logs(activity, screenshots, out_csv):
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp","app","window","keys","clicks","movements","idle","screenshot","reason"])

        if not activity:
            for s in screenshots:
                writer.writerow([s["timestamp"], None, None, None, None, None, None, s["screenshot"], s["reason"]])
            return

        for s in screenshots:
            closest = min(activity, key=lambda a: abs((a["timestamp"]-s["timestamp"]).total_seconds()))
            if abs((closest["timestamp"]-s["timestamp"]).total_seconds()) <= 1:
                writer.writerow([s["timestamp"], closest["app"], closest["window"], closest["keys"],
                                 closest["clicks"], closest["movements"], closest["idle"], s["screenshot"], s["reason"]])
            else:
                writer.writerow([s["timestamp"], None, None, None, None, None, None, s["screenshot"], s["reason"]])

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_metadata.py <YYYY-MM-DD>")
        sys.exit(1)

    date_str = sys.argv[1]
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        sys.exit(1)

    base_dir = "C:/Users/HP Zbook/Documents/MonitoringStart"
    activity_log_path = os.path.join(base_dir, "logs", "daily", date_str, f"activity_{date_str}.txt")
    screenshot_log_path = os.path.join(base_dir, "logs", "daily", date_str, "log.json")
    output_csv_path = os.path.join(base_dir, "processed", f"{date_str}_metadata.csv")
    
    # Adjust screenshot log path for 2025-10-01 case
    if date_str == "2025-10-01":
        screenshot_log_path = os.path.join(base_dir, "logs", "daily", "2025-10-01", "log.json")
        activity_log_path = os.path.join(base_dir, "logs", "daily", "2025-09-30", "activity_2025-09-30.txt")


    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)

    activity_data = parse_activity_log(activity_log_path)
    screenshot_data = parse_screenshot_log(screenshot_log_path)

    merge_logs(activity_data, screenshot_data, output_csv_path)

    print(f"Metadata CSV generated at: {output_csv_path}")