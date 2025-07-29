import requests

item_names = {}
def get_item_name(item_id: int) -> str:
    global item_names
    if not item_names:
        print("Loading item names.")
        item_names = requests.get("https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json/items.json").json()
    if item_id in item_names:
        return item_names[item_id]["en"]
    if str(item_id) in item_names:
        return item_names[str(item_id)]["en"]
    return f"Undefined ({item_id})"


worlds = {
    33: "Twintania",
    36: "Lich",
    42: "Zodiark",
    56: "Phoenix",
    66: "Odin",
    67: "Shiva",
    402: "Alpha",
}
def get_world_name(world_id: int) -> str:
    global worlds
    return worlds[world_id]