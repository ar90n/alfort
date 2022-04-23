from alfort.vdom import VDomElement, el


def test_construct_vdom() -> None:
    vdom = el("div", {"width": "100px"}, ["hello", el("span", {}, ["world"])])

    assert vdom.tag == "div"
    assert vdom.props == {"width": "100px"}
    assert len(vdom.children) == 2
    assert isinstance(vdom.children[0], str)
    assert vdom.children[0] == "hello"
    assert isinstance(vdom.children[1], VDomElement)
    assert vdom.children[1].tag == "span"
    assert vdom.children[1].props == {}
    assert len(vdom.children[1].children) == 1
