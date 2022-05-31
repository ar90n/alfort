import curses
from enum import Enum, auto
from typing import Any, Callable

from alfort import Alfort, Dispatch, Effect
from alfort.sub import Subscription, UnSubscription, subscription
from alfort.vdom import Node, Patch, PatchText, Props, VDom

handlers: dict[str, Callable[[], None]] = {}

stdscr = curses.initscr()


class Msg(Enum):
    Up = auto()
    Down = auto()


class TextNode(Node):
    stdscr: Any

    def __init__(self, text: str, dispatch: Dispatch[Msg]) -> None:
        self._draw_text(text)

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchText(new_text):
                self._draw_text(new_text)
            case _:
                raise ValueError(f"Invalid patch: {patch}")

    def _draw_text(self, text: str) -> None:
        stdscr.addstr(0, 0, text)
        stdscr.clrtoeol()
        stdscr.refresh()


class AlfortSimpleCounter(Alfort[int, Msg, TextNode]):
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
        children: list[TextNode],
        dispatch: Dispatch[Msg],
    ) -> TextNode:
        raise ValueError("create_element should not be called")

    def main(
        self,
    ) -> None:
        self._main()


def main(stdscr: Any) -> None:
    curses.curs_set(0)
    stdscr.clear()

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

    def subscriptions(state: int) -> list[Subscription[Msg]]:
        @subscription()
        def on_keydown(dispatch: Dispatch[Msg]) -> UnSubscription:
            handlers["u"] = lambda: dispatch(Msg.Up)
            handlers["d"] = lambda: dispatch(Msg.Down)
            return lambda: handlers.clear()

        return [on_keydown]

    app = AlfortSimpleCounter(
        init=init, view=view, update=update, subscriptions=subscriptions
    )
    app.main()
    while True:
        c = chr(stdscr.getch())
        if c == "q":
            break
        if handle := handlers.get(c):
            handle()


if __name__ == "__main__":
    try:
        main(stdscr)
    finally:
        curses.endwin()
