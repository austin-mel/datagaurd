"""Portable editor syntax shared with frontend ruleSyntax.ts (no regex flags)."""
import re


def portable_pattern(pattern: str) -> str:
    if not 1 <= len(pattern) <= 200 or not pattern.isascii():
        raise ValueError("Use a 1–200 character ASCII regex pattern without flags.")
    classes = {"d": "0-9", "w": "A-Za-z0-9_", "s": r" \t\n\r\f\v"}
    output = ""
    in_class = False
    class_content = False
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 1
            if index == len(pattern):
                raise ValueError("Incomplete regex escape.")
            escaped = pattern[index]
            if escaped.lower() in classes:
                content = classes[escaped.lower()]
                if in_class and escaped.isupper():
                    raise ValueError("Complement shorthand escapes must be outside character classes.")
                output += content if in_class else "[" + ("^" if escaped.isupper() else "") + content + "]"
            elif escaped in "nrtfv" or escaped in r"^$.*+?()[]{}|/\\" or (escaped == "-" and in_class):
                output += "\\" + escaped
            else:
                raise ValueError("Unsupported regex escape. Use literal characters, ASCII classes or d/w/s shorthands.")
            class_content = True
        elif in_class:
            if char == "]":
                if not class_content:
                    raise ValueError("Empty character classes are not supported.")
                in_class = False
            elif char == "[" or pattern[index:index + 2] in {"&&", "~~", "--", "||"}:
                raise ValueError("Nested classes and set operations are not supported.")
            elif char != "^" or class_content:
                class_content = True
            output += char
        elif char == "[":
            in_class, class_content = True, False
            output += char
        elif char in "]}":
            raise ValueError("Escape literal closing brackets or braces.")
        elif char == "{":
            quantifier = re.match(r"\{[0-9]+(?:,[0-9]*)?\}", pattern[index:])
            if not quantifier:
                raise ValueError("Use a valid repetition count or escape the brace.")
            if any(int(count) > 1_000_000 for count in re.findall(r"[0-9]+", quantifier[0])):
                raise ValueError("Regex repetition counts must not exceed 1000000.")
            output += quantifier[0]
            index += len(quantifier[0]) - 1
            if pattern[index + 1:index + 2] == "+":
                raise ValueError("Possessive quantifiers are not supported.")
        elif char == "(" and pattern[index:index + 2] == "(?" and pattern[index:index + 3] != "(?:":
            raise ValueError("Use plain or noncapturing groups; flags and lookarounds are not supported.")
        elif char in "*+?" and pattern[index + 1:index + 2] == "+":
            raise ValueError("Possessive quantifiers are not supported.")
        else:
            output += r"[^\n]" if char == "." else char
        index += 1
    if in_class:
        raise ValueError("Unclosed character class.")
    try:
        re.compile(output, re.ASCII)
    except (re.error, OverflowError) as exc:
        raise ValueError("Enter a valid regular expression.") from exc
    return output


def allowed_values(text: str) -> list[str]:
    """Comma-separated values, with CSV double quotes for embedded commas/quotes."""
    values: list[str] = []
    index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        value = ""
        if index < len(text) and text[index] == '"':
            index += 1
            while True:
                if index == len(text):
                    raise ValueError("Close the quoted allowed value.")
                char = text[index]
                index += 1
                if char != '"':
                    value += char
                elif index < len(text) and text[index] == '"':
                    value += '"'
                    index += 1
                else:
                    break
            while index < len(text) and text[index].isspace():
                index += 1
            if index < len(text) and text[index] != ",":
                raise ValueError("Separate allowed values with commas.")
        else:
            start = index
            while index < len(text) and text[index] != ",":
                index += 1
            value = text[start:index].strip()
            if '"' in value:
                raise ValueError("Quote the entire value and double embedded quotes.")
        if not value.strip() or value in values:
            raise ValueError("Allowed values must be unique and nonblank.")
        values.append(value)
        if index == len(text):
            return values
        index += 1


def format_allowed_values(values: list[str]) -> str:
    return ", ".join('"' + value.replace('"', '""') + '"'
                     if ',' in value or '"' in value or value != value.strip() else value for value in values)
