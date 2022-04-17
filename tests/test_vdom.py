from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, Tuple, TypeVar, Union

import pytest

from alfort.vdom import (
    App,
    Patch,
    PatchInsertChild,
    PatchProps,
    PatchRemoveChild,
    PatchText,
    Target,
    VDom,
    VDomElement,
    VDomText,
    el,
    text,
    to_vdom,
)

S = TypeVar("S")
M = TypeVar("M")


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
        match (self._vdom, patch):
            case (VDomElement() as vdom_element, PatchInsertChild(child, reference)):
                ind = len(vdom_element.children)
                if reference is not None:
                    ind = vdom_element.children.index(reference)
                vdom_element.children.insert(ind, child)
            case (VDomElement() as vdom_element, PatchRemoveChild(child)):
                vdom_element.children.remove(child)
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
        props: dict,
        children: list,
        dispatch: Optional[Callable[[Any], None]] = None,
    ) -> "VDomTarget":
        def _dispatch(_: Any) -> None:
            pass

        if dispatch is None:
            dispatch = _dispatch
        return VDomTarget(
            vdom=VDomElement(tag=tag, props=props, children=children), dispatch=dispatch
        )

    @staticmethod
    def text(
        text: str, dispatch: Optional[Callable[[Any], None]] = None
    ) -> "VDomTarget":
        def _dispatch(_: Any) -> None:
            pass

        if dispatch is None:
            dispatch = _dispatch
        return VDomTarget(vdom=VDomText(text=text), dispatch=dispatch)


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


class MockApp(App):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._mock_target = MockTarget()

    def create_element(
        self,
        tag: str,
        props: dict,
        children: list[Any],
        dispatch: Callable[[Any], None],
    ) -> MockTarget:
        return self._mock_target

    def create_text(self, text: str) -> MockTarget:
        return self._mock_target


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
    app = MockApp(view=lambda _: new_vdom, update=lambda _, state: (state, []))

    patch = app.make_patch()

    (node, _) = patch(None, old_vdom)
    app._mock_target.unwrap().clear()

    (node, patches_to_parent) = patch(node, new_vdom)
    assert [type(p) for p in patches_to_parent] == expected_root_patches
    assert [type(p) for p in app._mock_target.unwrap()] == expected_patches

    patched_vdom = to_vdom(node) if node is not None else None
    assert patched_vdom == new_vdom


class VDomApp(Generic[S, M], App[S, M, Any]):
    def create_element(
        self,
        tag: str,
        props: dict,
        children: list[Any],
        dispatch: Callable[[Any], None],
    ) -> VDomTarget:
        return VDomTarget.el(tag, props, children, dispatch)

    def create_text(self, text: str) -> VDomTarget:
        return VDomTarget.text(text)


def test_app() -> None:
    def view(state: dict[str, int]) -> VDom:
        return el(
            "div",
            {},
            [
                el("span", {}, [text("count: ")]),
                el("span", {}, [text(str(state["count"]))]),
            ],
        )

    def init() -> Tuple[dict[str, int], list[Callable]]:
        return ({"count": 0}, [])

    root = None

    def mount(target: Target) -> None:
        nonlocal root
        root = target.unwrap()

    app = VDomApp[dict[str, int], int](
        update=lambda _, state: (state, []),
        view=view,
    )
    app(
        mount=mount,
        init=init,
    )

    assert root == view(init()[0])


def test_event() -> None:
    def view(state: dict[str, int]) -> VDom:
        return el(
            "div",
            {},
            [
                text(str(state["count"])),
            ],
        )

    def init() -> Tuple[dict[str, int], list[Callable]]:
        return ({"count": 0}, [])

    @dataclass(frozen=True)
    class CountUp:
        pass

    @dataclass(frozen=True)
    class CountDown:
        pass

    Msg = Union[CountUp, CountDown]

    def update(
        msg: Msg, state: dict[str, int]
    ) -> Tuple[dict[str, int], list[Callable]]:
        match msg:
            case CountUp():
                return ({"count": state["count"] + 1}, [])
            case CountDown():
                return ({"count": state["count"] - 1}, [])

    dispatch: Callable = lambda x: x
    root: Optional[Any] = None

    def mount(target: Target) -> None:  # type: ignore
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
