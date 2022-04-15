from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Callable, Generic, Optional, Protocol, TypeAlias, TypeVar, Union

T = TypeVar("T")


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


def with_target(cls: Any):
    class WithTarget(cls):
        target: Target

    return WithTarget


@dataclass(slots=True, frozen=True)
class Element(Generic[T]):
    tag: str
    props: dict[str, Any]
    children: list[T]


@dataclass(slots=True, frozen=True)
class Text:
    text: str


@dataclass(slots=True, frozen=True)
class VDomElement(Element["VDomElement"]):
    pass


@dataclass(slots=True, frozen=True)
class VDomText(Text):
    pass


VDom: TypeAlias = Union[VDomElement, VDomText]


@dataclass(slots=True, frozen=True)
@with_target
class NodeElement(Element["NodeElement"]):
    pass


#    def patch(self, cls: type[Node], virtual_node: VDomElement) -> 'MirrorNode':
#        new_children = []
#        for m_c, v_c in zip_longest(self.children, virtual_node.children):
#            res = patch2(cls, m_c, v_c)
#            if res[0]:
#                new_children.append(res[0])
#                for p in res[1]:
#                    self.node.apply(p)
#        return NodeElement(
#            tag=virtual_node.tag,
#            props=virtual_node.props,
#            children=new_children,
#            node=self.node,
#        )
#
#    def update(
#        self,
#        props: Optional[dict[str, Any]] = None,
#        children: Optional[list[Any]] = None,
#    ) -> 'NodeElement':
#        patches = []
#        if props is None:
#            props = {}
#        if children is None:
#            children = []
#
#        if props != self.props:
#            patches.append(PatchProps(props))
#        if children != self.children:
#            patches.append(PatchChildren(children=[c.node.unwrap() for c in children]))
#
#        if len(patches) == 0:
#            return self
#
#        for p in patches:
#            self.node.apply(p)
#        return NodeElement(
#            tag=self.tag,
#            props=props,
#            children=children,
#            node=self.node,
#        )
#
#    @staticmethod
#    def of(virtual_node: VDomElement, cls: type[Node]) -> 'NodeElement':
#        def _dispatch(virtual_node: VirtualNode, cls: type[Node]) -> MirrorNode:
#            match virtual_node:
#                case VDomElement():
#                    return NodeElement.of(virtual_node, cls)
#                case VirtualNodeText():
#                    return MirrorNodeText.of(virtual_node, cls)
#
#        new_children = [_dispatch(v_c, cls) for v_c in virtual_node.children]
#
#        node = cls()
#        node.apply(
#            PatchReplace(
#                tag=virtual_node.tag,
#                props=virtual_node.props,
#                children=[c.node.unwrap() for c in new_children],
#            )
#        )
#        return NodeElement(
#            tag=virtual_node.tag,
#            props=virtual_node.props,
#            children=new_children,
#            node=node,
#        )


@dataclass(slots=True, frozen=True)
@with_target
class NodeText(Text):
    pass


#    def update(self, text: str) -> 'NodeText':
#        if self.text == text:
#            return self
#
#        self.node.apply(PatchText(text=text))
#        return NodeText(text=text, node=self.node)
#
#    @staticmethod
#    def of(virtual_node: VirtualNodeText, cls: type[Node]) -> 'NodeText':
#        node = cls()
#        node.apply(PatchText(text=virtual_node.text))
#        return NodeText(text=virtual_node.text, node=node)


Node: TypeAlias = Union[NodeElement, NodeText]

# to support key


@dataclass
class PatchResult:
    node: Optional[Node]
    patches_to_parent: list[Patch]


