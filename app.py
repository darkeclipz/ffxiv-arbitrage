from typing import Any, List
import threading
import queue
import websocket
import time
import signal
import bson
import os
from dotenv import load_dotenv
from arbitrage.events import Event
from arbitrage.naming import get_item_name, get_world_name, worlds
from arbitrage.universalis import ListingEvent, MarketBoardCurrentData, SaleEvent, get_market_board, get_market_board_current_data, parse_listing_event, parse_sale_event
from arbitrage.helpers import dispatch_discord_notification
from arbitrage.db import DbParameters, initialize_database, db_insert_row, db_flush_rows


load_dotenv()


HOME_WORLD = int(os.getenv("HOME_WORLD", 0))
WEBSOCKET_ADDR = os.getenv("UNIVERSALIS_WEBSOCKET_ADDR")
SELL_TAX = float(os.getenv("SELL_TAX", 0.05))
BUY_TAX = float(os.getenv("BUY_TAX", 0.05))
ARBITRAGE_PROFIT_THRESHOLD = int(os.getenv("ARBITRAGE_PROFIT_THRESHOLD", 100_000))
MARKET_BOARD_DATA_EXPIRES_AFTER_HOURS = int(os.getenv("MARKET_BOARD_DATA_EXPIRES_AFTER_HOURS", 4))
DB_PARAMS = DbParameters(
    os.getenv("DB_HOST", ""),
    int(os.getenv("DB_PORT", 5432)),
    os.getenv("DB_USER", ""),
    os.getenv("DB_PASSWORD", ""),
    os.getenv("DB_NAME", "")
)
DB_USE_TIMESCALE = os.getenv("DB_TIMESCALE", "0") == "1"


if not all([HOME_WORLD, WEBSOCKET_ADDR, SELL_TAX, BUY_TAX, ARBITRAGE_PROFIT_THRESHOLD, MARKET_BOARD_DATA_EXPIRES_AFTER_HOURS]):
    print("ERROR: .env not defined properly.")
    quit()


def http_scraper(http_scraper_queue, arbitrager_queue, stop_event):
    print("Started http_scraper.")
    while not stop_event.is_set():
        try:
            event: Event = http_scraper_queue.get(timeout=1)
            if event.type == Event.UpdateItem:
                item_code = event.args["item_code"]
                updated_item = get_market_board_current_data([item_code])
                arbitrager_queue.put(Event.update_market_board(updated_item))
        except queue.Empty:
            continue
    print("Stopped http_scraper.")


def websocket_client(arbitrager_queue, stop_event):
    def on_open(ws):
        for world_id in worlds.keys():
            ws.send(bson.encode({"event": "subscribe", "channel": "sales/add{world=" + str(world_id) + "}"}))
            ws.send(bson.encode({"event": "subscribe", "channel": "listings/add{world=" + str(world_id) + "}"}))
    def on_message(ws, encoded_message):
        message = bson.decode(encoded_message)
        if message["event"] == "sales/add":
            arbitrager_queue.put(Event.sale(parse_sale_event(message)))
        elif message["event"] == "listings/add":
            arbitrager_queue.put(Event.listing(parse_listing_event(message)))
    def on_close(ws, close_status_code, close_msg):
        print(f"WebSocket closed. Code: {close_status_code}, Message: {close_msg}")
    def on_error(ws, error):
        print(f"WebSocket error: {error}")

    print("Starting websocket_client.")

    while not stop_event.is_set():
        ws = websocket.WebSocketApp(
            WEBSOCKET_ADDR,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
        )

        # Run the websocket in this thread, so we can handle reconnects synchronously
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()

        # Wait while the connection is alive, poll for shutdown
        while wst.is_alive() and not stop_event.is_set():
            time.sleep(0.2)

        if stop_event.is_set():
            print("Stop event set, closing websocket client.")
            try:
                ws.close()
            except Exception:
                pass
            break

        print("Websocket disconnected, attempting to reconnect in 5 seconds...")
        try:
            ws.close()
        except Exception:
            pass
        time.sleep(5)  # Wait before reconnecting

    print("Stopped websocket_client.")


