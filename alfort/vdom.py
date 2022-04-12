from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Generic, Protocol, TypeAlias, TypeVar


@dataclass(slots=True, frozen=True)
class PatchReplace:
    tag: str
    props: dict[str, Any]
    children: list[Any]


@dataclass(slots=True, frozen=True)
class PatchProps:
    props: dict[str, Any]


@dataclass(slots=True, frozen=True)
class PatchText:
    text: str


@dataclass(slots=True, frozen=True)
class PatchChildren:
    children: list[Any]


Patch = PatchReplace | PatchProps | PatchText | PatchChildren


class Node(Protocol):
    def unwrap(self) -> Any:
        ...

    def apply(self, patch: Patch) -> None:
        ...


def with_node(cls: Any):
    class WithNode(cls):
        node: Node

    return WithNode


T = TypeVar("T")


@dataclass(slots=True, frozen=True)
class Element(Generic[T]):
    tag: str
    props: dict[str, Any]
    children: list[T]


@dataclass(slots=True, frozen=True)
class Text:
    text: str


@dataclass(slots=True, frozen=True)
class VirtualNodeElement(Element["VirtualNodeElement"]):
    pass


@dataclass(slots=True, frozen=True)
class VirtualNodeText(Text):
    pass


VirtualNode: TypeAlias = VirtualNodeElement | VirtualNodeText


@dataclass(slots=True, frozen=True)
@with_node
class MirrorNodeElement(Element["MirrorNodeElement"]):
    def update(
        self, props: dict[str, Any] | None = None, children: list[Any] | None = None
    ) -> MirrorNodeElement:
        patches = []
        if props is None:
            props = {}
        if children is None:
            children = []

        if props != self.props:
            patches.append(PatchProps(props))
        if children != self.children:
            patches.append(PatchChildren(children=[c.node.unwrap() for c in children]))

        if len(patches) == 0:
            return self

        for p in patches:
            self.node.apply(p)
        return MirrorNodeElement(
            tag=self.tag,
            props=props,
            children=children,
            node=self.node,
        )

    @staticmethod
    def of(virtual_node: VirtualNodeElement, cls: type[Node]) -> MirrorNodeElement:
        def _dispatch(virtual_node: VirtualNode, cls: type[Node]) -> MirrorNode:
            match virtual_node:
                case VirtualNodeElement():
                    return MirrorNodeElement.of(virtual_node, cls)
                case VirtualNodeText():
                    return MirrorNodeText.of(virtual_node, cls)

        new_children = [_dispatch(v_c, cls) for v_c in virtual_node.children]

        node = cls()
        node.apply(
            PatchReplace(
                tag=virtual_node.tag,
                props=virtual_node.props,
                children=[c.node.unwrap() for c in new_children],
            )
        )
        return MirrorNodeElement(
            tag=virtual_node.tag,
            props=virtual_node.props,
            children=new_children,
            node=node,
        )


@dataclass(slots=True, frozen=True)
@with_node
class MirrorNodeText(Text):
    def update(self, text: str) -> MirrorNodeText:
        if self.text == text:
            return self

        self.node.apply(PatchText(text=text))
        return MirrorNodeText(text=text, node=self.node)

    @staticmethod
    def of(virtual_node: VirtualNodeText, cls: type[Node]) -> MirrorNodeText:
        node = cls()
        node.apply(PatchText(text=virtual_node.text))
        return MirrorNodeText(text=virtual_node.text, node=node)


MirrorNode: TypeAlias = MirrorNodeElement | MirrorNodeText


def patch(
    cls: type[Node], mirror_node: MirrorNode | None, virtual_node: VirtualNode | None
) -> MirrorNode | None:
    match (mirror_node, virtual_node):
        case (_, None):
            return None
        case (
            MirrorNodeText() as mirror_node,
            VirtualNodeText() as virtual_node,
        ):
            return mirror_node.update(virtual_node.text)
        case (_, VirtualNodeText() as virtual_node):
            return MirrorNodeText.of(virtual_node, cls)
        case (
            MirrorNodeElement() as mirror_node,
            VirtualNodeElement() as virtual_node,
        ) if mirror_node.tag == virtual_node.tag:
            new_children = []
            for m_c, v_c in zip_longest(mirror_node.children, virtual_node.children):
                if n := patch(cls, m_c, v_c):
                    new_children.append(n)
            return mirror_node.update(virtual_node.props, new_children)
        case (_, VirtualNodeElement() as virtual_node):
            return MirrorNodeElement.of(virtual_node, cls)
        case (_, _):
            raise ValueError("Invalid patch")
    raise ValueError("e")


def element(
    tag: str,
    props: dict[str, Any] | None = None,
    children: list[VirtualNode] | None = None,
) -> VirtualNodeElement:
    if props is None:
        props = {}
    if children is None:
        children = []
    return VirtualNodeElement(tag=tag, props=props, children=children)


def text(text: str) -> VirtualNodeText:
    return VirtualNodeText(text=text)
