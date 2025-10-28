#!/usr/bin/env python3
"""
测试验证新的嵌套 schema 结构，确保没有 $defs 引用
"""

import json
from typing import List

from intentkit.models.chat import ChatMessage

# 导入必要的模型和函数
from app.entrypoints.x402 import X402MessageRequest


def resolve_schema_refs(schema: dict) -> dict:
    """Recursively resolve $defs references in a JSON schema.

    This function takes a JSON schema with $defs references and returns
    a fully nested schema without any $ref pointers.

    Args:
        schema: The JSON schema dictionary that may contain $defs and $ref

    Returns:
        dict: A new schema with all $ref resolved to nested objects
    """
    import copy

    # Deep copy to avoid modifying the original
    resolved_schema = copy.deepcopy(schema)

    # Extract $defs if they exist
    defs = resolved_schema.pop("$defs", {})

    def resolve_refs(obj, defs_dict):
        """Recursively resolve $ref in an object."""
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                if ref_path.startswith("#/$defs/"):
                    def_name = ref_path.replace("#/$defs/", "")
                    if def_name in defs_dict:
                        # Recursively resolve the referenced definition
                        resolved_def = resolve_refs(defs_dict[def_name], defs_dict)
                        return resolved_def
                    else:
                        # Keep the reference if definition not found
                        return obj
                else:
                    # Keep non-$defs references as is
                    return obj
            else:
                # Recursively process all values in the dictionary
                return {
                    key: resolve_refs(value, defs_dict) for key, value in obj.items()
                }
        elif isinstance(obj, list):
            # Recursively process all items in the list
            return [resolve_refs(item, defs_dict) for item in obj]
        else:
            # Return primitive values as is
            return obj

    # Resolve all references in the schema
    return resolve_refs(resolved_schema, defs)


def get_x402_message_request_schema() -> dict:
    """Generate JSON schema for X402MessageRequest with resolved $defs."""
    base_schema = X402MessageRequest.model_json_schema(mode="serialization")
    return resolve_schema_refs(base_schema)


def get_chat_message_list_schema() -> dict:
    """Generate JSON schema for List[ChatMessage] with resolved $defs."""
    base_schema = ChatMessage.model_json_schema(mode="serialization")
    resolved_item_schema = resolve_schema_refs(base_schema)

    return {
        "type": "array",
        "items": resolved_item_schema,
    }


def check_for_refs(obj, path="root") -> List[str]:
    """递归检查对象中是否还有 $ref 或 $defs"""
    refs_found = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}"

            if key == "$ref":
                refs_found.append(f"{current_path}: {value}")
            elif key == "$defs":
                refs_found.append(f"{current_path}: 发现 $defs 定义")

            if isinstance(value, (dict, list)):
                refs_found.extend(check_for_refs(value, current_path))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            current_path = f"{path}[{i}]"
            if isinstance(item, (dict, list)):
                refs_found.extend(check_for_refs(item, current_path))

    return refs_found


def main():
    print("🧪 测试验证新的嵌套 Schema 结构")
    print("=" * 80)

    # 测试 X402MessageRequest 嵌套 schema
    print("\n📥 测试 X402MessageRequest 嵌套 Schema:")
    x402_nested_schema = get_x402_message_request_schema()

    print(f"Schema 顶层键: {list(x402_nested_schema.keys())}")

    # 检查是否还有 $ref 或 $defs
    x402_refs = check_for_refs(x402_nested_schema)
    if x402_refs:
        print(f"❌ 仍然发现 {len(x402_refs)} 个引用:")
        for ref in x402_refs:
            print(f"  - {ref}")
    else:
        print("✅ 没有发现任何 $ref 或 $defs 引用")

    # 测试 ChatMessage List 嵌套 schema
    print("\n📤 测试 List[ChatMessage] 嵌套 Schema:")
    chat_list_nested_schema = get_chat_message_list_schema()

    print(f"Schema 顶层键: {list(chat_list_nested_schema.keys())}")
    print(f"Items schema 顶层键: {list(chat_list_nested_schema['items'].keys())}")

    # 检查是否还有 $ref 或 $defs
    chat_refs = check_for_refs(chat_list_nested_schema)
    if chat_refs:
        print(f"❌ 仍然发现 {len(chat_refs)} 个引用:")
        for ref in chat_refs:
            print(f"  - {ref}")
    else:
        print("✅ 没有发现任何 $ref 或 $defs 引用")

    # 比较原始和嵌套 schema 的大小
    print("\n📊 Schema 大小比较:")

    # 原始 schemas
    original_x402 = X402MessageRequest.model_json_schema(mode="serialization")
    original_chat = ChatMessage.model_json_schema(mode="serialization")

    print("X402MessageRequest:")
    print(f"  原始 schema 字符数: {len(json.dumps(original_x402))}")
    print(f"  嵌套 schema 字符数: {len(json.dumps(x402_nested_schema))}")

    print("ChatMessage:")
    print(f"  原始 schema 字符数: {len(json.dumps(original_chat))}")
    print(f"  嵌套 schema 字符数: {len(json.dumps(chat_list_nested_schema['items']))}")

    # 展示部分嵌套结构示例
    print("\n🔍 嵌套结构示例 (X402MessageRequest.attachments):")
    if (
        "properties" in x402_nested_schema
        and "attachments" in x402_nested_schema["properties"]
    ):
        attachments_prop = x402_nested_schema["properties"]["attachments"]
        print(json.dumps(attachments_prop, indent=2)[:500] + "...")

    print("\n✅ 嵌套 Schema 验证完成！")


if __name__ == "__main__":
    main()
