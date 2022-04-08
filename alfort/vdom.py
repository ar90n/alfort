from itertools import zip_longest
from typing import Any, TypeAlias, Union, Iterable, Protocol
from dataclasses import dataclass

Props: TypeAlias = dict[str, Any]
VNode: TypeAlias = Union["ElementVNode", "TextVNode"]


@dataclass(slots=True, frozen=True)
class PatchReplace:
    pass


@dataclass(slots=True, frozen=True)
class PatchReorder:
    pass


@dataclass(slots=True, frozen=True)
class PatchProps:
    new_props: Props
    del_keys: Iterable[str]


@dataclass(slots=True, frozen=True)
class PatchText:
    text: str


Patch = PatchReplace | PatchReorder | PatchProps | PatchText


class Node(Protocol):
    def apply(self, patch: Patch) -> None:
        pass


@dataclass(slots=True)
class ElementVNode:
    tag: str
    props: Props
    children: list[VNode]
    key: int


@dataclass(slots=True)
class TextVNode:
    text: str
    key: int


@dataclass(slots=True)
class ElementMNode(ElementVNode):
    parent: "ElementMNode"
    node: Any


@dataclass(slots=True)
class TextMNode(TextVNode):
    parent: "ElementMNode"
    node: Any


def element(
    tag: str, props: Props | None = None, children: list[VNode] | None = None
) -> ElementVNode:
    if props is None:
        props = {}
    if children is None:
        children = []

    return ElementVNode(tag, props=props, children=children, key=None)


def text(text: str) -> TextVNode:
    return TextVNode(text=text, key=None)


def diff(old_vnode: VNode | None, new_vnode: VNode | None) -> list[Patch]:
    patches = []
    match (old_vnode, new_vnode):
        case (_, None):
            pass
        case (TextVNode(text=old_text), TextVNode(text=new_text)):
            if old_text != new_text:
                patches.append(PatchText(new_text))
        case (
            ElementVNode(
                tag=old_tag, key=old_key, props=old_props, children=old_children
            ),
            ElementVNode(
                tag=new_tag, key=new_key, props=new_props, children=new_children
            ),
        ) if old_tag == new_tag and old_key == new_key:
            ret = []
            del_keys = set(old_props.keys()) - set(new_props.keys())
            new_props2 = {
                k: v
                for k, v in new_props.items()
                if k not in old_props or old_props[k] != v
            }
            if del_keys or new_props2:
                patches.append(PatchProps(new_props=new_props2, del_keys=del_keys))

            for old_child_vnode, new_child_vnode in zip_longest(
                old_children, new_children
            ):
                patches.extend(diff(old_child_vnode, new_child_vnode))
            return ret
        case (_, _):
            patches.append(PatchReplace(new_vnode))

    return patches
