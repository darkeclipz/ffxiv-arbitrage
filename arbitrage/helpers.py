import requests
import time


def pretty_number(n):
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    else:
        return str(n)
    

def batcher(list, n):
    batch = []
    for item in list:
        batch.append(item)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch


class RateLimiter:
    def __init__(self, requests_per_second: int):
        self.counter = 0
        self.requests_per_second = requests_per_second
    def increase(self):
        self.counter += 1
        if self.counter >= self.requests_per_second:
            self.counter = 0
            time.sleep(1)


discord_rate_limiter = RateLimiter(50)
last_sended_messages_queue = []
def dispatch_discord_notification(message, webhook_url):
    global last_sended_messages_queue
    if message in last_sended_messages_queue:
        print("Discord notification already send recently, skipping.")
        return
    if not webhook_url:
        print("WARNING: Discord notification is not dispatched, because the `DISCORD_WEBHOOK` environment variable is not defined.")
        return
    last_sended_messages_queue.append(message)
    if len(last_sended_messages_queue) >= 10:
        _ = last_sended_messages_queue.pop(0)
    data = {"content": message}
    response = requests.post(webhook_url, json=data)
    discord_rate_limiter.increase()
    if response.status_code != 204:
        print(f"Failed to send Discord notification: {response.status_code} - {response.text}")
