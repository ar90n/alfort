from dataclasses import dataclass
from typing import (
    Any,
    Generic,
    List,
    MutableMapping,
    Protocol,
    TypeAlias,
    TypeVar,
    Union,
)

T = TypeVar("T")


@dataclass(slots=True, frozen=True)
class PatchProps:
    remove_keys: List[str]
    add_props: "Props"


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


Patch = Union[PatchProps, PatchInsertChild, PatchRemoveChild, PatchText]


class Node(Protocol):
    def apply(self, patch: Patch) -> None:
        ...


@dataclass(slots=True, frozen=True)
class Element(Generic[T]):
    tag: str
    props: "Props"
    children: List[T]


@dataclass(slots=True, frozen=True)
class VDomElement(Element["VDom"]):
    ...


VDom = Union[VDomElement, str]


Props: TypeAlias = MutableMapping[str, Any]


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
