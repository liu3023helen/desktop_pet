"""音效选择功能测试 + 回归测试"""
import re, os, sys

def test_reminder_dialog():
    with open('reminder_dialog.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('_scan_sound_files function defined', '_scan_sound_files' in content),
        ('os imported', 'import os' in content),
        ('sound_file_combo widget created', '_sound_file_combo' in content),
        ('QComboBox used', 'QComboBox()' in content),
        ('sound_file in _on_ok result dict', '"sound_file": sound_file' in content),
        ('sound_file read in _populate_form', 'r.get("sound_file"' in content),
        ('combo box has tooltip', '专属音效' in content),
    ]

    print('=== reminder_dialog.py ===')
    all_pass = True
    for name, result in checks:
        status = 'PASS' if result else 'FAIL'
        if not result: all_pass = False
        print('  [%s] %s' % (status, name))
    return all_pass


def test_main_py():
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('DEFAULT_SOUND_FILE constant defined', 'DEFAULT_SOUND_FILE' in content),
        ('play_reminder_sound accepts sound_file param', 'def play_reminder_sound(sound_file' in content),
        ('trigger_reminder reads sound_file from reminder dict', 'reminder.get("sound_file"' in content),
        ('play_reminder_sound called with custom file', 'play_reminder_sound(sound_file if sound_file else None)' in content),
        ('old hardcoded mp3 sound file removed', '小新-下班了，快去打卡.mp3' not in content),
    ]

    print('')
    print('=== main.py ===')
    all_pass = True
    for name, result in checks:
        status = 'PASS' if result else 'FAIL'
        if not result: all_pass = False
        print('  [%s] %s' % (status, name))
    return all_pass


def test_regression_existing_features():
    """回归测试：确保现有功能未被破坏"""
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('bubble_widget import still present', 'from bubble_widget import BubbleWidget' in content),
        ('trigger_reminder method exists', 'def trigger_reminder(self, reminder:' in content),
        ('bubble.show_bubble still called', 'self.bubble.show_bubble(' in content),
        ('weather bubble integration intact', '_show_weather_bubble' in content),
        ('QMetaObject.invokeMethod for weather thread safety', 'QMetaObject.invokeMethod' in content),
        ('pyqtSlot decorator on _show_weather_bubble', '@pyqtSlot(str)' in content),
        ('wander range ratio for pet movement', '_wander_x_range_ratio' in content),
    ]

    print('')
    print('=== Regression tests ===')
    all_pass = True
    for name, result in checks:
        status = 'PASS' if result else 'FAIL'
        if not result: all_pass = False
        print('  [%s] %s' % (status, name))
    return all_pass


def test_sound_files_exist():
    sounds_dir = os.path.join(os.path.dirname(__file__) or '.', 'assets', 'sounds')
    required = ['reminder.wav']

    print('')
    print('=== Sound files ===')
    all_pass = True
    for f in required:
        p = os.path.join(sounds_dir, f)
        exists = os.path.exists(p)
        size = os.path.getsize(p) if exists else 0
        status = 'PASS' if exists else 'FAIL'
        if not exists: all_pass = False
        print('  [%s] %s (%d bytes)' % (status, f, size))

    # List all wav files
    if os.path.isdir(sounds_dir):
        wavs = [f for f in os.listdir(sounds_dir) if f.lower().endswith('.wav')]
        print('  Total WAV files: %d' % len(wavs))

    return all_pass


if __name__ == '__main__':
    r1 = test_reminder_dialog()
    r2 = test_main_py()
    r3 = test_regression_existing_features()
    r4 = test_sound_files_exist()

    print('')
    print('=' * 40)
    if all([r1, r2, r3, r4]):
        print('ALL TESTS PASSED')
        sys.exit(0)
    else:
        print('SOME TESTS FAILED')
        sys.exit(1)
