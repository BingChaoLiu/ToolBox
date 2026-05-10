"""文本处理工具：大小写转换、计数等"""
def main(text="", operation="info"):
    if not text:
        print("请输入文本内容")
        return {"error": "no text"}

    print(f"输入文本 ({len(text)} 字符):")
    print(f"  \"{text}\"")
    print()

    if operation == "upper":
        result = text.upper()
        print(f"转大写: {result}")
    elif operation == "lower":
        result = text.lower()
        print(f"转小写: {result}")
    elif operation == "reverse":
        result = text[::-1]
        print(f"反转: {result}")
    elif operation == "info":
        lines = text.split("\n")
        words = text.split()
        chars = len(text)
        result = {
            "chars": chars,
            "lines": len(lines),
            "words": len(words),
        }
        print(f"统计信息:")
        print(f"  字符数: {chars}")
        print(f"  行数: {len(lines)}")
        print(f"  词数: {len(words)}")
        print(f"  字节数: {len(text.encode('utf-8'))}")
    else:
        result = text

    return {"result": result if 'result' in dir() else text, "operation": operation}
