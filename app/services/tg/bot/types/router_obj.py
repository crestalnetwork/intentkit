class RouterObj:
    def __init__(self, router):
        self.router = router

    def get_router(self):
        return self.router

    def set_dispatcher(self, dp):
        self.dispatcher = dp

    def get_dispatcher(self):
        return self.dispatcher
