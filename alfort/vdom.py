from abc import abstractmethod
from dataclasses import dataclass
from itertools import zip_longest
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    Protocol,
    Tuple,
    TypeAlias,
    TypeVar,
    Union,
)

T = TypeVar("T")
N = TypeVar("N")
S = TypeVar("S")
M = TypeVar("M")


@dataclass(slots=True, frozen=True)
class PatchProps:
    remove_keys: list[str]
    add_props: dict[str, Any]


@dataclass(slots=True, frozen=True)
class PatchInsertChild:
    child: Any
    reference: Any


@dataclass(slots=True, frozen=True)
class PatchRemoveChild:
    child: Any


@dataclass(slots=True, frozen=True)
class PatchText:
    text: str


Patch = Union[PatchProps, PatchInsertChild, PatchRemoveChild, PatchText]


class Target(Protocol):
    def unwrap(self) -> Any:
        ...

    def apply(self, patch: Patch) -> None:
        ...


@dataclass(slots=True, frozen=True)
class Element(Generic[N]):
    tag: str
    props: dict[str, Any]
    children: list[N]


@dataclass(slots=True, frozen=True)
class Text:
    text: str


@dataclass(slots=True, frozen=True)
class VDomElement(Element["VDom"]):
    pass


@dataclass(slots=True, frozen=True)
class VDomText(Text):
    pass


VDom: TypeAlias = Union[VDomElement, VDomText]


@dataclass(slots=True, frozen=True)
class NodeElement(Element["Node"]):
    target: Target


@dataclass(slots=True, frozen=True)
class NodeText(Text):
    target: Target


Node: TypeAlias = Union[NodeElement, NodeText]

# to support key

# (node, patch_to_parent)
PatchResult: TypeAlias = Tuple[Optional[Node], list[Patch]]


def to_vdom(node: Node) -> VDom:
    match node:
        case (NodeElement(tag, props, children)):
            return VDomElement(tag, props, [to_vdom(c) for c in children])
        case (NodeText(text)):
            return VDomText(text=text)
    raise ValueError(f"Unknown node type: {node}")


def el(
    tag: str,
    props: dict[str, Any] | None = None,
    children: list[VDom] | None = None,
) -> VDomElement:
    if props is None:
        props = {}
    if children is None:
        children = []
    return VDomElement(tag=tag, props=props, children=children)


def text(text: str) -> VDomText:
    return VDomText(text=text)


UpdateResult: TypeAlias = Tuple[S, list[Callable[[], None]]]
Dispatch: TypeAlias = Callable[[M], None]
Effect: TypeAlias = Callable[[], None]
View: TypeAlias = Callable[[S], VDom]
Update: TypeAlias = Callable[[M, S], tuple[S, list[Effect]]]
Init: TypeAlias = Callable[[], tuple[S, list[Effect]]]
Mount: TypeAlias = Callable[[Target], None]


