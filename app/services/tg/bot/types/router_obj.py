from typing import Any

from aiogram import Dispatcher, Router


class RouterObj:
    def __init__(self, router: Router):
        self.router: Router = router
        self.dispatcher: Dispatcher | None = None

    def get_router(self) -> Router:
        return self.router

    def set_dispatcher(self, dp: Dispatcher) -> None:
        self.dispatcher = dp

    def get_dispatcher(self) -> Dispatcher | Any:
        return self.dispatcher
