import time
import requests
import pandas as pd

start_at_item_id = 0
max_requests_per_second = 25
max_item_ids_per_request = 100
is_test_run = False
endpoint = "https://universalis.app/api/v2/aggregated/europe/{{comma_seperated_items_ids}}"
item_names = items = requests.get("https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json/items.json").json()

item_ids = [item_id for item_id, item_name_translations in item_names.items() if item_name_translations["en"] and int(item_id) >= start_at_item_id]
print(f"There are {len(item_ids)} items.")

# 54869 items / 100 per request * 25 per second = 54896 items / 2500 per second = 21.9 seconds to load all data.
current_item_price_data = []


world_names = {}
def get_world_name(world_id):
    global world_names
    if not world_id:
        return ""
    if not world_names:
        world_names = {item["id"]: item["name"] for item in requests.get("https://universalis.app/api/v2/worlds").json()}
    return world_names[world_id]


def get_property(page, path):
    current = page
    for direction in path[:-1]:
        if direction in current:
            current = current[direction]
        else:
            return None
    return current[path[-1]]


def parse_item_data(obj):
    if not "results" in obj:
        return
    for item_data in obj["results"]:
        item_id = item_data["itemId"]
        item_name = item_names[str(item_id)]["en"]
        print(f"parsing item {item_id}")
        nq_min_listing_price = get_property(item_data, ["nq", "minListing", "region", "price"])
        nq_min_listing_world_id = get_property(item_data, ["nq", "minListing", "region", "worldId"])
        nq_recent_purchase_price = get_property(item_data, ["nq", "recentPurchase", "region", "price"])
        nq_recent_purchase_world_id = get_world_name(get_property(item_data, ["nq", "recentPurchase", "region", "worldId"]))
        nq_average_sale_price = get_property(item_data, ["nq", "averageSalePrice", "region", "price"])
        nq_average_sale_velocity = get_property(item_data, ["nq", "dailySaleVelocity", "region", "quantity"])
        hq_min_listing_price = get_property(item_data, ["hq", "minListing", "region", "price"])
        hq_min_listing_world_id = get_property(item_data, ["hq", "minListing", "region", "worldId"])
        hq_recent_purchase_price = get_property(item_data, ["hq", "recentPurchase", "region", "price"])
        hq_recent_purchase_world_id = get_world_name(get_property(item_data, ["hq", "recentPurchase", "region", "worldId"]))
        hq_average_sale_price = get_property(item_data, ["hq", "averageSalePrice", "region", "price"])
        hq_average_sale_velocity = get_property(item_data, ["hq", "dailySaleVelocity", "region", "quantity"])
        current_item_price_data.append([
            item_id, item_name,
            nq_min_listing_price, nq_min_listing_world_id, nq_recent_purchase_price, 
            nq_recent_purchase_world_id, nq_average_sale_price, nq_average_sale_velocity,
            hq_min_listing_price, hq_min_listing_world_id, hq_recent_purchase_price, 
            hq_recent_purchase_world_id, hq_average_sale_price, hq_average_sale_velocity
        ])


def batcher(list, n):
    batch = []
    for item in list:
        batch.append(item)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch


rate_limit_counter = 0
def rate_limit():
    global rate_limit_counter
    rate_limit_counter += 1
    if rate_limit_counter >= max_requests_per_second:
        time.sleep(1)
        rate_limit_counter = 0


for item_ids in batcher(item_ids, max_item_ids_per_request):
    comma_seperated_items_ids = ",".join(item_ids)
    address = endpoint.replace("{{comma_seperated_items_ids}}", comma_seperated_items_ids)
    print(f"GET {address}")
    data = requests.get(address).json()
    parse_item_data(data)
    if is_test_run:
        break
    rate_limit()
    

df = pd.DataFrame(current_item_price_data, columns=[
    "item_id", 
    "item_name",
    "nq_min_listing_price",
    "nq_min_listing_world_id",
    "nq_recent_purchase_price",
    "nq_recent_purchase_world_id",
    "nq_average_sale_price",
    "nq_average_sale_velocity",
    "hq_min_listing_price",
    "hq_min_listing_world_id",
    "hq_recent_purchase_price",
    "hq_recent_purchase_world_id",
    "hq_average_sale_price",
    "hq_average_sale_velocity",
])

df['nq_volume_gil'] = df['nq_average_sale_price'] * df['nq_average_sale_velocity']
df['nq_min_listing_sales_price_profit'] = df['nq_average_sale_price'] - df['nq_min_listing_price']

df['hq_volume_gil'] = df['hq_average_sale_price'] * df['hq_average_sale_velocity']
df['hq_min_listing_sales_price_profit'] = df['hq_average_sale_price'] - df['hq_min_listing_price']

df.to_excel("current_item_price.xlsx")