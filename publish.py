import datetime as dt
import fcntl
import json
import os
import pathlib
import urllib.request

def post(url, payload, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=240) as response:
        return json.load(response)

def run():
    root = pathlib.Path("/data")
    if os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") != str(root):
        raise RuntimeError("Attach a persistent volume at /data")
    lock = (root / "lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    path = root / "posts.json"
    history = json.loads(path.read_text()) if path.exists() else []
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).date()
    if history and (today - dt.date.fromisoformat(history[-1]["date"])).days < 3:
        return
    pending = root / "pending.json"
    if pending.exists():
        raise RuntimeError("Check Telegram and reconcile pending.json before publishing again")
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    channel = os.environ["TELEGRAM_CHAT_ID"]
    queue = json.loads(pathlib.Path(__file__).with_name("queue.json").read_text())
    sent = {p.get("id") for p in history}
    for article in queue:
        if article["id"] in sent:
            continue
        entry = dict(article, date=str(today))
        message = article["text"] + "\n\n" + article["source"]
        pending.write_text(json.dumps(entry, ensure_ascii=False))
        reply = post("https://api.telegram.org/bot" + token + "/sendMessage",
                     {"chat_id": channel, "text": message,
                      "link_preview_options": {"url": article["source"], "prefer_large_media": True}})
        if not reply.get("ok"):
            raise RuntimeError("Telegram did not confirm delivery")
        entry["message_id"] = reply["result"]["message_id"]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(history + [entry], ensure_ascii=False))
        tmp.replace(path)
        pending.unlink()
        return
    print("Queue exhausted")

if __name__ == "__main__":
    run()
