"""macOS privacy permission checks used by the interactive client."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass


class MacOSPermissionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MacOSPermissionStatus:
    microphone: bool
    accessibility: bool
    input_monitoring: bool
    post_events: bool

    @property
    def ready(self) -> bool:
        return all((self.microphone, self.accessibility, self.input_monitoring, self.post_events))


def _require_macos() -> None:
    if sys.platform != 'darwin':
        raise RuntimeError('macOS permission APIs are only available on Darwin')


def microphone_authorized() -> bool:
    _require_macos()
    from AVFoundation import (
        AVAuthorizationStatusAuthorized,
        AVCaptureDevice,
        AVMediaTypeAudio,
    )

    return AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio) == AVAuthorizationStatusAuthorized


def request_microphone_access(timeout: float = 60.0) -> bool:
    _require_macos()
    from AVFoundation import (
        AVAuthorizationStatusAuthorized,
        AVAuthorizationStatusNotDetermined,
        AVCaptureDevice,
        AVMediaTypeAudio,
    )
    from Foundation import NSDate, NSRunLoop

    status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
    if status == AVAuthorizationStatusAuthorized:
        return True
    if status != AVAuthorizationStatusNotDetermined:
        return False

    result = {'granted': False}
    completed = threading.Event()

    def completion_handler(granted):
        result['granted'] = bool(granted)
        completed.set()

    AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVMediaTypeAudio, completion_handler)
    deadline = time.monotonic() + timeout
    run_loop = NSRunLoop.currentRunLoop()
    while not completed.is_set() and time.monotonic() < deadline:
        run_loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
    return result['granted']


def accessibility_authorized(prompt: bool = False) -> bool:
    _require_macos()
    from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

    if prompt:
        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}))
    return bool(AXIsProcessTrusted())


def input_monitoring_authorized(request: bool = False) -> bool:
    _require_macos()
    from Quartz import CGPreflightListenEventAccess, CGRequestListenEventAccess

    return bool(CGRequestListenEventAccess() if request else CGPreflightListenEventAccess())


def post_events_authorized(request: bool = False) -> bool:
    _require_macos()
    from Quartz import CGPreflightPostEventAccess, CGRequestPostEventAccess

    return bool(CGRequestPostEventAccess() if request else CGPreflightPostEventAccess())


def permission_status() -> MacOSPermissionStatus:
    _require_macos()
    return MacOSPermissionStatus(
        microphone=microphone_authorized(),
        accessibility=accessibility_authorized(),
        input_monitoring=input_monitoring_authorized(),
        post_events=post_events_authorized(),
    )


def request_required_permissions() -> MacOSPermissionStatus:
    _require_macos()
    request_microphone_access()
    accessibility_authorized(prompt=True)
    input_monitoring_authorized(request=True)
    post_events_authorized(request=True)
    return permission_status()


def show_macos_error(message: str, title: str = 'CapsWriter 无法启动') -> None:
    """Display a visible error when the windowed app cannot use the terminal."""
    _require_macos()
    from AppKit import NSAlert, NSAlertStyleCritical, NSApplication

    NSApplication.sharedApplication()
    alert = NSAlert.alloc().init()
    alert.setAlertStyle_(NSAlertStyleCritical)
    alert.setMessageText_(title)
    alert.setInformativeText_(message)
    alert.addButtonWithTitle_('退出')
    alert.runModal()


def show_permission_error(message: str) -> None:
    show_macos_error(message, title='CapsWriter 需要 macOS 权限')
