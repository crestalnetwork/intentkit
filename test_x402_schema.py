#!/usr/bin/env python3
"""
Test script to verify X402 input and output schemas.

This script demonstrates the actual JSON schemas used for X402 endpoints
to ensure they match the expected structure.
"""

import json

from intentkit.models.chat import ChatMessage

from app.entrypoints.x402 import X402MessageRequest


def get_chat_message_list_schema() -> dict:
    """Generate JSON schema for List[ChatMessage].

    This is the same helper function used in api.py.

    Returns:
        dict: JSON schema for List[ChatMessage]
    """
    return {
        "type": "array",
        "items": ChatMessage.model_json_schema(mode="serialization"),
    }


def main():
    """Main function to display and compare schemas."""
    print("=" * 80)
    print("X402 Schema Verification")
    print("=" * 80)

    # Get input schema (X402MessageRequest)
    input_schema = X402MessageRequest.model_json_schema(mode="serialization")

    # Get output schema (List[ChatMessage])
    output_schema = get_chat_message_list_schema()

    print("\n📥 INPUT SCHEMA (X402MessageRequest):")
    print("-" * 50)
    print(json.dumps(input_schema, indent=2, ensure_ascii=False))

    print("\n📤 OUTPUT SCHEMA (List[ChatMessage]):")
    print("-" * 50)
    print(json.dumps(output_schema, indent=2, ensure_ascii=False))

    print("\n🔍 SCHEMA ANALYSIS:")
    print("-" * 50)

    # Analyze input schema
    print(f"Input schema type: {input_schema.get('type', 'unknown')}")
    if "properties" in input_schema:
        print(f"Input required fields: {input_schema.get('required', [])}")
        print(f"Input properties: {list(input_schema['properties'].keys())}")

    # Analyze output schema
    print(f"Output schema type: {output_schema.get('type', 'unknown')}")
    if "items" in output_schema:
        items_schema = output_schema["items"]
        print(f"Output array items type: {items_schema.get('type', 'unknown')}")
        if "properties" in items_schema:
            print(f"ChatMessage properties: {list(items_schema['properties'].keys())}")
            print(f"ChatMessage required fields: {items_schema.get('required', [])}")

    print("\n✅ VERIFICATION COMPLETE")
    print("=" * 80)

    # Create sample data to show structure
    print("\n📋 SAMPLE DATA STRUCTURES:")
    print("-" * 50)

    print("\nSample X402MessageRequest:")
    sample_input = {
        "agent_id": "agent-123",
        "message": "Hello, how can you help me today?",
        "app_id": "app-789",
        "search_mode": True,
        "super_mode": False,
        "attachments": [{"type": "link", "url": "https://example.com"}],
    }
    print(json.dumps(sample_input, indent=2, ensure_ascii=False))

    print("\nSample List[ChatMessage] response structure:")
    sample_output = [
        {
            "id": "msg-456",
            "agent_id": "agent-123",
            "chat_id": "x402",
            "user_id": "x402",
            "author_id": "agent-123",
            "author_type": "agent",
            "message": "Hello! I'm here to help you with various tasks.",
            "created_at": "2024-01-15T10:30:00.000Z",
            "input_tokens": 10,
            "output_tokens": 15,
            "time_cost": 1.2,
        }
    ]
    print(json.dumps(sample_output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
