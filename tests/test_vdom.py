from typing import Any
from unittest.mock import Mock

import pytest

from alfort.vdom import (
    MirrorNodeElement,
    MirrorNodeText,
    PatchChildren,
    PatchProps,
    PatchReplace,
    PatchText,
    VirtualNodeElement,
    VirtualNodeText,
    patch,
    Node,
    Patch,
    element,
    text,
)


class MockNode(Node):
    def __init__(self) -> None:
        self._patches = []

    def unwrap(self) -> Any:
        return self._patches

    def apply(self, patch: Patch) -> None:
        self._patches.append(patch)


class VNodeNode(Node):
    def __init__(self) -> None:
        self._node = None

    def unwrap(self) -> Any:
        return self._node

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchReplace():
                self._node = VirtualNodeElement(patch.tag, patch.props, patch.children)
            case PatchChildren():
                self._node = VirtualNodeElement(self._node.tag, self._node.props, patch.children)
            case PatchProps():
                for k in patch.del_keys:
                    self._node.props.pop(k)
                self._node.props.update(patch.add_props)
            case PatchText():
                self._node = VirtualNodeText(patch.text)


def test_construct_virtual_node():
    node = element("div", props={"display": "flex"}, children=[text("abc")])

    assert node.tag == "div"
    assert node.props == {"display": "flex"}
    assert len(node.children) == 1
    assert node.children[0] == VirtualNodeText("abc")


@pytest.mark.parametrize(
    "mirror_node_root, virtual_node_root, expected_patches",
    [
        (
            None,
            element("div", {"display": "flex"}),
            [PatchReplace("div", {"display": "flex"}, [])],
        ),
        (
            None,
            element("div", {"display": "flex"}, [element("br"), element("br")]),
            [
                PatchReplace(
                    "div",
                    {"display": "flex"},
                    [[PatchReplace("br", {}, [])], [PatchReplace("br", {}, [])]],
                )
            ],
        ),
        (
            MirrorNodeText("abc", node=MockNode()),
            element("div", {"display": "flex"}),
            [PatchReplace("div", {"display": "flex"}, [])],
        ),
        (
            MirrorNodeElement(
                "div",
                {"display": "absolute", "width": "100px"},
                children=[],
                node=MockNode(),
            ),
            element("div", {"display": "flex", "height": "100px"}),
            [
                PatchProps(
                    add_props={"display": "flex", "height": "100px"}, del_keys=["width"]
                )
            ],
        ),
        (
            MirrorNodeElement("div", {"display": "flex"}, children=[], node=MockNode()),
            element("div", {"display": "flex"}, children=[element("br")]),
            [PatchChildren([[PatchReplace("br", {}, [])]])],
        ),
        (
            None,
            text("abc"),
            [PatchText("abc")],
        ),
        (
            MirrorNodeText("def", node=MockNode()),
            text("abc"),
            [PatchText("abc")],
        ),
        (
            MirrorNodeElement("div", {"display": "flex"}, children=[], node=MockNode()),
            element("div", {"display": "flex"}),
            [],
        ),
    ],
)
def test_make_patch(mirror_node_root, virtual_node_root, expected_patches):
    root = patch(MockNode, mirror_node_root, virtual_node_root)

    assert root.node.unwrap() == expected_patches


@pytest.mark.parametrize(
    "old_node_root, new_node_root",
    [
        (None, element("div", {"display": "flex"})),
        (element("div", {"display": "flex"}), element("div", {"display": "flex"})),
        (
            element("div", {"display": "flex"}),
            element("div", {"display": "flex"}, [element("br"), text("abc")]),
        ),
        (
            element("br"),
            element("div", {"display": "flex"}, [element("br"), text("abc")]),
        ),
        (
            element("div", children=[text("abc")]),
            text("abc")
        ),
    ],
)
def test_patch_nodes(old_node_root, new_node_root):
    mirror_node_root = patch(VNodeNode, None, old_node_root)
    patched_node_root = patch(
        VNodeNode, mirror_node=mirror_node_root, virtual_node=new_node_root
    )
    assert patched_node_root.node.unwrap() == new_node_root
