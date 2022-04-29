import curses
from dataclasses import dataclass
from typing import Any

from alfort import Alfort, Dispatch, Effect, Init, Update, View
from alfort.vdom import Node, Patch, PatchInsertChild, PatchText, Props, VDom


@dataclass(frozen=True)
class CountUp:
    ...


@dataclass(frozen=True)
class CountDown:
    ...


Msg = CountUp | CountDown


def draw_text(stdscr: Any, text: str) -> None:
    stdscr.addstr(0, 0, text)
    stdscr.clrtoeol()
    stdscr.refresh()


class TextNode(Node):
    dispatch: Dispatch[Msg]
    text: str
    stdscr: Any

    def __init__(self, text: str, dispatch: Dispatch[Msg], stdscr: Any) -> None:
        self.text = text
        TextNode.dispatch = dispatch
        self._stdscr = stdscr

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchText(new_text):
                self.text = new_text
                draw_text(self._stdscr, self.text)
            case _:
                raise ValueError(f"Invalid patch: {patch}")


class ContainerNode(Node):
    children: list["CounterNode"]
    stdscr: Any

    def __init__(self, stdscr: Any) -> None:
        self.children = []
        self._stdscr = stdscr

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchInsertChild(child):
                self.children.append(child)
                draw_text(self._stdscr, child.text)
            case _:
                raise ValueError(f"Invalid patch: {patch}")


CounterNode = TextNode | ContainerNode


class AlfortSimpleCounter(Alfort[dict[str, Any], Msg, CounterNode]):
    stdscr: Any

    def __init__(
        self,
        init: Init[dict[str, Any], Msg],
        view: View[dict[str, Any]],
        update: Update[Msg, dict[str, Any]],
        stdscr: Any,
    ) -> None:
        super().__init__(init=init, view=view, update=update)
        self.stdscr = stdscr

    def create_text(
        self,
        text: str,
        dispatch: Dispatch[Msg],
    ) -> TextNode:
        return TextNode(text, dispatch, self.stdscr)

    def create_element(
        self,
        tag: str,
        props: Props,
        children: list[CounterNode],
        dispatch: Dispatch[Msg],
    ) -> ContainerNode:
        return ContainerNode(self.stdscr)

    def main(
        self,
        root_node: ContainerNode,
    ) -> None:
        self.stdscr.clear()
        self._main(root_node)
        while True:
            c = self.stdscr.getch()
            if c == ord("q"):
                break
            elif c == ord("u"):
                TextNode.dispatch(CountUp())
            elif c == ord("d"):
                TextNode.dispatch(CountDown())


def main(stdscr: Any) -> None:
    curses.curs_set(0)

    def view(state: dict[str, int]) -> VDom:
        return f"Count(press 'u' - up, 'd' - down', 'q' - quit): {state['count']}"

    def init() -> tuple[dict[str, int], list[Effect[Msg]]]:
        return ({"count": 0}, [])

    def update(
        msg: Msg, state: dict[str, int]
    ) -> tuple[dict[str, int], list[Effect[Msg]]]:
        match msg:
            case CountUp():
                return ({"count": state["count"] + 1}, [])
            case CountDown():
                return ({"count": state["count"] - 1}, [])

    app = AlfortSimpleCounter(init=init, view=view, update=update, stdscr=stdscr)
    app.main(ContainerNode(stdscr))


if __name__ == "__main__":
    curses.wrapper(main)
