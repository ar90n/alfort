from typing import Any

import pytest

from alfort.vdom import (
    MirrorNode,
    MirrorNodeElement,
    MirrorNodeText,
    Node,
    Patch,
    PatchChildren,
    PatchProps,
    PatchReplace,
    PatchText,
    VirtualNode,
    VirtualNodeElement,
    VirtualNodeText,
    element,
    patch,
    text,
)


class MockNode(Node):
    _patches: list[Patch]

    def __init__(self) -> None:
        self._patches = []

    def unwrap(self) -> Any:
        return self._patches

    def apply(self, patch: Patch) -> None:
        self._patches.append(patch)


class VNodeNode(Node):
    _node: VirtualNode | None

    def __init__(self) -> None:
        self._node = None

    def unwrap(self) -> Any:
        return self._node

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchReplace():
                self._node = VirtualNodeElement(patch.tag, patch.props, patch.children)
            case PatchChildren():
                if not isinstance(self._node, VirtualNodeElement):
                    raise ValueError("Only to apply children to elements")

                self._node = VirtualNodeElement(
                    self._node.tag, self._node.props, patch.children
                )
            case PatchProps():
                if not isinstance(self._node, VirtualNodeElement):
                    raise ValueError("Only to apply props to an element node")

                for k in patch.del_keys:
                    self._node.props.pop(k)
                self._node.props.update(patch.add_props)
            case PatchText():
                self._node = VirtualNodeText(patch.text)


def test_construct_virtual_node() -> None:
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
def test_make_patch(
    mirror_node_root: MirrorNode | None,
    virtual_node_root: VirtualNode | None,
    expected_patches: list[Patch],
) -> None:
    root = patch(MockNode, mirror_node_root, virtual_node_root)

    if root is None:
        assert virtual_node_root is None
    else:
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
        (element("div", children=[text("abc")]), text("abc")),
    ],
)
def test_patch_nodes(
    old_node_root: VirtualNode | None, new_node_root: VirtualNode | None
) -> None:
    mirror_node_root = patch(VNodeNode, None, old_node_root)
    patched_node_root = patch(
        VNodeNode, mirror_node=mirror_node_root, virtual_node=new_node_root
    )

    if patched_node_root is None:
        assert patched_node_root is new_node_root is None
    else:
        assert patched_node_root.node.unwrap() == new_node_root
