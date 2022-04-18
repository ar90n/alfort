from dataclasses import dataclass, replace
from typing import Any, Callable, Generic, Mapping, Optional, Tuple, TypeVar, Union

import pytest

from alfort.vdom import (
    App,
    Dispatch,
    Effect,
    Node,
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

S = TypeVar("S", bound=Mapping[str, Any])
M = TypeVar("M")


def remove_node(vdom: VDom) -> VDom:
    kwargs: dict[str, Any] = {
        "node": None,
    }
    if isinstance(vdom, VDomElement):
        kwargs["children"] = [remove_node(child) for child in vdom.children]
    return replace(vdom, **kwargs)


class MockNode(Node):
    _patches: list[Patch]

    def __init__(self) -> None:
        self._patches = []

    def unwrap(self) -> Any:
        return self._patches

    def apply(self, patch: Patch) -> None:
        self._patches.append(patch)


class VDomNode(Node):
    _vdom: VDom
    _dispatch: Optional[Callable[[Any], None]]

    def __init__(self, vdom: VDom, dispatch: Callable[[Any], None]) -> None:
        self._vdom = vdom
        self._dispatch = dispatch

    def unwrap(self) -> Any:
        return self._vdom

    def apply(self, patch: Patch) -> None:
        match (self._vdom, patch):
            case (VDomElement() as vdom_element, PatchInsertChild(child, reference)):
                ind = len(vdom_element.children)
                if reference is not None:
                    ind = vdom_element.children.index(reference.unwrap())
                vdom_element.children.insert(ind, child.unwrap())
            case (VDomElement() as vdom_element, PatchRemoveChild(child)):
                vdom_element.children.remove(child.unwrap())
            case (VDomElement() as vdom_element, PatchProps(remove_keys, add_props)):
                for k in remove_keys:
                    del vdom_element.props[k]
                for k, v in add_props.items():
                    vdom_element.props[k] = v
            case (VDomText() as vdom_text, PatchText(text)):
                object.__setattr__(vdom_text, "text", text)
            case (_, _):
                raise ValueError(f"Invalid patch: {patch}")

    @staticmethod
    def el(
        tag: str,
        props: Props,
        children: list["VDomNode"],
        dispatch: Optional[Callable[[Any], None]] = None,
    ) -> "VDomNode":
        def _dispatch(_: Any) -> None:
            pass

        if dispatch is None:
            dispatch = _dispatch
        return VDomNode(
            vdom=VDomElement(
                tag=tag, props=props, children=[c._vdom for c in children]
            ),
            dispatch=dispatch,
        )

    @staticmethod
    def text(text: str, dispatch: Optional[Callable[[Any], None]] = None) -> "VDomNode":
        def _dispatch(_: Any) -> None:
            pass

        if dispatch is None:
            dispatch = _dispatch
        return VDomNode(vdom=VDomText(text=text), dispatch=dispatch)


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


class MockApp(App[dict[str, Any], Any, Any]):
    mock_target: MockNode = MockNode()

    def __init__(
        self, view: View[dict[str, Any]], update: Update[dict[str, Any], Any]
    ) -> None:
        super().__init__(view, update)

    @classmethod
    def create_element(
        cls,
        tag: str,
        props: Props,
        children: list[Any],
        dispatch: Dispatch[Any],
    ) -> Node:
        return cls.mock_target

    @classmethod
    def create_text(cls, text: str) -> Node:
        return cls.mock_target


class VDomApp(Generic[S, M], App[S, M, VDomNode]):
    @classmethod
    def create_element(
        cls,
        tag: str,
        props: Props,
        children: list[VDomNode],
        dispatch: Dispatch[M],
    ) -> VDomNode:
        return VDomNode.el(tag, props, children, dispatch)

    @classmethod
    def create_text(cls, text: str) -> VDomNode:
        return VDomNode.text(text)


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
def test_make_patch(
    old_vdom: VDom | None,
    new_vdom: VDom,
    expected_patches: list[type[Patch]],
    expected_root_patches: list[type[Patch]],
) -> None:
    def dispatch(_: Any) -> None:
        pass

    (node, _) = MockApp.patch(dispatch, None, old_vdom)
    MockApp.mock_target.unwrap().clear()

    (node, patches_to_parent) = MockApp.patch(dispatch, node, new_vdom)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in MockApp.mock_target.unwrap()] == expected_patches

    assert node is not None
    assert remove_node(node) == new_vdom


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
def test_null_vdom(
    old_vdom: VDom | None,
    expected_patches: list[type[Patch]],
    expected_root_patches: list[type[Patch]],
) -> None:
    def dispatch(_: Any) -> None:
        pass

    (node, _) = MockApp.patch(dispatch, None, old_vdom)
    MockApp.mock_target.unwrap().clear()

    (node, patches_to_parent) = MockApp.patch(dispatch, node, None)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in MockApp.mock_target.unwrap()] == expected_patches

    assert node is None


def test_app() -> None:
    root = None

    def view(state: dict[str, int]) -> VDom:
        return el(
            "div",
            {},
            [
                el("span", {}, [text("count: ")]),
                el("span", {}, [text(str(state["count"]))]),
            ],
        )

    def init() -> Tuple[dict[str, int], list[Effect[Any]]]:
        return ({"count": 0}, [])

    def update(
        msg: Any, state: dict[str, int]
    ) -> Tuple[dict[str, int], list[Effect[Any]]]:
        return (state, [])

    def mount(target: VDomNode) -> None:
        nonlocal root
        root = target.unwrap()

    app = VDomApp[dict[str, int], int](
        update=update,
        view=view,
    )
    app(
        mount=mount,
        init=init,
    )

    assert root == view(init()[0])


def test_event() -> None:
    @dataclass(frozen=True)
    class CountUp:
        pass

    @dataclass(frozen=True)
    class CountDown:
        pass

    Msg = Union[CountUp, CountDown]

    def view(state: dict[str, int]) -> VDom:
        return el(
            "div",
            {},
            [
                text(str(state["count"])),
            ],
        )

    def init() -> Tuple[dict[str, int], list[Effect[Msg]]]:
        return ({"count": 0}, [])

    def update(
        msg: Msg, state: dict[str, int]
    ) -> Tuple[dict[str, int], list[Effect[Msg]]]:
        match msg:
            case CountUp():
                return ({"count": state["count"] + 1}, [])
            case CountDown():
                return ({"count": state["count"] - 1}, [])

    dispatch: Dispatch[Msg] = lambda _: None
    root: Optional[Any] = None

    def mount(target: VDomNode) -> None:  # type: ignore
        nonlocal root
        nonlocal dispatch
        root = target.unwrap()
        dispatch = target._dispatch  # type: ignore

    app = VDomApp(view=view, update=update)
    app(mount=mount, init=init)

    assert root == view({"count": 0})
    dispatch(CountUp())
    assert root == view({"count": 1})
    dispatch(CountDown())
    assert root == view({"count": 0})
