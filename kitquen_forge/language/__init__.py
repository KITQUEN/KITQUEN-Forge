"""Kitlean 3D 0.1 parser and canonical serializers."""

import math
import re
import shlex
from dataclasses import dataclass

VERSION = "0.1"
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,62}\Z")
OBJECT_REF = re.compile(r"(?:[A-Za-z][A-Za-z0-9_-]{0,62}|[0-9a-f]{32})\Z")
PRIMITIVES = ("cube", "sphere", "cylinder", "cone", "plane", "torus")
Value = str | int | float | tuple[float, ...]


class ForgeError(ValueError):
    def __init__(self, code: str, detail: str, line: int = 0):
        self.code = code
        self.detail = detail
        self.line = line
        super().__init__(detail)

    def response(self) -> dict:
        return {
            "ok": False,
            "line": self.line,
            "code": self.code,
            "detail": self.detail,
            "message": f"ERR {self.line} {self.code} {self.detail}",
        }


@dataclass(frozen=True)
class Command:
    op: str
    target: str
    args: tuple[tuple[str, Value], ...]
    line: int

    @property
    def values(self) -> dict[str, Value]:
        return dict(self.args)


def scalar(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value) or abs(value) > 1e6:
        raise ValueError("number must be finite and within ±1,000,000")
    return value


def vector(raw: str) -> tuple[float, ...]:
    values = tuple(scalar(part) for part in raw.strip("()").split(","))
    if len(values) != 3:
        raise ValueError("expected three components")
    return values


def size(raw: str) -> tuple[float, ...]:
    values = vector(raw) if "," in raw else (scalar(raw),) * 3
    if min(values) < 0.0001:
        raise ValueError("dimensions must be at least 0.0001")
    return values


def positive(raw: str) -> float:
    value = scalar(raw)
    if value < 0.0001:
        raise ValueError("expected a value of at least 0.0001")
    return value


def unit(raw: str) -> float:
    value = scalar(raw)
    if not 0 <= value <= 1:
        raise ValueError("expected a value from 0 to 1")
    return value


def frames(raw: str) -> tuple[float, ...]:
    start, end = map(int, raw.split(":"))
    if not 0 <= start < end <= 250000:
        raise ValueError("expected 0 <= start < end <= 250000")
    return start, end


def color(raw: str) -> str:
    if re.fullmatch(r"#[a-fA-F0-9]{6}", raw) is None:
        raise ValueError("expected #RRGGBB")
    return raw.upper()


def ref(raw: str) -> str:
    if not OBJECT_REF.fullmatch(raw):
        raise ValueError("expected a Forge alias or object ID")
    return raw


def alias(raw: str) -> str:
    if not IDENTIFIER.fullmatch(raw) or re.fullmatch(r"[a-f0-9]{32}", raw):
        raise ValueError("expected an alias starting with a letter, up to 63 characters")
    return raw


def choice(*choices):
    def convert(raw):
        if raw not in choices:
            raise ValueError(f"expected one of {', '.join(choices)}")
        return raw

    return convert


# Keys prefixed by '*' are required. The order also defines canonical serialization.
SCHEMAS = {
    **{f"+{name}": {"size": size} for name in PRIMITIVES},
    "+hole": {"*d": positive, "at": vector},
    "+copy": {"*as": alias},
    "+light": {"type": choice("point", "sun", "spot", "area"), "power": positive, "color": color},
    "+camera": {},
    "@pos": {"*value": vector},
    "@rot": {"*value": vector},
    "@scale": {"*value": size},
    "@size": {"*value": size},
    "@color": {"*value": color},
    "@material": {"color": color, "roughness": unit, "metallic": unit, "alpha": unit},
    "@energy": {"*value": positive},
    "@parent": {"*value": ref},
    "-": {},
    "?": {},
    "~move": {"*from": vector, "*to": vector, "*frames": frames},
    "~scale": {"*from": size, "*to": size, "*frames": frames},
    "~rotate": {"*axis": choice("x", "y", "z"), "*deg": scalar, "*frames": frames},
    "!timeline": {"*frames": frames},
    "!camera": {},
    "!export": {"*path": str},
}
POSITIONAL = {
    key: next(iter(schema)).removeprefix("*")
    for key, schema in SCHEMAS.items()
    if key.startswith("@") and len(schema) == 1
}
POSITIONAL.update({"!timeline": "frames", "!export": "path"})
READABLE = {
    "+": "create.",
    "@": "set.",
    "~": "animate.",
    "!": "scene.",
    "-": "delete",
    "?": "inspect",
}
PROPERTIES = {
    "position": "@pos",
    "rotation": "@rot",
    "scale": "@scale",
    "size": "@size",
    "material.color": "@color",
    "parent": "@parent",
    "energy": "@energy",
}


