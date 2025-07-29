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
    402: "Alpha",
    36: "Lich",
    66: "Odin",
    56: "Phoenix",
    67: "Shiva",
    33: "Twintania",
    42: "Zodiark"
}
def get_world_name(world_id: int) -> str:
    global worlds
    return worlds[world_id]