class App(Generic[S, M, N]):
    def __init__(self, view: View[S], update: Update[M, S]) -> None:
        self.view = view
        self.update = update

    @abstractmethod
    def create_element(
        self,
        tag: str,
        props: dict[str, Any],
        children: list[N],
        dispatch: Dispatch[M],
    ) -> Target:
        raise NotImplementedError("create_element")

    @abstractmethod
    def create_text(self, text: str) -> Target:
        raise NotImplementedError("create_text")

    def make_patch(
        self, dispatch: Dispatch[M] = lambda _: None
    ) -> Callable[[Optional[Node], Optional[VDom]], PatchResult]:
        return lambda node, vdom: self._patch(
            create_element=self.create_element,
            create_text=self.create_text,
            dispatch=dispatch,
            node=node,
            vdom=vdom,
        )

    def __call__(
        self,
        init: Init[S],
        mount: Mount,
    ) -> None:
        state, _ = init()
        node = None

        def dispatch(msg: M) -> None:
            nonlocal state
            nonlocal node
            (state, _) = self.update(msg, state)
            (node, _) = patch(node, self.view(state))

        patch = self.make_patch(dispatch)

        (node, _) = patch(None, self.view(state))

        if node is not None and node.target is not None:
            mount(node.target)

    @classmethod
    def _patch(
        cls,
        create_element: Callable[[str, dict[str, Any], list[N], Dispatch[M]], Target],
        create_text: Callable[[str], Target],
        dispatch: Dispatch[M],
        node: Node | None,
        vdom: VDom | None,
    ) -> tuple[Node | None, list[Patch]]:
        match (node, vdom):
            case (None, None):
                return (None, [])
            case (NodeElement() as node, None):
                return (None, [PatchRemoveChild(child=node.target.unwrap())])
            case (None, VDomText(text)):
                target = create_text(text)
                return (
                    NodeText(text=text, target=target),
                    [PatchInsertChild(child=target.unwrap(), reference=None)],
                )
            case (NodeElement() as node, VDomText(text)):
                new_target = create_text(text)
                return (
                    NodeText(text=text, target=new_target),
                    [
                        PatchInsertChild(
                            child=new_target.unwrap(), reference=node.target
                        ),
                        PatchRemoveChild(child=node.target.unwrap()),
                    ],
                )
            case (NodeText(node_text) as node, VDomText(vdom_text)):
                if node_text == vdom_text:
                    return (node, [])

                node.target.apply(PatchText(text=vdom_text))
                return (NodeText(text=vdom_text, target=node.target), [])

            case (None, VDomElement(tag, props, children)):
                node_children: list[Node] = []
                target = create_element(tag, props, [], dispatch)
                for c in children:
                    (new_node, patches_to_parent) = cls._patch(
                        create_element=create_element,
                        create_text=create_text,
                        dispatch=dispatch,
                        node=None,
                        vdom=c,
                    )
                    if new_node is not None:
                        node_children.append(new_node)
                    for p in patches_to_parent:
                        target.apply(p)

                return (
                    NodeElement(
                        tag=tag, props=props, children=node_children, target=target
                    ),
                    [PatchInsertChild(child=target.unwrap(), reference=None)],
                )
            case (
                NodeElement(
                    tag=node_tag,
                    props=node_props,
                    children=node_children,
                    target=target,
                ),
                VDomElement(tag, props, children),
            ) if node_tag == tag:
                if node_props != props:
                    del_keys = list(set(node_props.keys()) - set(props.keys()))
                    add_props = {
                        k: v
                        for k, v in props.items()
                        if k not in node_props
                        or (k in node_props and node_props[k] != v)
                    }
                    target.apply(PatchProps(remove_keys=del_keys, add_props=add_props))

                new_children: list[Node] = []
                for n, vd in zip_longest(node_children, children):
                    (new_node, patches_to_parent) = cls._patch(
                        create_element, create_text, dispatch, n, vd
                    )
                    if new_node is not None:
                        new_children.append(new_node)
                    for p in patches_to_parent:
                        target.apply(p)
                return (
                    NodeElement(
                        tag=tag, props=props, children=new_children, target=target
                    ),
                    [],
                )
            case (NodeElement() as node, VDomElement(tag, props, children)):
                node_children = []
                new_target = create_element(tag, props, [], dispatch)
                for c in children:
                    (new_node, patches_to_parent) = cls._patch(
                        create_element=create_element,
                        create_text=create_text,
                        dispatch=dispatch,
                        node=None,
                        vdom=c,
                    )
                    if new_node is not None:
                        node_children.append(new_node)
                    for p in patches_to_parent:
                        new_target.apply(p)

                return (
                    NodeElement(
                        tag=tag, props=props, children=node_children, target=new_target
                    ),
                    [
                        PatchInsertChild(
                            child=new_target.unwrap(), reference=node.target
                        ),
                        PatchRemoveChild(child=node.target.unwrap()),
                    ],
                )
            case (_, _):
                raise AssertionError(f"unexpected: {node} {vdom}")
