from notifiers.base import Notifier, NotificationPayload


class SignalNotifierStub(Notifier):
    def send(self, payload: NotificationPayload) -> None:
        # Placeholder for future signal-cli integration.
        _ = payload
