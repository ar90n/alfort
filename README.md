# Alfort
[![Build][build-shiled]][build-url]
[![Version][version-shield]][version-url]
[![Downloads][download-shield]][download-url]
[![Contributors][contributors-shield]][contributors-url]
[![Issues][issues-shield]][issues-url]
[![Codecov][codecov-shield]][codecov-url]
[![Apache License 2.0 License][license-shield]][license-url]

Alfort is simple and plain ELM-like interactive applicaiton framework for Python.
Alfort is motivated to provide declaretive UI framework independent from any backends.

Alfort is developping now. So there will be breaking changes.

## Features
* Rendering with Virtual DOM (this feature is truely inspired from hyperapp)
* Elm-like Movel-View-Update architecture
* Independent from Real DOM
* Simple implementation (under 1k loc)

## Installation
```bash
$ pip install alfort
```

## Example
Code
```python
from typing import Callable
from enum import Enum, auto

from click import prompt

from alfort import Alfort, Dispatch, Effect
from alfort.vdom import Node, Patch, PatchText, Props, VDOM


handlers: dict[str, Callable[[], None]] = {}


class Msg(Enum):
    Up = auto()
    Down = auto()


class TextNode(Node):
    def __init__(self, text: str) -> None:
        print(text)

    def apply(self, patch: Patch) -> None:
        match patch:
            case PatchText(new_text):
                print(new_text)
            case _:
                raise ValueError(f"Invalid patch: {patch}")


class AlfortSimpleCounter(Alfort[int, Msg, TextNode]):
    def create_text(
        self,
        text: str,
        dispatch: Dispatch[Msg],
    ) -> TextNode:
        handlers["u"] = lambda: dispatch(Msg.Up)
        handlers["d"] = lambda: dispatch(Msg.Down)
        return TextNode(text)

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
        while True:
            c = prompt("press u or d")
            if handle := handlers.get(c):
                handle()


def main() -> None:
    def view(state: int) -> VDOM:
        return f"Count: {state}"

    def init() -> tuple[int, list[Effect[Msg]]]:
        return (0, [])

    def update(msg: Msg, state: int) -> tuple[int, list[Effect[Msg]]]:
        match msg:
            case Msg.Up:
                return (state + 1, [])
            case Msg.Down:
                return (state - 1, [])

    app = AlfortSimpleCounter(init=init, view=view, update=update)
    app.main()


if __name__ == "__main__":
    main()
```

Output
```
Count: 0
press u or d: u
Count: 1
press u or d: u
Count: 2
press u or d: u
Count: 3
press u or d: d
Count: 2
press u or d: d
Count: 1
```

If you need more exmplaes, please check the [examples](https://github.com/ar90n/alfort/tree/main/examples).

## Concept
Alfort is inspired by TEA(The Elm Architecture). So Alfort makes you create an interactive application with `View`, `Model` and `Update`. If you need more specification about TEA, please see this [documentation](https://guide.elm-lang.org/architecture/).

Therefore, Alfort doesn't support Command. So Alfort uses functions whose type is `Callable[[Callable[[Msg], None]], None]` to achieve side effect.
You can run some tasks which have side effects in this function.  And, if you need, you can pass the result of side effect as Message to `dicpatch` which is given as an argument.
This idea is inspired by [hyperapp](https://github.com/jorgebucaran/hyperapp).

For now, Alfort doesn't support the following features.

* Event subscription
* Virtual DOM comparison by key
* Port to the outside of runtime.

Alfort doesn't provide Real DOM or other Widgets manupulation.
But there is an iterface between your concrete target and Alfort's Virtual DOM.
It is `Patche`.  So you have to implement some codes to handle some patches.
[alfort-dom](https://github.com/ar90n/alfort-dom) is an implementation for manupulation DOM.

## For development
### Install Poery plugins
```bash
$ poetry self add "poethepoet[poetry_plugin]"
```

### Run tests
```bash
$ poetry poe test
```

### Run linter and formatter
```bash
$ poetry poe check
```

## See Also
* [Elm](https://elm-lang.org/)
* [hyperapp](https://elm-lang.org/)

## License
[Apache-2.0](https://github.com/ar90n/alfort/blob/main/LICENSE)

[download-shield]: https://img.shields.io/pypi/dm/alfort?style=flat
[download-url]: https://pypi.org/project/alfort/
[version-shield]: https://img.shields.io/pypi/v/alfort?style=flat
[version-url]: https://pypi.org/project/alfort/
[build-shiled]: https://img.shields.io/github/workflow/status/ar90n/alfort/CI%20testing/main
[build-url]: https://github.com/ar90n/alfort/actions/workflows/ci-testing.yml
[contributors-shield]: https://img.shields.io/github/contributors/ar90n/alfort.svg?style=flat
[contributors-url]: https://github.com/ar90n/alfort/graphs/contributors
[issues-shield]: https://img.shields.io/github/issues/ar90n/alfort.svg?style=flat
[issues-url]: https://github.com/ar90n/alfort/issues
[license-shield]: https://img.shields.io/github/license/ar90n/alfort.svg?style=flat
[license-url]: https://github.com/ar90n/alfort/blob/master/LICENSE.txt
[codecov-shield]: https://codecov.io/gh/ar90n/alfort/branch/main/graph/badge.svg?token=8GKU96ODLY
[codecov-url]: https://codecov.io/gh/ar90n/alfort
