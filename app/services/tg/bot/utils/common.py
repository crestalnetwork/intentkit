def agent_chat_id(group_memory_public: bool, chat_id: int) -> str:
    if group_memory_public:
        return "public"
    return f"telegram-{chat_id}"