def _patch(
    create_element: Callable[
        [str, dict[str, Any], list[Any], Callable[[Any], None]], Target
    ],
    create_text: Callable[[str], Target],
    dispatch: Callable[[Any], None],
    node: Optional[Node],
    vdom: Optional[VDom],
) -> PatchResult:
    match (node, vdom):
        case (None, None):
            return PatchResult(node=None, patches_to_parent=[])
        case (_, None):
            return PatchResult(
                node=None,
                patches_to_parent=[PatchRemoveChild(child=node.target.unwrap())],
            )
        case (None, VDomText(text)):
            target = create_text(text)
            return PatchResult(
                node=NodeText(text=text, target=target),
                patches_to_parent=[
                    PatchInsertChild(child=target.unwrap(), reference=None)
                ],
            )
        case (NodeElement(), VDomText(text)):
            new_target = create_text(text)
            return PatchResult(
                node=NodeText(text=text, target=new_target),
                patches_to_parent=[
                    PatchInsertChild(child=new_target.unwrap(), reference=node.target),
                    PatchRemoveChild(child=node.target.unwrap()),
                ],
            )
        case (NodeText(node_text), VDomText(vdom_text)):
            if node_text == vdom_text:
                return PatchResult(node=node, patches_to_parent=[])

            node.target.apply(PatchText(text=vdom_text))
            return PatchResult(
                node=NodeText(text=vdom_text, target=node.target), patches_to_parent=[]
            )

        case (None, VDomElement(tag, props, children)):
            node_children = []
            target = create_element(tag, props, [], dispatch)
            for c in children:
                ret = _patch(create_element, create_text, dispatch, None, c)
                node_children.append(ret.node)
                for p in ret.patches_to_parent:
                    target.apply(p)

            return PatchResult(
                node=NodeElement(
                    tag=tag, props=props, children=node_children, target=target
                ),
                patches_to_parent=[
                    PatchInsertChild(child=target.unwrap(), reference=None)
                ],
            )
        case (
            NodeElement(node_tag, node_props, node_children, target),
            VDomElement(tag, props, children),
        ) if node_tag == tag:
            if node_props != props:
                del_keys = set(node_props.keys()) - set(props.keys())
                add_props = {
                    k: v
                    for k, v in props.items()
                    if k not in node_props or (k in node_props and node_props[k] != v)
                }
                target.apply(PatchProps(remove_keys=del_keys, add_props=add_props))

            new_children = []
            for n, vd in zip_longest(node_children, children):
                ret = _patch(create_element, create_text, dispatch, n, vd)
                if ret.node is not None:
                    new_children.append(ret.node)
                for p in ret.patches_to_parent:
                    target.apply(p)
            return PatchResult(
                node=NodeElement(
                    tag=tag, props=props, children=new_children, target=target
                ),
                patches_to_parent=[],
            )
        case (_, VDomElement(tag, props, children)):
            node_children = []
            new_target = create_element(tag, props, [], dispatch)
            for c in children:
                ret = _patch(create_element, create_text, dispatch, None, c)
                node_children.append(ret.node)
                for p in ret.patches_to_parent:
                    new_target.apply(p)

            return PatchResult(
                node=NodeElement(
                    tag=tag, props=props, children=node_children, target=new_target
                ),
                patches_to_parent=[
                    PatchInsertChild(child=new_target.unwrap(), reference=node.target),
                    PatchRemoveChild(child=node.target.unwrap()),
                ],
            )


def to_vdom(node: Node) -> VDom:
    match node:
        case (NodeElement(tag, props, children)):
            return VDomElement(
                tag=tag, props=props, children=[to_vdom(c) for c in children]
            )
        case (NodeText(text)):
            return VDomText(text=text)
    raise ValueError(f"Unknown node type: {node}")


def el(
    tag: str,
    props: Optional[dict[str, Any]] = None,
    children: Optional[list[VDom]] = None,
) -> VDomElement:
    if props is None:
        props = {}
    if children is None:
        children = []
    return VDomElement(tag=tag, props=props, children=children)


def text(text: str) -> VDomText:
    return VDomText(text=text)


def make_patch(
    create_element: Callable[
        [str, dict[str, Any], list[Any], Callable[[Any], None]], Target
    ],
    create_text: Callable[[str], Target],
    dispatch: Optional[Callable[[Any], None]] = None,
) -> Callable[[Optional[Node], Optional[VDom]], PatchResult]:
    return lambda node, vdom: _patch(
        create_element=create_element,
        create_text=create_text,
        dispatch=dispatch,
        node=node,
        vdom=vdom,
    )


S = TypeVar("S")
M = TypeVar("M")


@dataclass(frozen=True)
class UpdateResult(Generic[S]):
    state: S
    effects: list[Callable]


def app(
    create_element: Callable[
        [str, dict[str, Any], list[Any], Callable[[Any], None]], Target
    ],
    create_text: Callable[[str], Target],
    mount: Callable[[Target], None],
    init: Callable[[], UpdateResult[S]],
    view: Callable[[S], VDom],
    update: Callable[[M, S], UpdateResult[S]],
) -> None:
    def dispatch(msg):
        nonlocal state
        nonlocal node
        update_result = update(msg, state)
        state = update_result.state
        patch_result = patch(node, view(state))
        node = patch_result.node

    patch = make_patch(create_element, create_text, dispatch)

    state = init()
    ret = patch(None, view(state))
    node = ret.node
    mount(node.target)
