from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

import pytest

from alfort.vdom import (
    Patch,
    PatchInsertChild,
    PatchProps,
    PatchRemoveChild,
    PatchText,
    Target,
    UpdateResult,
    VDom,
    VDomElement,
    VDomText,
    app,
    el,
    make_patch,
    text,
    to_vdom,
)


class MockTarget(Target):
    _patches: list[Patch]

    def __init__(self) -> None:
        self._patches = []

    def unwrap(self) -> Any:
        return self._patches

    def apply(self, patch: Patch) -> None:
        self._patches.append(patch)


class VDomTarget(Target):
    _vdom: VDom
    _dispatch: Optional[Callable[[Any], None]]

    def __init__(self, vdom: VDom, dispatch: Callable[[Any], None]) -> None:
        self._vdom = vdom
        self._dispatch = dispatch

    def unwrap(self) -> Any:
        return self._vdom

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchInsertChild(child, reference):
                ind = len(self._vdom.children)
                if reference is not None:
                    ind = self._vdom.children.index(reference)
                self._vdom.children.insert(ind, child)
            case PatchRemoveChild(child):
                self._vdom.children.remove(child)
            case PatchProps(remove_keys, add_props):
                for k in remove_keys:
                    del self._vdom.props[k]
                for k, v in add_props.items():
                    self._vdom.props[k] = v
            case PatchText(text):
                object.__setattr__(self._vdom, "text", text)

    @staticmethod
    def el(
        tag: str,
        props: dict,
        children: list,
        dispatch: Optional[Callable[[Any], None]] = None,
    ) -> "VDomTarget":
        return VDomTarget(
            vdom=VDomElement(tag=tag, props=props, children=children), dispatch=dispatch
        )

    @staticmethod
    def text(
        text: str, dispatch: Optional[Callable[[Any], None]] = None
    ) -> "VDomTarget":
        return VDomTarget(vdom=VDomText(text=text), dispatch=dispatch)


def test_construct_vdom():
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
            el(
                "div",
                {},
                children=[],
            ),
            None,
            [],
            [PatchRemoveChild],
        ),
        (
            None,
            text("abc"),
            [],
            [PatchInsertChild],
        ),
        (None, None, [], []),
    ],
)
def test_make_patch(
    old_vdom: VDom | None,
    new_vdom: VDom | None,
    expected_patches: list[type[Patch]],
    expected_root_patches: list[type[Patch]],
) -> None:
    mock_target = MockTarget()

    def create_element(
        tag: str, props: dict, children: list[Any], dispatch
    ) -> MockTarget:
        return mock_target

    def create_text(text: str) -> MockTarget:
        return mock_target

    patch = make_patch(create_element, create_text)

    ret = patch(None, old_vdom)
    mock_target.unwrap().clear()
    node = ret.node

    ret = patch(node, new_vdom)
    assert [type(p) for p in ret.patches_to_parent] == expected_root_patches
    assert [type(p) for p in mock_target.unwrap()] == expected_patches

    patched_vdom = ret.node
    if patched_vdom is not None:
        patched_vdom = to_vdom(patched_vdom)
    assert patched_vdom == new_vdom


def test_app():
    def create_element(
        tag: str, props: dict, children: list[Any], dispatch
    ) -> MockTarget:
        return VDomTarget.el(tag, props, children)

    def create_text(text: str) -> MockTarget:
        return VDomTarget.text(text)

    def view(state: dict[str, int]) -> VDom:
        return el(
            "div",
            {},
            [
                el("span", {}, [text("count: ")]),
                el("span", {}, [text(str(state["count"]))]),
            ],
        )

    def init():
        return {"count": 0}

    root = None

    def mount(target: Target) -> None:
        nonlocal root
        root = target.unwrap()

    app(
        create_element,
        create_text,
        mount=mount,
        init=init,
        view=view,
        update=lambda state, _: state,
    )

    assert root == view(init())


def test_event():
    def create_element(
        tag: str, props: dict, children: list[Any], dispatch
    ) -> MockTarget:
        return VDomTarget.el(tag, props, children, dispatch)

    def create_text(text: str) -> MockTarget:
        return VDomTarget.text(text)

    def view(state: dict[str, int]) -> VDom:
        return el(
            "div",
            {},
            [
                text(str(state["count"])),
            ],
        )

    def init():
        return {"count": 0}

    @dataclass(frozen=True)
    class CountUp:
        pass

    @dataclass(frozen=True)
    class CountDown:
        pass

    Msg = Union[CountUp, CountDown]

    def update(msg: Msg, state: dict[str, int]) -> UpdateResult[dict[str, int]]:
        match msg:
            case CountUp():
                return UpdateResult(state={"count": state["count"] + 1}, effects=[])
            case CountDown():
                return UpdateResult(state={"count": state["count"] - 1}, effects=[])

    dispatch = None
    root = None

    def mount(target: Target) -> None:
        nonlocal root
        nonlocal dispatch
        root = target.unwrap()
        dispatch = target._dispatch

    app(create_element, create_text, mount=mount, init=init, view=view, update=update)

    assert root == view({"count": 0})
    dispatch(CountUp())
    assert root == view({"count": 1})
    dispatch(CountDown())
    assert root == view({"count": 0})
