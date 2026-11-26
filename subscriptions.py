import argparse
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets

DATABASE = Path("subscriptions.local.json")
REGISTRY = Path("subscriptions.json")


def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def expiry(value):
    end = datetime.combine(date.fromisoformat(value) + timedelta(days=1), time(), timezone.utc)
    if end <= datetime.now(timezone.utc):
        raise ValueError("Choose an expiry date that has not passed.")
    return int(end.timestamp())


def username(value):
    value = value.strip()
    if not value or len(value.encode("utf-8")) > 120 or any(ord(c) < 32 for c in value):
        raise ValueError("Enter a username between 1 and 120 UTF-8 bytes.")
    return value


def publish(records):
    entries = {}
    for record in records.values():
        if not record["revoked"]:
            material = record["token"] + "\n" + record["username"]
            entries[hashlib.sha256(material.encode("utf-8")).hexdigest()] = record["expires_at"]
    write_json(REGISTRY, {"version": 1, "subscriptions": entries})


def main():
    parser = argparse.ArgumentParser(description="Manage Market Advisor subscriptions locally.")
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("issue")
    issue.add_argument("username")
    issue.add_argument("valid_through")
    for command, field in (("rename", "username"), ("extend", "valid_through"), ("revoke", None)):
        action = commands.add_parser(command)
        action.add_argument("id")
        if field:
            action.add_argument(field)
    commands.add_parser("publish")
    args = parser.parse_args()
    records = json.loads(DATABASE.read_text(encoding="utf-8")) if DATABASE.exists() else {}
    try:
        if args.command == "issue":
            key_id = secrets.token_hex(6)
            token = secrets.token_hex(32)
            records[key_id] = {"username": username(args.username), "token": token,
                               "expires_at": expiry(args.valid_through), "revoked": False}
        elif args.command != "publish":
            if not re.fullmatch("[a-f0-9]{12}", args.id) or args.id not in records:
                raise ValueError("Unknown subscription ID.")
            record = records[args.id]
            if args.command == "rename":
                record["username"] = username(args.username)
            elif args.command == "extend":
                record["expires_at"] = expiry(args.valid_through)
                record["revoked"] = False
            else:
                record["revoked"] = True
        elif not DATABASE.exists() and REGISTRY.exists():
            raise ValueError("Restore the local database before rebuilding the registry.")
    except ValueError as error:
        parser.error(str(error))
    write_json(DATABASE, records)
    publish(records)
    if args.command == "issue":
        print("Subscription ID", key_id)
        print("Activation code", token)


if __name__ == "__main__":
    main()