def arbitrager(arbitrager_queue, http_scraper_queue, stop_event):
    try:
        market_board = get_market_board(stop_event, MARKET_BOARD_DATA_EXPIRES_AFTER_HOURS)
        def on_update_market_board(items: List[MarketBoardCurrentData]):
            for item in items:
                nq_lowest_listing_price = item.min_listing_on_world(HOME_WORLD, False)
                hq_lowest_listing_price = item.min_listing_on_world(HOME_WORLD, True)
                print(f"Updated market board for {get_item_name(item.item_id)}, lowest price on {get_world_name(HOME_WORLD)} for low quality is {nq_lowest_listing_price:,} gil, and high quality is {hq_lowest_listing_price:,} gil.")
                market_board[item.item_id] = item
        def on_sale(sale_event: SaleEvent):
            for sale in sale_event.sales:
                is_hq = " (high-quality)" if sale.hq else ""
                if DB_PARAMS.is_valid():
                    db_insert_row(sale.timestamp, sale_event.world_id, sale_event.item_code, sale.price_per_unit, sale.quantity, DB_PARAMS)
                print(f"{sale.buyer_name} ({get_world_name(sale_event.world_id)}) purchased {sale.quantity:,} × {get_item_name(sale_event.item_code)}{is_hq} for {sale.price_per_unit:,} gil each, totaling {sale.total:,} gil.")
            if sale_event.world_id == HOME_WORLD:
                http_scraper_queue.put(Event.update_item({ "item_code": sale_event.item_code }))
        def on_listing(listing_event: ListingEvent):
            if listing_event.item_code not in market_board:
                print(f"ERROR: {get_item_name(listing_event.item_code)} ({listing_event.item_code}) not in market board.")
                return
            item = market_board[listing_event.item_code]
            for listing in listing_event.listings:
                is_hq = " (high-quality)" if listing.hq else ""
                print(f"{listing.retainerName} ({get_world_name(listing_event.world_id)}) listed {listing.quantity:,} × {get_item_name(listing_event.item_code)}{is_hq} for {listing.price_per_unit:,} gil each, totaling {listing.total:,} gil.")
                lowest_listing_price = item.min_listing_on_world(HOME_WORLD, listing.hq)
                arbitrage_profit = (1 - SELL_TAX) * lowest_listing_price * listing.quantity - (1 + BUY_TAX) * listing.price_per_unit * listing.quantity
                if arbitrage_profit >= ARBITRAGE_PROFIT_THRESHOLD:
                    average_price = item.hq_average_price if listing.hq else item.nq_average_price
                    listing_price_vs_average_price_percentage = lowest_listing_price / average_price
                    notification_msg = f"{listing.quantity} × **[{get_item_name(listing_event.item_code)}{is_hq}](https://universalis.app/market/{listing_event.item_code})** can be bought on **{get_world_name(listing_event.world_id)}** from {listing.retainerName} for {listing.price_per_unit:,.0f} gil each and sold on {get_world_name(HOME_WORLD)} for {lowest_listing_price:,.0f} gil each ({(listing_price_vs_average_price_percentage-1)*100:,.1f}%), resulting in **{arbitrage_profit:,.0f} gil** profit."
                    print(f"ARBITRAGE: {notification_msg}")
                    dispatch_discord_notification(notification_msg, os.getenv("DISCORD_WEBHOOK"))
        def handle_event(event: Event):
            events = {
                Event.UpdateMarketBoard: on_update_market_board,
                Event.Listing: on_listing,
                Event.Sale: on_sale
            }
            if event.type not in events:
                print(f"Unhandled event type '{event.type}' with args '{event.args}'.")
                return
            events[event.type](event.args)
        print("Starting arbitrager.")
        while not stop_event.is_set():
            try:
                event: Event = arbitrager_queue.get(timeout=1)
                handle_event(event)
            except queue.Empty:
                continue
        print("Stopped arbitrager.")
    except Exception as err:
        print("ERROR: ", err)
        stop_event.set()
    if DB_PARAMS.is_valid():
        db_flush_rows(DB_PARAMS)


def main():
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, lambda _, __: stop_event.set())

    if DB_PARAMS.is_valid():
        initialize_database(DB_PARAMS, DB_USE_TIMESCALE)

    http_scraper_queue = queue.Queue()
    arbitrager_queue = queue.Queue()

    threads = [
        threading.Thread(target=http_scraper, args=(http_scraper_queue, arbitrager_queue, stop_event)),
        threading.Thread(target=websocket_client, args=(arbitrager_queue, stop_event)),
        threading.Thread(target=arbitrager, args=(arbitrager_queue, http_scraper_queue, stop_event)),
    ]

    for t in threads:
        t.start()

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_event.set()

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
