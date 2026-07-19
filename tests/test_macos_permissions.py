import sys

import pytest

from core.client.macos_permissions import MacOSPermissionStatus


def test_permission_status_requires_every_capability():
    assert MacOSPermissionStatus(True, True, True, True).ready
    assert not MacOSPermissionStatus(True, True, False, True).ready


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS permission APIs')
def test_permission_checks_return_booleans():
    from core.client.macos_permissions import permission_status

    status = permission_status()
    assert isinstance(status.microphone, bool)
    assert isinstance(status.accessibility, bool)
    assert isinstance(status.input_monitoring, bool)
    assert isinstance(status.post_events, bool)
