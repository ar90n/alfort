from venv import create
from alfort.vdom import PatchReplace, element, text, diff, PatchText


def test_construct_element():
    el = element(
        "ul",
        props={"class": "foo", "key": 123},
        children=[
            element("li", children=[text("a")]),
            element("li", children=[text("b")]),
            element("li", children=[text("c")]),
        ],
    )

    assert el is not None
    assert hash(el)
    assert el.tag == "ul"
    assert el.props == {"class": "foo", "key": 123}
    assert el.key == 123
    assert el.children[0].tag == "li"
    assert el.children[0].children[0].text == "a"
    assert el.children[0].key == 42
    assert el.count == 6


def test_diff_element():
    assert diff(None, None) == []
    assert diff(text("a"), None) == []
    assert diff(text("a"), text("b")) == [PatchText("b")]

    new_vnode = element("ul")
    assert diff(element("li"), new_vnode) == [PatchReplace(new_vnode)]

    old = element(
        "ul",
        props={"class": "foo", "key": 123},
        children=[
            element("li", children=[text("a")]),
            element("li", children=[text("b")]),
            element("li", children=[text("c")]),
        ],
    )
    new = element(
        "ul",
        props={"class": "foo", "key": 123},
        children=[
            element("li", children=[text("a")]),
            element("li", children=[text("c")]),
            element("li", children=[text("c")]),
        ],
    )
    assert diff(old, new) == [PatchText("c")]