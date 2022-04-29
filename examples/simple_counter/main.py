import curses
from enum import Enum, auto
from typing import Any, Callable

from alfort import Alfort, Dispatch, Effect, Init, Update, View
from alfort.vdom import Node, Patch, PatchText, Props, VDom

handlers: dict[str, Callable[[], None]] = {}


class Msg(Enum):
    Up = auto()
    Down = auto()


class TextNode(Node):
    stdscr: Any

    def __init__(self, text: str, dispatch: Dispatch[Msg], stdscr: Any) -> None:
        self._stdscr = stdscr
        handlers["u"] = lambda: dispatch(Msg.Up)
        handlers["d"] = lambda: dispatch(Msg.Down)
        self._draw_text(text)

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchText(new_text):
                self._draw_text(new_text)
            case _:
                raise ValueError(f"Invalid patch: {patch}")

    def _draw_text(self, text: str) -> None:
        self._stdscr.addstr(0, 0, text)
        self._stdscr.clrtoeol()
        self._stdscr.refresh()


class AlfortSimpleCounter(Alfort[int, Msg, TextNode]):
    stdscr: Any

    def __init__(
        self,
        init: Init[int, Msg],
        view: View[int],
        update: Update[Msg, int],
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
        children: list[TextNode],
        dispatch: Dispatch[Msg],
    ) -> TextNode:
        raise ValueError("create_element should not be called")

    def main(
        self,
    ) -> None:
        self.stdscr.clear()
        self._main()
        while True:
            c = chr(self.stdscr.getch())
            if c == "q":
                break
            if handle := handlers.get(c):
                handle()


def main(stdscr: Any) -> None:
    curses.curs_set(0)

    def view(state: int) -> VDom:
        return f"Count(press 'u' - up, 'd' - down', 'q' - quit): {state}"

    def init() -> tuple[int, list[Effect[Msg]]]:
        return (0, [])

    def update(msg: Msg, state: int) -> tuple[int, list[Effect[Msg]]]:
        match msg:
            case Msg.Up:
                return (state + 1, [])
            case Msg.Down:
                return (state - 1, [])

    app = AlfortSimpleCounter(init=init, view=view, update=update, stdscr=stdscr)
    app.main()


if __name__ == "__main__":
    curses.wrapper(main)
