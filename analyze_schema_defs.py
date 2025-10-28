#!/usr/bin/env python3
"""
分析 X402MessageRequest 和 ChatMessage 的 JSON schema 结构
识别所有 $defs 引用，为后续的嵌套 schema 转换做准备
"""

from typing import List

from intentkit.models.chat import ChatMessage

# 导入必要的模型
from app.entrypoints.x402 import X402MessageRequest


def analyze_schema_defs(schema: dict, path: str = "root") -> List[str]:
    """递归分析 schema 中的 $defs 引用"""
    defs_refs = []

    if isinstance(schema, dict):
        for key, value in schema.items():
            current_path = f"{path}.{key}"

            if key == "$ref" and isinstance(value, str):
                if value.startswith("#/$defs/"):
                    defs_refs.append(f"{current_path}: {value}")
            elif isinstance(value, (dict, list)):
                defs_refs.extend(analyze_schema_defs(value, current_path))

    elif isinstance(schema, list):
        for i, item in enumerate(schema):
            current_path = f"{path}[{i}]"
            if isinstance(item, (dict, list)):
                defs_refs.extend(analyze_schema_defs(item, current_path))

    return defs_refs


def main():
    print("🔍 分析 X402MessageRequest 和 ChatMessage 的 JSON Schema 结构")
    print("=" * 80)

    # 分析 X402MessageRequest
    print("\n📥 X402MessageRequest Schema 分析:")
    x402_schema = X402MessageRequest.model_json_schema(mode="serialization")

    print(f"Schema 顶层键: {list(x402_schema.keys())}")

    if "$defs" in x402_schema:
        print(f"$defs 定义数量: {len(x402_schema['$defs'])}")
        print(f"$defs 键名: {list(x402_schema['$defs'].keys())}")

    x402_refs = analyze_schema_defs(x402_schema)
    print(f"发现的 $defs 引用 ({len(x402_refs)} 个):")
    for ref in x402_refs:
        print(f"  - {ref}")

    # 分析 ChatMessage
    print("\n📤 ChatMessage Schema 分析:")
    chat_schema = ChatMessage.model_json_schema(mode="serialization")

    print(f"Schema 顶层键: {list(chat_schema.keys())}")

    if "$defs" in chat_schema:
        print(f"$defs 定义数量: {len(chat_schema['$defs'])}")
        print(f"$defs 键名: {list(chat_schema['$defs'].keys())}")

    chat_refs = analyze_schema_defs(chat_schema)
    print(f"发现的 $defs 引用 ({len(chat_refs)} 个):")
    for ref in chat_refs:
        print(f"  - {ref}")

    # 分析 List[ChatMessage] schema
    print("\n📋 List[ChatMessage] Schema 分析:")
    list_schema = {"type": "array", "items": chat_schema}

    list_refs = analyze_schema_defs(list_schema)
    print(f"发现的 $defs 引用 ({len(list_refs)} 个):")
    for ref in list_refs:
        print(f"  - {ref}")

    # 详细展示 $defs 内容
    print("\n🔍 详细 $defs 内容:")

    if "$defs" in x402_schema:
        print("\nX402MessageRequest $defs:")
        for def_name, def_content in x402_schema["$defs"].items():
            print(f"  {def_name}:")
            print(f"    类型: {def_content.get('type', 'unknown')}")
            if "properties" in def_content:
                print(f"    属性数量: {len(def_content['properties'])}")
                print(f"    属性: {list(def_content['properties'].keys())}")

    if "$defs" in chat_schema:
        print("\nChatMessage $defs:")
        for def_name, def_content in chat_schema["$defs"].items():
            print(f"  {def_name}:")
            print(f"    类型: {def_content.get('type', 'unknown')}")
            if "properties" in def_content:
                print(f"    属性数量: {len(def_content['properties'])}")
                print(f"    属性: {list(def_content['properties'].keys())}")

    print("\n✅ 分析完成！")


if __name__ == "__main__":
    main()
