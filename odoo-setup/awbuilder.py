#!/usr/bin/env python3
import argparse
import atexit
import logging
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime
from pathlib import Path

from fabric import Connection
from invoke import UnexpectedExit

####
# kvm -cpu host -nic user,model=virtio-net-pci,mac=52:54:00:3a:af:07,hostfwd=tcp:127.0.0.1:10242-:242 -m 16384 -drive if=virtio,file=/data/vms/virsh-vms/winfinal.qcow2,snapshot=on -serial none -monitor none -machine q35,smm=on -global driver=cfi.pflash01,property=secure,value=on -drive if=pflash,format=raw,unit=0,file=/usr/share/OVMF/OVMF_CODE_4M.ms.fd,readonly=on -drive if=pflash,format=raw,unit=1,file=OVMF_VARS_4M_aw_builder_win.1.0.ms.fd -snapshot
####

logger = logging.getLogger('awbuilder')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

BOOT_TIMEOUT = 60
UEFI_FIRMWARE_PATH = "/usr/share/OVMF/OVMF_CODE_4M.ms.fd"  # Default path when ovmf deb package is installed

ODOO_SIGN_SCRIPT = '/home/odoo/hsm_sign/hsm_sign.py'

class ActivityWatchWinBuilder:
    def __init__(self, args):
        self.args = args
        self.dest_dir = Path(args.destdir)
        self.dest_dir.mkdir(exist_ok=True)
        self.result_path = None
        self.image = args.vm_image
        if not Path(self.image).exists():
            raise FileNotFoundError(f'VM file "{self.image}" does not exists')
        self.uefi_variable_template = args.vm_uefi_var
        if not Path(self.uefi_variable_template).exists():
            raise FileNotFoundError(f'UEFI variable template file "{self.uefi_variable_template}" does not exists')
        self.login = args.vm_login
        self.ssh_key = args.vm_ssh_key
        self.activitywatch_path = args.activitywatch_path or (Path(__file__) / '../../').resolve()
        self.check_activitywatch_path()
        self.graphical = args.graphical

    def check_activitywatch_path(self):
        mandatory_dirs = [
            'awatcher',
            'aw-qt',
            'aw-server-rust',
            'odoo-setup',
        ]
        for d in mandatory_dirs:
            path_to_check = self.activitywatch_path / d
            if not path_to_check.is_dir():
                logger.error('It seems that the %s directory is not the Odoo patched ActivityWatch  directory', self.activitywatch_path)
                sys.exit(1)

    def timeout(self, signum, frame):
        logger.warning("VM timeout kill (pid: %s)", self.kvm_proc.pid)
        self.kvm_proc.terminate()

    def start(self):
        kvm_cmd = [
            "kvm",
            "-cpu", "host",
            "-nic", "user,model=virtio-net-pci,mac=52:54:00:3a:af:07,hostfwd=tcp:127.0.0.1:11242-:22",
            "-m", "16384",
            "-drive", f"if=virtio,file={self.image},snapshot=on",
            "-serial", "none",
            "-monitor", "none",
            "-snapshot",
            # UEFI compatibility part (Need ovmf deb package installed)
            "-machine", "q35,smm=on",
            "-global", "driver=cfi.pflash01,property=secure,value=on",
            "-drive", f"if=pflash,format=raw,unit=0,file={UEFI_FIRMWARE_PATH},readonly=on",
            "-drive", f"if=pflash,format=raw,unit=1,file={self.uefi_variable_template}",
        ]

        if not self.graphical:
            kvm_cmd.append("-nographic")
        logger.info("Starting kvm: %s", " ".join(kvm_cmd))
        self.kvm_proc = subprocess.Popen(kvm_cmd)
        logger.info('kvm pid: %s', self.kvm_proc.pid)
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        logger.info('Waiting for Virtual Machine to boot up (verifying ssh port is open)')
        start_time = time.time()
        result = 1
        while bool(result):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 11242))
            sock.close()
            time.sleep(1)
            if time.time() - start_time > BOOT_TIMEOUT:
                logger.error('VM took too much time to boot ... exiting')
                self.kvm_proc.terminate()
                sys.exit(1)
        logger.info("VM is up !")
        time.sleep(120)

    def stop_kvm(self, exit_code=0):
        if self.kvm_proc is not None and self.kvm_proc.poll() is None:
            logger.info("Stopping VM (pid: %s)...", self.kvm_proc.pid)
            self.kvm_proc.terminate()
            try:
                self.kvm_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Timeout - Killing VM ...")
                self.kvm_proc.kill()
            logger.info("VM stopped.")
            sys.exit(exit_code)

    def cleanup(self, *args, exit_code=0, **kwargs):
        self.stop_kvm(exit_code=exit_code)

    def start_steps(self):
        logger.info("Starting build steps")
        try:
            signal.alarm(3600)
            signal.signal(signal.SIGALRM, self.timeout)
            self.run()
        finally:
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            self.kvm_proc.terminate()
            time.sleep(2)

    def _upload_activitywatch(self, connection):
        """Upload activitywatch source directory to the VM via SCP."""
        logger.info('Uploading activitywatch sources to VM...')
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
            tmp_path = tmp.name

        with tarfile.open(tmp_path, 'w:gz') as tar:
            tar.add(self.activitywatch_path, arcname='activitywatch')

        remote_path = '/Users/moc/activitywatch.tar.gz'
        connection.put(tmp_path, remote=remote_path)
        Path(tmp_path).unlink()

        connection.run('cd ~ && tar -xzf activitywatch.tar.gz && rm activitywatch.tar.gz')
        logger.info('Activitywatch sources uploaded.')

    def run(self):
        connect_kwargs = {
            "banner_timeout": 60,
            "timeout": 60,
            "auth_timeout": 60,
        }
        connect_kwargs["key_filename"] = self.ssh_key if self.ssh_key else None
        connection = Connection(host='127.0.0.1', user=self.login, port=11242, connect_kwargs=connect_kwargs)
        connection.open()

        self._upload_activitywatch(connection)

        build_steps = [
            'cd ~ ; python3 -m venv ~/buildenv',
            # Env variable to avoid a bug in poetry install on windows via ssh
            'source ~/buildenv/Scripts/activate && cd ~/activitywatch && PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring CARGO_BUILD_TARGET=x86_64-pc-windows-msvc SKIP_SERVER_PYTHON=true ODOO_WINDOWS_BUILD=true make build',
            'source ~/buildenv/Scripts/activate ; cd ~/activitywatch ; PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring CARGO_BUILD_TARGET=x86_64-pc-windows-msvc SKIP_SERVER_PYTHON=true ODOO_WINDOWS_BUILD=true make package',
            'ls ~/activitywatch/dist/*.exe',
        ]

        for step in build_steps:
            logger.info('Running: "%s"', step)
            try:
                connection.run(step)
            except UnexpectedExit as e:
                logger.error('Step "%s" failed', step)
                logger.error('Error "%s"', e.result)
                connection.close()
                time.sleep(5)  # let the time for the connection to properly close
                self.cleanup(exit_code=1)

        logger.info('Build Finished 🥳')
        sftp = connection.sftp()
        dist_dir = 'activitywatch/dist'

        # resulting file is something like 'activitywatch-v0.13.2.dev-ade74fd-windows-x86_64-setup.exe'
        for f in sftp.listdir(dist_dir):
            if f.endswith('setup.exe'):
                tstamp = datetime.now().strftime('%Y.%m.%0d')
                parts = f.split('-')
                parts.insert(-1, f'odoo_patched_{tstamp}')
                setup_filename = '-'.join(parts)
                self.result_path = self.dest_dir / setup_filename
                connection.get(f'{dist_dir}/{f}', local=str(self.result_path))
                break
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script to build Odoo patched Activity Watch.")
    parser.add_argument("--vm-ssh-key", "-k", help="Ssh identify file to use for connection to the VM (Defaults to current user identity file)")
    parser.add_argument("--vm-image", "-i", required=True, help="Path to Qemu/KVM image used to build Activity Watch")
    parser.add_argument("--vm-uefi-var", "-u", required=True, help="Path to UEFI variable template")
    parser.add_argument("--vm-login", "-l", required=True, help="Login for the VM")
    parser.add_argument("--destdir", "-d", default='/tmp', help="Directory where to put the built image (Defaults to '/tmp')")
    parser.add_argument("--symlink-latest", "-s", action="store_true", default=False, help="Create a latest symlink in output dir")
    parser.add_argument("--pesign", "-p", action="store_true", help="Sign PE file")
    parser.add_argument("--vm-debug", "-v", action="store_true", default=False, help="Just start the VM (snapshot mode) and wait")
    parser.add_argument("--activitywatch-path", "-a", type=Path, help="Path to activitywatch directory. (Defaults to parent directory of this script).")
    parser.add_argument("--graphical", "-g", action="store_true", default=False, help="Start VM in graphical mode.")

    args = parser.parse_args()
    builder = ActivityWatchWinBuilder(args)
    builder.start()

    if args.vm_debug:
        logger.info(f'You can connect it with "ssh {args.vm_login}@127.0.0.1 -p 11242"')
        if builder.kvm_proc is not None and builder.kvm_proc.poll() is None:
            builder.kvm_proc.wait()
    else:
        builder.start_steps()
        if builder.result_path:
            logger.info('Successfully built in: %s', builder.result_path)
        if args.pesign:
            logger.info('Signing Executable file')
            subprocess.run([ODOO_SIGN_SCRIPT, builder.result_path.absolute()])
        if args.symlink_latest:
            logger.info('Creating Symlink to latest')
            symlink = builder.dest_dir / 'activitywatch-odoo_patched-latest-setup.exe'
            if symlink.is_symlink():
                symlink.unlink()
            symlink.symlink_to(builder.result_path.absolute())
