from dataclasses import dataclass
from typing import Any, Union

import pytest

from alfort import Alfort, Dispatch, Effect, Init, Update, View
from alfort.app import Mount, NodeDom, NodeDomElement, NodeDomText
from alfort.vdom import (
    Node,
    Patch,
    PatchInsertChild,
    PatchProps,
    PatchRemoveChild,
    PatchText,
    Props,
    VDom,
    el,
)


def to_vnode(node_dom: NodeDom) -> VDom:
    match node_dom:
        case NodeDomText():
            return node_dom.value
        case NodeDomElement(tag, props, children):
            return el(tag, props, [to_vnode(child) for child in children])


class MockNode(Node):
    patches: list[Patch]

    def __init__(self) -> None:
        self.patches = []

    def apply(self, patch: Patch) -> None:
        self.patches.append(patch)


class AlfortMock(Alfort[dict[str, Any], Any, MockNode]):
    mock_target: MockNode = MockNode()

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
    def create_text(cls, text: str, dispatch: Dispatch[Any]) -> MockNode:
        return cls.mock_target

    @classmethod
    def main(
        cls,
        init: Init[dict[str, Any], Any],
        view: View[dict[str, Any]],
        update: Update[Any, dict[str, Any]],
    ) -> None:

        cls._main(
            init=init,
            view=view,
            update=update,
            mount=lambda node: None,
        )


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
                [el("br"), "abc", el("br"), el("br")],
            ),
            el(
                "div",
                {"display": "flex", "height": "100px"},
                [el("br"), "hello", "world"],
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
            "abc",
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

    (node_dom, _) = AlfortMock.patch(dispatch, None, old_vdom)
    AlfortMock.mock_target.patches.clear()

    (node, patches_to_parent) = AlfortMock.patch(dispatch, node_dom, new_vdom)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in AlfortMock.mock_target.patches] == expected_patches

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

    (node, _) = AlfortMock.patch(dispatch, None, old_vdom)
    AlfortMock.mock_target.patches.clear()

    (node, patches_to_parent) = AlfortMock.patch(dispatch, node, None)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in AlfortMock.mock_target.patches] == expected_patches

    assert node is None


@dataclass(frozen=True)
class CountUp:
    value: int = 1


@dataclass(frozen=True)
class CountDown:
    value: int = 1


Msg = Union[CountUp, CountDown]


class TextNode(Node):
    text: str
    dispatch: Dispatch[Msg]

    def __init__(self, text: str, dispatch: Dispatch[Msg]) -> None:
        self.text = text
        self.dispatch = dispatch

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchText(new_text):
                self.text = new_text
            case _:
                raise ValueError(f"Invalid patch: {patch}")


class AlfortText(Alfort[dict[str, Any], Msg, TextNode]):
    @classmethod
    def create_text(
        cls,
        text: str,
        dispatch: Dispatch[Msg],
    ) -> TextNode:
        return TextNode(text, dispatch)

    @classmethod
    def create_element(
        cls,
        tag: str,
        props: Props,
        children: list[TextNode],
        dispatch: Dispatch[Msg],
    ) -> TextNode:
        return TextNode("", dispatch)

    @classmethod
    def main(
        cls,
        init: Init[dict[str, Any], Msg],
        view: View[dict[str, Any]],
        update: Update[Msg, dict[str, Any]],
        mount: Mount[TextNode],
    ) -> None:
        cls._main(init=init, view=view, update=update, mount=mount)


def test_update_state() -> None:
    root = TextNode("", lambda _: None)

    def view(state: dict[str, int]) -> VDom:
        return str(state["count"])

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

    def mount(target: TextNode) -> None:
        nonlocal root
        root = target

    AlfortText.main(init=init, view=view, update=update, mount=mount)

    assert root.text == view({"count": 3})
    root.dispatch(CountUp())
    assert root.text == view({"count": 4})
    root.dispatch(CountDown())
    assert root.text == view({"count": 3})
