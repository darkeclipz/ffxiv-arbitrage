from typing import Any


class Event:
    Sale = "arbitrager/sale"
    Listing = "arbitrager/listing"
    UpdateItem = "http-scraper/update-item"
    UpdateMarketBoard = "arbitrager/update-market-board"

    def __init__(self, type: str, args: Any):
        self.type = type
        self.args = args

    @staticmethod
    def new(type: str, args: Any):
        return Event(type, args)
    @staticmethod
    def sale(args: Any):
        return Event.new(Event.Sale, args)
    @staticmethod
    def listing(args: Any):
        return Event.new(Event.Listing, args)
    @staticmethod
    def update_item(args: Any):
        return Event.new(Event.UpdateItem, args)
    @staticmethod
    def update_market_board(args: Any):
        return Event.new(Event.UpdateMarketBoard, args)