from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

import pytest

from alfort import Alfort, Dispatch, Effect
from alfort.app import NodeDom, NodeDomElement, NodeDomText
from alfort.sub import Subscription, UnSubscription, subscription
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

T = TypeVar("T", bound=Node)


def to_vnode(node_dom: NodeDom) -> VDom:
    match node_dom:
        case NodeDomText():
            return node_dom.value
        case NodeDomElement(tag, props, children):
            return el(tag, props, [to_vnode(child) for child in children])


class RootNode(Node, Generic[T]):
    child: T | None

    def __init__(self) -> None:
        self.child = None

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchInsertChild(child):
                self.child = child
            case _:
                raise ValueError(f"Invalid patch: {patch}")


class MockNode(Node):
    patches: list[Patch]

    def __init__(self) -> None:
        self.patches = []

    def apply(self, patch: Patch) -> None:
        self.patches.append(patch)


class AlfortMock(Alfort[dict[str, Any], Any, MockNode]):
    mock_target: MockNode = MockNode()

    def create_element(
        self,
        tag: str,
        props: Props,
        children: list[MockNode],
        dispatch: Dispatch[Any],
    ) -> MockNode:
        return AlfortMock.mock_target

    def create_text(self, text: str, dispatch: Dispatch[Any]) -> MockNode:
        return AlfortMock.mock_target

    def main(
        self,
    ) -> None:
        self._main(root_node=AlfortMock.mock_target)


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

    app = AlfortMock(
        init=lambda: ({}, []),
        view=lambda state: "",
        update=lambda _, state: (state, []),
    )
    (node_dom, _) = app.patch(dispatch, None, old_vdom)
    AlfortMock.mock_target.patches.clear()

    (node, patches_to_parent) = app.patch(dispatch, node_dom, new_vdom)
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

    app = AlfortMock(
        init=lambda: ({}, []),
        view=lambda state: "",
        update=lambda _, state: (state, []),
    )
    (node, _) = app.patch(dispatch, None, old_vdom)
    AlfortMock.mock_target.patches.clear()

    (node, patches_to_parent) = app.patch(dispatch, node, None)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in AlfortMock.mock_target.patches] == expected_patches

    assert node is None


@dataclass(frozen=True)
class CountUp:
    value: int = 1


@dataclass(frozen=True)
class CountDown:
    value: int = 1


Msg = CountUp | CountDown


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


class AlfortText(Alfort[dict[str, Any], Msg, TextNode | RootNode[TextNode]]):
    def create_text(
        self,
        text: str,
        dispatch: Dispatch[Msg],
    ) -> TextNode:
        return TextNode(text, dispatch)

    def create_element(
        self,
        tag: str,
        props: Props,
        children: list[TextNode | RootNode[TextNode]],
        dispatch: Dispatch[Msg],
    ) -> RootNode[TextNode]:
        return RootNode()

    def main(
        self,
        root_node: RootNode[TextNode],
    ) -> None:
        self._main(root_node=root_node)


def test_update_state() -> None:
    root = RootNode[TextNode]()

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

    app = AlfortText(init=init, view=view, update=update)
    app.main(root)

    assert root.child is not None
    assert root.child.text == "3"
    root.child.dispatch(CountUp())
    assert root.child.text == "4"
    root.child.dispatch(CountDown())
    assert root.child.text == "3"


def test_enqueue() -> None:
    root = RootNode[TextNode]()

    view_values: list[str | None] = []

    def capture(_: Dispatch[Msg]) -> None:
        nonlocal view_values
        if root.child is None:
            view_values.append(None)
        else:
            view_values.append(root.child.text)

    rendering_queue: list[Callable[[], None]] = []

    def enqueue(f: Callable[[], None]) -> None:
        rendering_queue.append(f)

    def render() -> None:
        for f in rendering_queue:
            f()

    def view(state: dict[str, int]) -> VDom:
        return str(state["count"])

    def init() -> tuple[dict[str, int], list[Effect[Msg]]]:
        return ({"count": 5}, [capture, lambda d: enqueue(lambda: capture(d))])

    def update(
        msg: Msg, state: dict[str, int]
    ) -> tuple[dict[str, int], list[Effect[Msg]]]:
        return (state, [])

    app = AlfortText(init=init, view=view, update=update, enqueue=enqueue)
    app.main(root)

    assert view_values == [None]
    render()
    assert view_values == [None, "5"]


def test_subscriptions() -> None:
    root = RootNode[TextNode]()

    def view(state: dict[str, int]) -> VDom:
        return str(state["count"])

    def init() -> tuple[dict[str, int], list[Effect[Msg]]]:
        return ({"count": 0}, [])

    def update(
        msg: Msg, state: dict[str, int]
    ) -> tuple[dict[str, int], list[Effect[Msg]]]:
        match msg:
            case CountUp(value):
                return ({"count": state["count"] + value}, [])
            case CountDown(value):
                return ({"count": state["count"] - value}, [])

    countup = None

    def subscriptions(state: dict[str, int]) -> list[Subscription[Msg]]:
        @subscription()
        def on_countup(dispatch: Dispatch[Msg]) -> UnSubscription:
            nonlocal countup

            def _countup() -> None:
                dispatch(CountUp(1))

            countup = _countup

            def _unsubscribe():
                nonlocal countup
                countup = None

            return _unsubscribe

        return [on_countup] if state["count"] < 2 else []

    app = AlfortText(init=init, view=view, update=update, subscriptions=subscriptions)
    app.main(root)

    assert root.child is not None
    assert root.child.text == "0"
    assert countup is not None
    countup()
    assert root.child.text == "1"
    countup()
    assert root.child.text == "2"
    assert countup is None
