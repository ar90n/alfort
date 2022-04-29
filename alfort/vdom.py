from dataclasses import dataclass
from typing import Any, Generic, MutableMapping, Protocol, TypeAlias, TypeVar

T = TypeVar("T")

Props: TypeAlias = MutableMapping[str, Any]


@dataclass(slots=True, frozen=True)
class PatchProps:
    remove_keys: list[str]
    add_props: Props


@dataclass(slots=True, frozen=True)
class PatchInsertChild:
    child: Any
    reference: Any | None


@dataclass(slots=True, frozen=True)
class PatchRemoveChild:
    child: Any


@dataclass(slots=True, frozen=True)
class PatchText:
    value: str


Patch = PatchProps | PatchInsertChild | PatchRemoveChild | PatchText


class Node(Protocol):
    def apply(self, patch: Patch) -> None:
        ...


@dataclass(slots=True, frozen=True)
class Element(Generic[T]):
    tag: str
    props: Props
    children: list[T]


@dataclass(slots=True, frozen=True)
class VDomElement(Element["VDom"]):
    ...


VDom = VDomElement | str


def el(
    tag: str,
    props: Props | None = None,
    children: list[VDom] | None = None,
) -> VDomElement:
    if props is None:
        props = {}
    if children is None:
        children = []
    return VDomElement(tag=tag, props=props, children=children)
