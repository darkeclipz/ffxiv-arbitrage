from dataclasses import dataclass
from typing import List
import requests
import pandas as pd
import time
import pickle
import os
from arbitrage.helpers import RateLimiter, batcher


rate_limiter = RateLimiter(25)


def get_marketable_items() -> List[int]:
    rate_limiter.increase()
    return requests.get("https://universalis.app/api/v2/marketable").json()


@dataclass 
class Listing:
    last_review_time: int
    retainer_name: str
    price_per_unit: int
    quantity: int
    world_id: int
    total: int
    tax: int
    hq: bool


def parse_listing(obj: dict) -> Listing:
    return Listing(
        obj["lastReviewTime"],
        obj["retainerName"],
        obj["pricePerUnit"],
        obj["quantity"],
        obj["worldID"],
        obj["total"],
        obj["tax"],
        obj["hq"]
    )


@dataclass
class RecentHistory:
    hq: bool
    price_per_unit: int
    quantity: int
    world_id: int
    buyer_name: str
    total: int
    timestamp: int


@dataclass
class SaleEventLine:
    hq: bool
    price_per_unit: int
    quantity: int
    total: int
    timestamp: int
    buyer_name: str


def parse_sale_event_line(obj: dict) -> SaleEventLine:
    return SaleEventLine(
        obj["hq"],
        obj["pricePerUnit"],
        obj["quantity"],
        obj["total"],
        obj["timestamp"],
        obj["buyerName"]
    )


@dataclass
class SaleEvent:
    item_code: int
    world_id: int
    sales: List[SaleEventLine]


def parse_sale_event(obj: dict) -> SaleEvent:
    return SaleEvent(
        obj["item"],
        obj["world"],
        [parse_sale_event_line(sale) for sale in obj["sales"]]
    )


@dataclass 
class ListingEventLine:
    price_per_unit: int
    quantity: int
    hq: bool
    retainerName: str
    total: int
    tax: int


def parse_listing_event_line(obj: dict) -> ListingEventLine:
    return ListingEventLine(
        obj["pricePerUnit"],
        obj["quantity"],
        obj["hq"],
        obj["retainerName"],
        obj["total"],
        obj["tax"]
    )


@dataclass 
class ListingEvent:
    item_code: int
    world_id: int
    listings: List[ListingEventLine]


def parse_listing_event(obj: dict):
    return ListingEvent(
        obj["item"],
        obj["world"],
        [parse_listing_event_line(listing) for listing in obj["listings"]]
    )


def parse_recent_history(obj: dict) -> RecentHistory:
    return RecentHistory(
        obj["hq"],
        obj["pricePerUnit"],
        obj["quantity"],
        obj["worldID"],
        obj["buyerName"],
        obj["total"],
        obj["timestamp"]
    )


@dataclass
class MarketBoardCurrentData:
    item_id: int
    nq_average_price: float
    hq_average_price: float
    nq_average_sale_velocity: float
    hq_average_sale_velocity: float
    listings: List[Listing]
    recent_history: List[RecentHistory]
    last_update: int
    def min_listings(self) -> List[tuple[int, bool, int]]:
        listings = [
            {
                "world_id": listing.world_id, 
                "price_per_unit": listing.price_per_unit, 
                "hq": listing.hq
            } 
            for listing 
            in self.listings
        ]
        if not listings:
            return []
        df = pd.DataFrame(listings)
        df = df[["world_id", "price_per_unit", "hq"]].groupby(["world_id", "hq"]).min().sort_values("price_per_unit")
        tuples = list(df.itertuples(index=True, name=None))
        return [(world_id, hq, price_per_unit) for (world_id, hq), price_per_unit in tuples]
    def min_listing_on_world(self, world_id, hq) -> int:
        listings = self.min_listings()
        for listing_world_id, listing_hq, listing_price in listings:
            if listing_world_id == world_id and listing_hq == hq:
                return listing_price
        return 0


def parse_market_board_current_data(obj: dict) -> MarketBoardCurrentData:
    return MarketBoardCurrentData(
        obj["itemID"],
        obj["averagePriceNQ"],
        obj["averagePriceHQ"],
        obj["nqSaleVelocity"],
        obj["hqSaleVelocity"],
        [parse_listing(listing) for listing in obj["listings"]],
        [parse_recent_history(history) for history in obj["recentHistory"]],
        int(time.time())
    )


def get_market_board_current_data(item_ids: List[int]) -> List[MarketBoardCurrentData]:
    assert 0 <= len(item_ids) <= 100
    comma_seperated_item_ids = ",".join(map(str, item_ids))
    rate_limiter.increase()
    address = f"https://universalis.app/api/v2/europe/{comma_seperated_item_ids}"
    http_status_ok = 200
    attempts_left = 7
    retry_after_seconds = 2
    response = requests.get(address)
    try:
        while response.status_code != http_status_ok and attempts_left:
            time.sleep(retry_after_seconds)
            response = requests.get(address)
            retry_after_seconds *= 2
            attempts_left -= 1
        obj = response.json()
        rate_limiter.increase()
        assert obj
        if "items" in obj:
            return [parse_market_board_current_data(item) for _, item in obj["items"].items()]
        elif "hasData" in obj:
            return [parse_market_board_current_data(obj)]
        return []
    except Exception as err:
        print(response.status_code)
        print(response.raw)
        raise err


def get_market_board(stop_event, max_age_in_hours) -> dict[int, MarketBoardCurrentData]:
    # check if there is an up-to-date version (age < 24h old)
    filename = 'market_board.pkl'
    if os.path.exists(filename):
        last_modified = os.path.getmtime(filename)
        if time.time() - last_modified < (max_age_in_hours * 60 * 60):
            with open(filename, 'rb') as f:
                market_board = pickle.load(f)
                return market_board
    # load market board from Universalis
    print("Market board is out of date and needs to be updated, this takes up to 15 minutes.")
    market_board = {}
    marketable_items = get_marketable_items()
    current_batch = 0
    batch_size = 100
    total_batches = len(marketable_items) // batch_size + 1
    from tqdm import tqdm
    with tqdm(total=len(marketable_items)) as progress:
        for item_ids in batcher(marketable_items, 100):
            if stop_event.is_set():
                return {}
            market_board_current_data = get_market_board_current_data(item_ids)
            for item in market_board_current_data:
                market_board[item.item_id] = item
            current_batch += 1
            progress.update(len(item_ids))
    # cache results
    with open(filename, 'wb') as f:
        pickle.dump(market_board, f)
    return market_board