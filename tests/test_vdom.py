from dataclasses import dataclass
from typing import Any, TypeAlias, Union

import pytest

from alfort.vdom import (
    App,
    Dispatch,
    Effect,
    Node,
    NodeDom,
    NodeDomElement,
    NodeDomText,
    Patch,
    PatchInsertChild,
    PatchProps,
    PatchRemoveChild,
    PatchText,
    Props,
    Update,
    VDom,
    VDomElement,
    VDomText,
    View,
    el,
    text,
)


def to_vnode(node_dom: NodeDom) -> VDom:
    match node_dom:
        case NodeDomText():
            return text(node_dom.text)
        case NodeDomElement(tag, props, children):
            return el(tag, props, [to_vnode(child) for child in children])


State: TypeAlias = dict[str, Any]


class MockNode(Node):
    patches: list[Patch]

    def __init__(self) -> None:
        self.patches = []

    def apply(self, patch: Patch) -> None:
        self.patches.append(patch)


class MockApp(App[State, Any, MockNode]):

    mock_target: MockNode = MockNode()

    def __init__(self, view: View[State], update: Update[State, Any]) -> None:
        super().__init__(view, update)

    @classmethod
    def create_element(
        cls,
        tag: str,
        props: Props,
        children: list[MockNode],
        dispatch: Dispatch[Any],
    ) -> MockNode:
        return cls.mock_target

    @classmethod
    def create_text(cls, text: str) -> MockNode:
        return cls.mock_target


@dataclass(frozen=True)
class CountUp:
    value: int = 1


@dataclass(frozen=True)
class CountDown:
    value: int = 1


Msg = Union[CountUp, CountDown]


class VDomNode(Node):
    vdom: VDom
    dispatch: Dispatch[Msg]

    def __init__(self, vdom: VDom, dispatch: Dispatch[Msg]) -> None:
        self.vdom = vdom
        self.dispatch = dispatch

    def apply(self, patch: Patch) -> None:
        match (self.vdom, patch):
            case (
                VDomElement() as vdom_element,
                PatchInsertChild(child, reference),
            ) if isinstance(child, VDomNode):
                ind = len(vdom_element.children)
                if reference is not None:
                    ind = vdom_element.children.index(reference.vdom)
                vdom_element.children.insert(ind, child.vdom)
            case (VDomElement() as vdom_element, PatchRemoveChild(child)) if isinstance(
                child, VDomNode
            ):
                vdom_element.children.remove(child.vdom)
            case (VDomElement() as vdom_element, PatchProps(remove_keys, add_props)):
                for k in remove_keys:
                    del vdom_element.props[k]
                for k, v in add_props.items():
                    vdom_element.props[k] = v
            case (VDomText() as vdom_text, PatchText(text)):
                object.__setattr__(vdom_text, "text", text)
            case (_, _):
                raise ValueError(f"Invalid patch: {patch}")

    @classmethod
    def text(
        cls,
        text: str,
        dispatch: Dispatch[Msg] = lambda _: None,
    ) -> "VDomNode":
        return cls(vdom=VDomText(text=text), dispatch=dispatch)

    @classmethod
    def el(
        cls,
        tag: str,
        props: Props,
        children: list["VDomNode"],
        dispatch: Dispatch[Msg] = lambda _: None,
    ) -> "VDomNode":
        return cls(
            vdom=VDomElement(
                tag=tag,
                props=props,
                children=[c.vdom for c in children],
            ),
            dispatch=dispatch,
        )


class VDomApp(App[dict[str, Any], Msg, VDomNode]):
    @classmethod
    def create_text(
        cls,
        text: str,
    ) -> VDomNode:
        return VDomNode.text(text)

    @classmethod
    def create_element(
        cls,
        tag: str,
        props: Props,
        children: list[VDomNode],
        dispatch: Dispatch[Msg],
    ) -> VDomNode:
        return VDomNode.el(tag, props, children, dispatch)