def normalize(line: str) -> str:
    match = re.fullmatch(r'\[create 3d\.([a-z]+)="([^"]+)"\]', line)
    if match:
        return f"+{match[1]}/{alias(match[2])}"
    match = re.fullmatch(r"scene\.export/(stl|obj|glb|blend)/\$(.+)\$", line)
    if match:
        return f"!export/{match[1]} {shlex.quote(match[2])}"
    match = re.fullmatch(r"([\w-]+)\.([\w.]+)([=/])(.+)", line)
    if match and match[2] in PROPERTIES:
        value = match[4].strip().removeprefix("(").removesuffix(")").replace(" ", "")
        return f"{PROPERTIES[match[2]]}/{match[1]} {value}"
    for prefix, readable in READABLE.items():
        if line.startswith(readable):
            return prefix + line[len(readable) :]
    return line


def compile_line(line: str, number: int) -> Command:
    try:
        words = shlex.split(normalize(line))
        if not words or not words[0].strip():
            raise ValueError("missing operation")
        op, _, target = words[0].partition("/")
        if op not in SCHEMAS:
            raise ValueError(f"unknown operation {op}")
        if op == "!export":
            target = choice("stl", "obj", "glb", "blend")(target)
        elif op == "!timeline":
            if target:
                raise ValueError("timeline takes frames, not an object")
        elif op in {f"+{name}" for name in (*PRIMITIVES, "light", "camera")}:
            alias(target)
        else:
            ref(target)

        raw = {}
        for index, word in enumerate(words[1:]):
            if "=" in word and op != "!export":
                key, value = word.split("=", 1)
            elif index == 0 and op in POSITIONAL:
                key, value = POSITIONAL[op], word
            else:
                raise ValueError(f"expected key=value, got {word}")
            if key in raw:
                raise ValueError(f"duplicate parameter {key}")
            raw[key] = value

        converted = []
        for field, converter in SCHEMAS[op].items():
            key = field.removeprefix("*")
            if key in raw:
                converted.append((key, converter(raw.pop(key))))
            elif field.startswith("*"):
                raise ValueError(f"missing parameter {key}")
        if raw:
            raise ValueError(f"unknown parameter {next(iter(raw))}")
        if op == "@material" and not converted:
            raise ValueError("provide at least one material property")
        return Command(op, target, tuple(converted), number)
    except ValueError as exc:
        raise ForgeError("INVALID_COMMAND", str(exc), number) from exc


def parse(source: str) -> list[Command]:
    if not isinstance(source, str) or len(source.encode("utf-8", errors="replace")) > 32768:
        raise ForgeError("LIMIT", "script must be text of at most 32 KiB")
    commands = []
    pending = None

    def flush():
        name, number, fields = pending
        if set(fields) != {"target", "diameter"}:
            raise ForgeError("INVALID_COMMAND", f"{name} needs target and diameter", number)
        commands.append(compile_line(f"+hole/{fields['target']} d={fields['diameter']}", number))

    for number, line in enumerate(source.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(("#", "//")) or line == "import.kln 3d":
            continue
        if pending:
            name, _, fields = pending
            field = re.fullmatch(re.escape(name) + r"\.(target)/([\w-]+)", line)
            field = field or re.fullmatch(re.escape(name) + r"\.(diameter)=([^\s]+)", line)
            if field:
                if field[1] in fields:
                    raise ForgeError("INVALID_COMMAND", f"duplicate {field[1]}", number)
                fields[field[1]] = field[2]
                continue
            flush()
            pending = None
        hole = re.fullmatch(r'\[create 3d\.hole="([A-Za-z][A-Za-z0-9_-]{0,62})"\]', line)
        if hole:
            pending = (hole[1], number, {})
        else:
            commands.append(compile_line(line, number))
    if pending:
        flush()
    if not 1 <= len(commands) <= 128:
        raise ForgeError("LIMIT", "expected 1 to 128 commands")
    for command in commands[:-1]:
        if command.op == "!export":
            raise ForgeError("INVALID_COMMAND", "export must be the final command", command.line)
    return commands


def serialize(commands: list[Command], readable: bool = False) -> str:
    lines = ["import.kln 3d"] if readable else []
    for command in commands:
        op = command.op
        prefix = READABLE[op[0]] + op[1:] if readable else op
        words = [f"{prefix}/{command.target}" if command.target else prefix]
        for key, value in command.args:
            if isinstance(value, tuple):
                separator = ":" if key == "frames" else ","
                value = separator.join(str(item) for item in value)
            word = str(value) if POSITIONAL.get(op) == key else f"{key}={value}"
            words.append(shlex.quote(word))
        lines.append(" ".join(words))
    return "\n".join(lines)
