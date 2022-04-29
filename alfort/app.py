from abc import abstractmethod
from dataclasses import dataclass, replace
from itertools import zip_longest
from typing import Callable, Generic, TypeAlias, TypeVar

from alfort.vdom import (
    Element,
    Node,
    Patch,
    PatchInsertChild,
    PatchProps,
    PatchRemoveChild,
    PatchText,
    Props,
    VDom,
    VDomElement,
)

T = TypeVar("T")
N = TypeVar("N", bound=Node)
S = TypeVar("S")
M = TypeVar("M")

Dispatch: TypeAlias = Callable[[M], None]
Effect: TypeAlias = Callable[[Dispatch[M]], None]
Init: TypeAlias = Callable[[], tuple[S, list[Effect[M]]]]
View: TypeAlias = Callable[[S], VDom]
Update: TypeAlias = Callable[[M, S], tuple[S, list[Effect[M]]]]
Enqueue: TypeAlias = Callable[[Callable[[], None]], None]


@dataclass(slots=True, frozen=True)
class NodeDomElement(Element["NodeDom"]):
    node: Node


@dataclass(slots=True, frozen=True)
class NodeDomText:
    value: str
    node: Node


NodeDom = NodeDomElement | NodeDomText


class Alfort(Generic[S, M, N]):
    @classmethod
    @abstractmethod
    def create_element(
        cls, tag: str, props: Props, children: list[N], dispatch: Dispatch[M]
    ) -> N:
        ...

    @classmethod
    @abstractmethod
    def create_text(cls, text: str, dispatch: Dispatch[M]) -> N:
        ...

    @classmethod
    def _run_effects(cls, dispatch: Dispatch[M], effects: list[Effect[M]]) -> None:
        for e in effects:
            e(dispatch)

    @classmethod
    def _diff_props(cls, node_props: Props, vdom_props: Props) -> PatchProps:
        remove_keys = set(node_props.keys()) - set(vdom_props.keys())
        add_props = {
            k: v
            for k, v in vdom_props.items()
            if k not in node_props or (node_props[k] != v)
        }
        return PatchProps(remove_keys=list(remove_keys), add_props=add_props)

    @classmethod
    def _diff_node(
        cls,
        cur_node: Node | None,
        new_node: Node | None,
    ) -> list[Patch]:
        patches_to_parent: list[Patch] = []

        reference = None
        if cur_node is not None:
            reference = cur_node
            patches_to_parent.append(PatchRemoveChild(child=reference))

        if new_node is not None:
            patches_to_parent.insert(
                0, PatchInsertChild(child=new_node, reference=reference)
            )

        return patches_to_parent

    @classmethod
    def _patch_children(
        cls,
        dispatch: Dispatch[M],
        node_children: list[NodeDom],
        vdom_children: list[VDom],
    ) -> tuple[list[NodeDom], list[Patch]]:
        new_children: list[NodeDom] = []
        patches_to_parent: list[Patch] = []
        for n, vd in zip_longest(node_children, vdom_children):
            (new_child, patches_to_self) = cls.patch(dispatch, n, vd)
            if new_child is not None:
                new_children.append(new_child)
            patches_to_parent.extend(patches_to_self)
        return (new_children, patches_to_parent)

    @classmethod
    def patch(
        cls,
        dispatch: Dispatch[M],
        node_dom: NodeDom | None,
        new_vdom: VDom | None,
    ) -> tuple[NodeDom | None, list[Patch]]:
        match (node_dom, new_vdom):
            case (_, None):
                if node_dom is None or node_dom.node is None:
                    return (None, [])
                patches_to_self: list[Patch] = [PatchRemoveChild(child=node_dom.node)]
                return (None, patches_to_self)
            case (
                NodeDomText(cur_text, cur_node),
                str() as new_text,
            ):
                if cur_node is None:
                    raise ValueError("cur_node is None")
                if cur_text == new_text:
                    return (node_dom, [])
                cur_node.apply(PatchText(value=new_text))
                return (replace(node_dom, value=new_text), [])
            case (
                NodeDomElement() as node_dom,
                VDomElement() as new_vdom,
            ) if node_dom.tag == new_vdom.tag:
                if node_dom.props != new_vdom.props and node_dom.node is not None:
                    node_dom.node.apply(cls._diff_props(node_dom.props, new_vdom.props))

                (new_children, patches_to_self) = cls._patch_children(
                    dispatch,
                    node_dom.children,
                    new_vdom.children,
                )
                if node_dom.node is not None:
                    for p in patches_to_self:
                        node_dom.node.apply(p)
                return (
                    replace(node_dom, props=new_vdom.props, children=new_children),
                    [],
                )
            case (_, str() as new_text):
                cur_node = node_dom.node if node_dom is not None else None
                new_node = cls.create_text(new_text, dispatch)
                patches_to_parent = cls._diff_node(cur_node, new_node)
                return (NodeDomText(value=new_text, node=new_node), patches_to_parent)
            case (_, VDomElement() as new_vdom):
                cur_node = node_dom.node if node_dom is not None else None
                new_node = cls.create_element(
                    new_vdom.tag, new_vdom.props, [], dispatch
                )
                patches_to_parent = cls._diff_node(cur_node, new_node)

                (new_children, patches_to_self) = cls._patch_children(
                    dispatch, [], new_vdom.children
                )
                for p in patches_to_self:
                    new_node.apply(p)

                return (
                    NodeDomElement(
                        tag=new_vdom.tag,
                        props=new_vdom.props,
                        children=new_children,
                        node=new_node,
                    ),
                    patches_to_parent,
                )
            case (_, _):
                raise AssertionError(f"unexpected: {node_dom} {new_vdom}")

    @classmethod
    def _main(
        cls,
        init: Init[S, M],
        view: View[S],
        update: Update[M, S],
        root_node: N,
        enqueue: Enqueue = lambda render: render(),
    ) -> None:
        state, effects = init()
        root = NodeDomElement(tag="__root__", props={}, children=[], node=root_node)

        def rooted_view(state: S) -> VDom:
            return VDomElement("__root__", {}, [view(state)])

        def render() -> None:
            nonlocal state
            nonlocal root
            (root, _) = cls.patch(dispatch, root, rooted_view(state))

        def dispatch(msg: M) -> None:
            nonlocal state
            nonlocal root
            (state, effects) = update(msg, state)
            enqueue(render)
            cls._run_effects(dispatch, effects)

        enqueue(render)
        cls._run_effects(dispatch, effects)