def test_construct_vdom() -> None:
    vdom = el(
        "div", {"width": "100px"}, [text("hello"), el("span", {}, [text("world")])]
    )

    assert vdom.tag == "div"
    assert vdom.props == {"width": "100px"}
    assert len(vdom.children) == 2
    assert isinstance(vdom.children[0], VDomText)
    assert vdom.children[0].text == "hello"
    assert isinstance(vdom.children[1], VDomElement)
    assert vdom.children[1].tag == "span"
    assert vdom.children[1].props == {}
    assert len(vdom.children[1].children) == 1


@pytest.mark.parametrize(
    "old_vdom, new_vdom, expected_patches, expected_root_patches",
    [
        (
            None,
            el("div", {"display": "flex"}),
            [],
            [PatchInsertChild],
        ),
        (
            None,
            el("div", {"display": "flex"}, [el("br"), el("br")]),
            [PatchInsertChild, PatchInsertChild],
            [PatchInsertChild],
        ),
        (
            el(
                "div",
                {"display": "absolute", "width": "100px"},
                [el("br"), text("abc"), el("br"), el("br")],
            ),
            el(
                "div",
                {"display": "flex", "height": "100px"},
                [el("br"), text("hello"), text("world")],
            ),
            [
                PatchProps,
                PatchText,
                PatchInsertChild,
                PatchRemoveChild,
                PatchRemoveChild,
            ],
            [],
        ),
        (
            None,
            text("abc"),
            [],
            [PatchInsertChild],
        ),
    ],
)
def test_apply_patch(
    old_vdom: VDom | None,
    new_vdom: VDom,
    expected_patches: list[type[Patch]],
    expected_root_patches: list[type[Patch]],
) -> None:
    def dispatch(_: Any) -> None:
        pass

    (node_dom, _) = MockApp.patch(dispatch, None, old_vdom)
    MockApp.mock_target.patches.clear()

    (node, patches_to_parent) = MockApp.patch(dispatch, node_dom, new_vdom)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in MockApp.mock_target.patches] == expected_patches

    assert node is not None
    assert to_vnode(node) == new_vdom


@pytest.mark.parametrize(
    "old_vdom, expected_patches, expected_root_patches",
    [
        (
            el(
                "div",
                {},
                children=[],
            ),
            [],
            [PatchRemoveChild],
        ),
        (None, [], []),
    ],
)
def test_apply_remove_child_patch(
    old_vdom: VDom | None,
    expected_patches: list[type[Patch]],
    expected_root_patches: list[type[Patch]],
) -> None:
    def dispatch(_: Any) -> None:
        pass

    (node, _) = MockApp.patch(dispatch, None, old_vdom)
    MockApp.mock_target.patches.clear()

    (node, patches_to_parent) = MockApp.patch(dispatch, node, None)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in MockApp.mock_target.patches] == expected_patches

    assert node is None


def test_update_state() -> None:
    def view(state: dict[str, int]) -> VDom:
        return el(
            "div",
            {},
            [
                text(str(state["count"])),
            ],
        )

    def init() -> tuple[dict[str, int], list[Effect[Msg]]]:
        return ({"count": 0}, [lambda dispatch: dispatch(CountUp(3))])

    def update(
        msg: Msg, state: dict[str, int]
    ) -> tuple[dict[str, int], list[Effect[Msg]]]:
        match msg:
            case CountUp(value):
                return ({"count": state["count"] + value}, [])
            case CountDown(value):
                return ({"count": state["count"] - value}, [])

    dispatch: Dispatch[Msg] = lambda _: None
    root: VDom | None = None

    def mount(target: VDomNode) -> None:
        nonlocal root
        nonlocal dispatch
        root = target.vdom
        dispatch = target.dispatch

    app = VDomApp(view=view, update=update)
    app(mount=mount, init=init)

    assert root == view({"count": 3})
    dispatch(CountUp())
    assert root == view({"count": 4})
    dispatch(CountDown())
    assert root == view({"count": 3})
