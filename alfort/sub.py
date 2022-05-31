from typing import Any, Callable, Generic, Hashable, TypeAlias, TypeVar

Msg = TypeVar("Msg")
State = TypeVar("State")

Dispatch: TypeAlias = Callable[[Msg], None]
UnSubscription: TypeAlias = Callable[[], None]
Subscription: TypeAlias = Callable[[Dispatch[Msg]], UnSubscription]
Subscriptions: TypeAlias = Callable[[State], list[Subscription[Msg]]]


class Context(Generic[State, Msg]):
    _subscriptions: Subscriptions[State, Msg] | None
    _unsubscriptions: dict[Subscription[Msg], UnSubscription] = {}

    def __init__(
        self,
        subscriptions: Subscriptions[State, Msg] | None,
    ) -> None:
        self._subscriptions = subscriptions

    def update(self, state: State, dispatch: Dispatch[Msg]) -> None:
        if self._subscriptions is None:
            return

        rem_unscribes = self._unsubscriptions
        self._unsubscriptions = {}
        for s in self._subscriptions(state):
            if us := rem_unscribes.pop(s, None):
                self._unsubscriptions[s] = us
            else:
                self._unsubscriptions[s] = s(dispatch)

        for us in rem_unscribes.values():
            us()


class SubscriptionWithKey(Generic[Msg]):
    def __init__(self, fun: Subscription[Msg], key: Hashable) -> None:
        self._key = key
        self._fun = fun

    def __call__(self, dispatch: Dispatch[Msg]) -> UnSubscription:
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
) -> Callable[[Subscription[Msg]], SubscriptionWithKey[Msg]]:
    def _constructor(f: Subscription[Msg]) -> SubscriptionWithKey[Msg]:
        _key = key if key is not None else tuple(f.__code__.co_lines())
        return SubscriptionWithKey[Msg](f, _key)

    return _constructor
