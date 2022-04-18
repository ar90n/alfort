from abc import abstractmethod
from dataclasses import dataclass, replace
from itertools import zip_longest
from typing import (
    Any,
    Callable,
    Generic,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Tuple,
    TypeAlias,
    TypeVar,
    Union,
)


@dataclass(slots=True, frozen=True)
class PatchProps:
    remove_keys: list[str]
    add_props: "Props"


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


class Node(Protocol):
    def apply(self, patch: Patch) -> None:
        ...


@dataclass(slots=True, frozen=True)
class VDomElement:
    tag: str
    props: "Props"
    children: list["VDom"]
    node: Node | None = None


@dataclass(slots=True, frozen=True)
class VDomText:
    text: str
    node: Node | None = None


VDom: TypeAlias = Union[VDomElement, VDomText]

N = TypeVar("N", bound=Node)
S = TypeVar("S", bound=Mapping[str, Any])
M = TypeVar("M")


UpdateResult: TypeAlias = Tuple[S, list[Callable[[], None]]]
Dispatch: TypeAlias = Callable[[M], None]
Effect: TypeAlias = Callable[[Dispatch[M]], None]
View: TypeAlias = Callable[[S], Optional[VDom]]
Update: TypeAlias = Callable[[M, S], tuple[S, list[Effect[M]]]]
Init: TypeAlias = Callable[[], tuple[S, list[Effect[M]]]]
Mount: TypeAlias = Callable[[N], None]
Props: TypeAlias = MutableMapping[str, Any]


class App(Generic[S, M, N]):
    def __init__(self, view: View[S], update: Update[M, S]) -> None:
        self.view = view
        self.update = update

    def __call__(
        self,
        init: Init[S, M],
        mount: Mount[N],
    ) -> None:
        state, effects = init()
        root = None

        def dispatch(msg: M) -> None:
            nonlocal state
            nonlocal root
            (state, effects) = self.update(msg, state)
            self._run_effects(dispatch, effects)
            (root, _) = self.patch(dispatch, root, self.view(state))

        self._run_effects(dispatch, effects)
        (root, _) = self.patch(dispatch, None, self.view(state))

        if root is not None and root.node is not None:
            mount(root.node)

    def _run_effects(self, dispatch: Dispatch[M], effects: list[Effect[M]]) -> None:
        for e in effects:
            e(dispatch)

    @classmethod
    @abstractmethod
    def create_element(
        cls,
        tag: str,
        props: Props,
        children: list[N],
        dispatch: Dispatch[M],
    ) -> N:
        raise NotImplementedError("create_element")

    @classmethod
    @abstractmethod
    def create_text(cls, text: str) -> Node:
        raise NotImplementedError("create_text")

    @classmethod
    def diff_props(cls, node_props: Props, vdom_props: Props) -> PatchProps:
        remove_keys = set(node_props.keys()) - set(vdom_props.keys())
        add_props = {
            k: v
            for k, v in vdom_props.items()
            if k not in node_props or (node_props[k] != v)
        }
        return PatchProps(remove_keys=list(remove_keys), add_props=add_props)

    @classmethod
    def diff_node(
        cls,
        node: Node,
        vdom: VDom | None,
    ) -> list[Patch]:
        reference = None
        patches_to_parent: list[Patch] = []
        if isinstance(vdom, VDom) and vdom.node is not None:
            reference = vdom.node
            patches_to_parent.append(PatchRemoveChild(child=reference))
        patches_to_parent.insert(0, PatchInsertChild(child=node, reference=reference))
        return patches_to_parent

    @classmethod
    def patch_children(
        cls,
        dispatch: Dispatch[M],
        node_children: list[VDom],
        vdom_children: list[VDom],
    ) -> Tuple[list[VDom], list[Patch]]:
        new_children: list[VDom] = []
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
        cur_vdom: VDom | None,
        new_vdom: VDom | None,
    ) -> tuple[VDom | None, list[Patch]]:
        match (cur_vdom, new_vdom):
            case (_, None):
                patches_to_self: list[Patch] = []
                if isinstance(cur_vdom, VDom) and cur_vdom.node is not None:
                    patches_to_self.append(PatchRemoveChild(child=cur_vdom.node))
                return (None, patches_to_self)
            case (
                VDomText(cur_text, cur_node),
                VDomText(new_text),
            ):
                if cur_node is None:
                    raise ValueError("cur_node is None")
                if cur_text == new_text:
                    return (cur_vdom, [])
                cur_node.apply(PatchText(text=new_text))
                return (replace(new_vdom, node=cur_node), [])
            case (
                VDomElement() as cur_vdom,
                VDomElement() as new_vdom,
            ) if cur_vdom.tag == new_vdom.tag:
                if cur_vdom.props != new_vdom.props and cur_vdom.node is not None:
                    cur_vdom.node.apply(cls.diff_props(cur_vdom.props, new_vdom.props))

                (new_children, patches_to_self) = cls.patch_children(
                    dispatch, cur_vdom.children, new_vdom.children
                )
                if cur_vdom.node is not None:
                    for p in patches_to_self:
                        cur_vdom.node.apply(p)
                return (
                    replace(new_vdom, children=new_children, node=cur_vdom.node),
                    [],
                )
            case (_, VDomText(new_text)):
                new_node = cls.create_text(new_text)
                patches_to_parent = cls.diff_node(new_node, cur_vdom)
                return (replace(new_vdom, node=new_node), patches_to_parent)
            case (_, VDomElement() as new_vdom):
                new_node = cls.create_element(
                    new_vdom.tag, new_vdom.props, [], dispatch
                )
                patches_to_parent = cls.diff_node(new_node, cur_vdom)

                (new_children, patches_to_self) = cls.patch_children(
                    dispatch, [], new_vdom.children
                )
                for p in patches_to_self:
                    new_node.apply(p)

                return (
                    replace(new_vdom, children=new_children, node=new_node),
                    patches_to_parent,
                )
            case (_, _):
                raise AssertionError(f"unexpected: {cur_vdom} {new_vdom}")


def el(
    tag: str,
    props: dict[str, Any] | None = None,
    children: list[VDom] | None = None,
    node: Node | None = None,
) -> VDomElement:
    if props is None:
        props = {}
    if children is None:
        children = []
    return VDomElement(tag=tag, props=props, children=children, node=node)


def text(text: str, node: Node | None = None) -> VDomText:
    return VDomText(text=text, node=node)
