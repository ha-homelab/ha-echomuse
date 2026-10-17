#!/usr/bin/env python3
"""Create a private overlay; refuse any upstream revision not reviewed here."""
import argparse
import hashlib
from pathlib import Path
import shutil

PINS = {
    'em_controller.py': '9f4cc4da555d520d14148fcec9dd7c6322a2ee871573a85eaad7c22eef97e73b',
    'em_api.py': 'f643b330240f3a681e2b3a465092ee70b935f5e314b2da6cf234b7139ae4d323',  # gitleaks:allow -- public source SHA-256, not a credential
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Upstream hook does not match exactly once')
    return text.replace(old, new, 1)


def patch_oww_inventory(text):
    """Do not interpret an interrupted device-shell probe as missing assets."""
    old = '''        f'echo "FREE $(busybox df -m /data | busybox tail -1)"'
    ), timeout=120.0)

    free_mb = None
'''
    new = '''        f'echo "FREE $(busybox df -m /data | busybox tail -1)"; '
        "printf '\\n%s%s\\n' '__EM_OWW_' 'INVENTORY_OK__'"
    ), timeout=120.0)

    # _shell_run can return empty or partial output on a broken connection.
    # Assemble the marker on the device so command echo cannot complete a probe.
    probe_lines = out.splitlines()
    if not probe_lines or probe_lines[-1].strip() != "__EM_OWW_INVENTORY_OK__":
        raise RuntimeError("Wake-word inventory probe did not complete; "
                           "installed assets are unknown")
    out = "\\n".join(probe_lines[:-1])
    free_mb = None
'''
    return replace_once(text, old, new)


def patch(name, raw):
    if hashlib.sha256(raw).hexdigest() != PINS[name]:
        raise ValueError('Unsupported upstream source hash: ' + name)
    text = raw.decode()
    if name == 'em_controller.py':
        text = replace_once(text, 'import em_wake_samples', 'import em_training\nimport em_wake_samples')
        text = replace_once(text,
            'async def handle_button_event(device: Device, event: dict):\n',
            'async def handle_button_event(device: Device, event: dict):\n'
            '    if await em_training.button(device, event):\n        return\n')
        text = replace_once(text, '                pcm = raw[MIC_HEADER_LEN:]\n',
            '                pcm = raw[MIC_HEADER_LEN:]\n'
            '                if em_training.feed(device, pcm, int.from_bytes(raw[1:3], "big")):\n'
            '                    continue\n')
        text = replace_once(text, '                    session, _seq, pcm = parsed\n',
            '                    session, _seq, pcm = parsed\n'
            '                    if em_training.active(device):\n                        continue\n')
        for kind in ('oww_wake', 'oww_shadow_cross'):
            anchor = f'                    elif msg_type == "{kind}":\n'
            close = ('                            if msg.get("session"):\n'
                     '                                await device.listen_close(msg["session"], "training")\n') if kind == 'oww_wake' else ''
            text = replace_once(text, anchor, anchor +
                '                        if em_training.active(device):\n' + close +
                '                            continue\n')
    else:
        text = patch_oww_inventory(text)
        text = replace_once(text, '    return app\n',
            '    import em_training\n    em_training.install(app, sys.modules[__name__])\n    return app\n')
        # em_api already imports sys in the reviewed revision.
        if '\nimport sys\n' not in text:
            text = 'import sys\n' + text
    compile(text, name, 'exec')
    return text


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = {n: patch(n, (args.source/n).read_bytes()) for n in PINS}
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    for n, s in result.items():
        (args.output/n).write_text(s)
    shutil.copyfile(Path(__file__).with_name('controller.py'), args.output/'em_training.py')
    print('Pinned controller overlay prepared; no service was changed.')

if __name__ == '__main__':
    main()
