from typing import Any, Mapping, TypeVar

from browser import DOMNode, document  # type: ignore

from alfort import Alfort, Dispatch, Init, Update, View
from alfort.vdom import (
    Node,
    Patch,
    PatchInsertChild,
    PatchProps,
    PatchRemoveChild,
    PatchText,
    Props,
)

S = TypeVar("S", bound=Mapping[str, Any])
M = TypeVar("M")


class DomNode(Node):
    dom: "DOMNode"

    def __init__(self, dom: "DOMNode") -> None:
        self.dom = dom

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchInsertChild(child, None) if isinstance(child, DomNode):
                self.dom.insertBefore(child.dom, None)
            case PatchInsertChild(child, reference) if isinstance(
                child, DomNode
            ) and isinstance(reference, DomNode):
                self.dom.insertBefore(child.dom, reference.dom)
            case PatchRemoveChild(child) if isinstance(child, DomNode):
                self.dom.removeChild(child.dom)
            case PatchProps(remove_keys, add_props):
                for k in remove_keys:
                    self.dom.removeAttribute(k)
                for k, v in add_props.items():
                    self.dom.setAttribute(k, v)
            case PatchText():
                self.dom.nodeValue = patch.value
            case _:
                raise ValueError(f"Unknown patch: {patch}")


class AlfortDom(Alfort[S, M, DomNode]):
    @classmethod
    def create_text(
        cls,
        text: str,
        dispatch: Dispatch[M],
    ) -> DomNode:
        return DomNode(document.createTextNode(text))

    @classmethod
    def create_element(
        cls,
        tag: str,
        props: Props,
        children: list[DomNode],
        dispatch: Dispatch[M],
    ) -> DomNode:
        element = document.createElement(tag, props)
        element <= [c.dom for c in children]  # type: ignore
        return DomNode(element)

    @classmethod
    def main(
        cls,
        init: Init[S, M],
        view: View[S],
        update: Update[M, S],
        root: str,
    ) -> None:
        def mount(node: Node) -> None:
            if not isinstance(node, DomNode):
                raise ValueError("node must be a DomNode")
            dom = node.dom
            document[root] <= dom  # type: ignore

        cls._main(
            mount=mount,
            init=init,
            view=view,
            update=update,
        )
