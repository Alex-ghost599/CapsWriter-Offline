import sys

import pytest

from core.client.clipboard.clipboard import (
    save_and_restore_clipboard,
    snapshot_macos_pasteboard,
    write_macos_pasteboard_text,
)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS pasteboard test")
def test_macos_pasteboard_snapshot_restores_multiple_types():
    from AppKit import NSPasteboard, NSPasteboardItem
    from Foundation import NSData

    pasteboard = NSPasteboard.pasteboardWithUniqueName()
    try:
        original = NSPasteboardItem.alloc().init()
        text_payload = "原始内容".encode("utf-8")
        binary_payload = bytes(range(16))
        original.setData_forType_(
            NSData.dataWithBytes_length_(text_payload, len(text_payload)),
            "public.utf8-plain-text",
        )
        original.setData_forType_(
            NSData.dataWithBytes_length_(binary_payload, len(binary_payload)),
            "com.capswriter.test-binary",
        )
        pasteboard.clearContents()
        pasteboard.writeObjects_([original])

        snapshot = snapshot_macos_pasteboard(pasteboard)
        expected_change_count = write_macos_pasteboard_text("临时识别结果", pasteboard)

        assert snapshot.restore(pasteboard, expected_change_count)
        restored = pasteboard.pasteboardItems()[0]
        assert bytes(restored.dataForType_("public.utf8-plain-text")) == text_payload
        assert bytes(restored.dataForType_("com.capswriter.test-binary")) == binary_payload
    finally:
        pasteboard.releaseGlobally()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS pasteboard test")
def test_macos_clipboard_context_does_not_overwrite_later_update():
    from AppKit import NSPasteboard, NSPasteboardTypeString

    pasteboard = NSPasteboard.pasteboardWithUniqueName()
    try:
        write_macos_pasteboard_text("original", pasteboard)
        with save_and_restore_clipboard(pasteboard) as mark_clipboard_updated:
            write_macos_pasteboard_text("temporary", pasteboard)
            mark_clipboard_updated()

        assert pasteboard.stringForType_(NSPasteboardTypeString) == "original"

        with save_and_restore_clipboard(pasteboard) as mark_clipboard_updated:
            write_macos_pasteboard_text("temporary", pasteboard)
            mark_clipboard_updated()
            write_macos_pasteboard_text("new user value", pasteboard)

        assert pasteboard.stringForType_(NSPasteboardTypeString) == "new user value"
    finally:
        pasteboard.releaseGlobally()
