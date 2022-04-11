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
    def patch(
        self,
        tag: str | None = None,
        props: dict[str, Any] | None = None,
        children: list[MirrorNode] | None = None,
        node: Node | None = None,
    ) -> MirrorNodeElement:
        tag = self.tag if tag is None else tag
        props = self.props if props is None else props
        children = self.children if children is None else children
        node = self.node if node is None else node
        return MirrorNodeElement(tag=tag, props=props, children=children, node=node)


@dataclass(slots=True, frozen=True)
@with_node
class MirrorNodeText(Text):
    def patch(
        self, text: str | None = None, node: Node | None = None
    ) -> MirrorNodeText:
        text = self.text if text is None else text
        node = self.node if node is None else node
        return MirrorNodeText(text=text, node=node)


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
            if mirror_node.text != virtual_node.text:
                mirror_node.node.apply(PatchText(virtual_node.text))
                return mirror_node.patch(text=virtual_node.text)
            return mirror_node
        case (
            MirrorNodeElement() as mirror_node,
            VirtualNodeElement() as virtual_node,
        ) if mirror_node.tag == virtual_node.tag:
            patches: list[Patch] = []
            if mirror_node.props != virtual_node.props:
                patches.append(PatchProps(virtual_node.props))

            new_children = mirror_node.children
            if mirror_node.children != virtual_node.children:
                child_pairs = zip_longest(mirror_node.children, virtual_node.children)
                new_children = [
                    v
                    for v in [patch(cls, m_c, v_c) for m_c, v_c in child_pairs]
                    if v is not None
                ]
                patches.append(PatchChildren([c.node.unwrap() for c in new_children]))

            if len(patches) == 0:
                return mirror_node

            for p in patches:
                mirror_node.node.apply(p)
            return mirror_node.patch(
                props=virtual_node.props,
                children=new_children,
            )

        case (_, VirtualNodeText() as virtual_node):
            node = cls()
            node.apply(PatchText(text=virtual_node.text))
            return MirrorNodeText(
                text=virtual_node.text,
                node=node,
            )

        case (_, VirtualNodeElement() as virtual_node):
            new_children = [
                v
                for v in [patch(cls, None, v_c) for v_c in virtual_node.children]
                if v is not None
            ]

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
