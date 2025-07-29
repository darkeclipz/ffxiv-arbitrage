# FFXIV Arbitrage

This script indexes the entire market board for your home server and listens to listing events on other servers.
If the different between the lowest price of the item on your server and the listing price on the other server exceeds some threshold, a notification will be send to a Discord webhook. 
This can be used to find arbitrage oppertunities, although just blindly following every arbitrage oppertunity that it finds usually ain't a good idea.
Use at your own caution.

## How to use

 1. Clone the project to a folder of your liking.
 2. Create a `.env` file and add `DISCORD_HOOK=<HOOK_URL>` (the entire url).
 3. Run `python app.py` and wait for ~15 minutes to index the market board.

## Configuration

In `app.py` the following settings can be changed:

 * `HOME_WORLD`, see `arbitrage/naming.py` for a list of worlds and their ID.
 * `SELL_TAX`, sell tax percentage that is applied (default `0.05`).
 * `BUY_TAX`, buy tax percentage that is applied (default `0.05`).
 * `ARBITRAGE_PROFIT_THRESHOLD`, minimum profit needed before a notification is send.
 * `MARKET_BOARD_DATA_EXPIRES_AFTER_HOURS`, time before the cached market data expires and needs to be re-indexed.

## Dependencies

```
pip install pymongo
pip install websocket-client
pip install requests
pip install dotenv
pip install tqdm
```

### Notes

 * `pymongo` is used for `bson`.
 * `websocked-client` is used for `websocket`.

See the Universalis Websocket API for more information: https://docs.universalis.app/.

# Resources

 * [Universalis Documentation](https://docs.universalis.app/)
 * [Market Board History](https://universalis.app/api/v2/europe/43557)
 * [Current Item Price](https://universalis.app/api/v2/aggregated/europe/43557)
 * [Available Worlds](https://universalis.app/api/v2/worlds)
 * [Data-centers](https://universalis.app/api/v2/data-centers)
 * [Market Board Current Data](https://universalis.app/api/v2/europe/43557)
 * [Sales History](https://universalis.app/api/v2/history/europe/43557?minSalePrice=0&maxSalePrice=2147483647)
 * [Item Names (all languages)](https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json/items.json)
 * [Marketable Items](https://universalis.app/api/v2/marketable)

