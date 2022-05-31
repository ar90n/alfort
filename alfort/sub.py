from typing import Any, Callable, Generic, Hashable, TypeAlias, TypeVar

Msg = TypeVar("Msg")
State = TypeVar("State")

Dispatch: TypeAlias = Callable[[Msg], None]
UnSubscribe: TypeAlias = Callable[[], None]
Subscribe: TypeAlias = Callable[[Dispatch[Msg]], UnSubscribe]
Subscriptions: TypeAlias = Callable[[State], list[Subscribe[Msg]]]


class Subscriber(Generic[State, Msg]):
    _subscriptions: Subscriptions[State, Msg] | None
    _unsubscribes: dict[Subscribe[Msg], UnSubscribe] = {}

    def __init__(
        self,
        subscriptions: Subscriptions[State, Msg] | None,
    ) -> None:
        self._subscriptions = subscriptions

    def update(self, state: State, dispatch: Dispatch[Msg]) -> None:
        if self._subscriptions is None:
            return

        rem_unscribes = self._unsubscribes
        self._unsubscribes = {}
        for s in self._subscriptions(state):
            if us := rem_unscribes.pop(s, None):
                self._unsubscribes[s] = us
            else:
                self._unsubscribes[s] = s(dispatch)

        for us in rem_unscribes.values():
            us()


class _Subscription(Generic[Msg]):
    def __init__(self, fun: Subscribe[Msg], key: Hashable) -> None:
        self._key = key
        self._fun = fun

    def __call__(self, dispatch: Dispatch[Msg]) -> UnSubscribe:
        return self._fun(dispatch)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, type(self)):
            return False
        if not isinstance(other._key, type(self._key)):
            return False

        return self._key == other._key

    def __hash__(self) -> int:
        return self._key.__hash__()


def subscription(
    key: Any | None = None,
) -> Callable[[Subscribe[Msg]], _Subscription[Msg]]:
    def _constructor(f: Callable[[Any], UnSubscribe]) -> _Subscription[Msg]:
        _key = key if key is not None else tuple(f.__code__.co_lines())
        return _Subscription[Msg](f, _key)

    return _constructor
