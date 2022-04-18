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
Effect: TypeAlias = Callable[[Dispatch[M]], None]
View: TypeAlias = Callable[[S], Optional[VDom]]
Update: TypeAlias = Callable[[M, S], tuple[S, list[Effect[M]]]]
Init: TypeAlias = Callable[[], tuple[S, list[Effect[M]]]]
Mount: TypeAlias = Callable[[Target], None]


class App(Generic[S, M, N]):
    def __init__(self, view: View[S], update: Update[M, S]) -> None:
        self.view = view
        self.update = update

    def __call__(
        self,
        init: Init[S, M],
        mount: Mount,
    ) -> None:
        state, effects = init()
        node = None

        def dispatch(msg: M) -> None:
            nonlocal state
            nonlocal node
            (state, effects) = self.update(msg, state)
            self._run_effects(dispatch, effects)
            (node, _) = self.patch(dispatch, node, self.view(state))

        self._run_effects(dispatch, effects)
        (node, _) = self.patch(dispatch, None, self.view(state))

        if node is not None and node.target is not None:
            mount(node.target)

    def _run_effects(self, dispatch: Dispatch[M], effects: list[Effect[M]]) -> None:
        for e in effects:
            e(dispatch)

    @classmethod
    @abstractmethod
    def create_element(
        cls,
        tag: str,
        props: dict[str, Any],
        children: list[N],
        dispatch: Dispatch[M],
    ) -> Target:
        raise NotImplementedError("create_element")

    @classmethod
    @abstractmethod
    def create_text(cls, text: str) -> Target:
        raise NotImplementedError("create_text")

    @classmethod
    def patch_props(
        cls, node_props: dict[str, Any], vdom_props: dict[str, Any]
    ) -> PatchProps:
        remove_keys = set(node_props.keys()) - set(vdom_props.keys())
        add_props = {
            k: v
            for k, v in vdom_props.items()
            if k not in node_props or (node_props[k] != v)
        }
        return PatchProps(remove_keys=list(remove_keys), add_props=add_props)

    @classmethod
    def patch_children(
        cls,
        dispatch: Dispatch[M],
        node_children: list[Node],
        vdom_children: list[VDom],
    ) -> Tuple[list[Node], list[Patch]]:
        new_children: list[Node] = []
        patches_to_parent: list[Patch] = []
        for n, vd in zip_longest(node_children, vdom_children):
            (new_child, patches_to_self) = cls.patch(dispatch, n, vd)
            if new_child is not None:
                new_children.append(new_child)
            patches_to_parent.extend(patches_to_self)
        return (new_children, patches_to_parent)

    @classmethod
    def patch_replace(
        cls,
        target: Target,
        node: Node | None,
    ) -> list[Patch]:
        reference = None
        patches_to_parent: list[Patch] = []
        if isinstance(node, Node):
            reference = node.target.unwrap()
            patches_to_parent.append(PatchRemoveChild(child=reference))
        patches_to_parent.insert(
            0, PatchInsertChild(child=target.unwrap(), reference=reference)
        )
        return patches_to_parent

    @classmethod
    def patch(
        cls,
        dispatch: Dispatch[M],
        node: Node | None,
        vdom: VDom | None,
    ) -> tuple[Node | None, list[Patch]]:
        match (node, vdom):
            case (_, None):
                patches_to_self: list[Patch] = []
                if isinstance(node, Node):
                    patches_to_self.append(PatchRemoveChild(child=node.target.unwrap()))
                return (None, patches_to_self)
            case (NodeText(node_text) as node, VDomText(vdom_text)):
                if node_text == vdom_text:
                    return (node, [])

                node.target.apply(PatchText(text=vdom_text))
                return (NodeText(text=vdom_text, target=node.target), [])

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
                    target.apply(cls.patch_props(node_props, props))

                (new_children, patches_to_self) = cls.patch_children(
                    dispatch, node_children, children
                )
                for p in patches_to_self:
                    target.apply(p)
                return (
                    NodeElement(
                        tag=tag, props=props, children=new_children, target=target
                    ),
                    [],
                )
            case (_, VDomText(text)):
                target = cls.create_text(text)
                patches_to_parent = cls.patch_replace(target, node)
                return (NodeText(text=text, target=target), patches_to_parent)
            case (_, VDomElement(tag, props, children)):
                target = cls.create_element(tag, props, [], dispatch)
                patches_to_parent = cls.patch_replace(target, node)

                (new_children, patches_to_self) = cls.patch_children(
                    dispatch, [], children
                )
                for p in patches_to_self:
                    target.apply(p)

                return (
                    NodeElement(
                        tag=tag, props=props, children=new_children, target=target
                    ),
                    patches_to_parent,
                )
            case (_, _):
                raise AssertionError(f"unexpected: {node} {vdom}")
