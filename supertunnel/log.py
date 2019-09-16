import logging.handlers
import os


class PIDFilter(logging.Filter):
    def __init__(self, pid):
        self.pid = pid

    def filter(self, record):
        record.pid = self.pid
        return True


def setup_logging(verbose):
    """Set up the loggers"""
    root = logging.getLogger()

    # TODO: Consider using application directory via click
    logdir = os.path.join(os.path.expanduser("~"), ".st")
    os.makedirs(logdir, exist_ok=True)

    # Logger for the master process.
    h = logging.FileHandler(os.path.join(logdir, "st.log"), mode="w")
    f = logging.Formatter("[%(levelname)-8s %(asctime)s] %(message)s [%(name)s]")

    h.setFormatter(f)
    h.setLevel(logging.DEBUG)
    root.setLevel(logging.DEBUG)
    root.addHandler(h)

    lvl = {1: logging.INFO, 0: logging.WARNING}.get(verbose, logging.DEBUG)
    sh = logging.StreamHandler()
    sh.setLevel(lvl)
    sh.setFormatter(f)
    root.addHandler(sh)

    # Logger for each subprocess.
    # TODO: Consider not rotating these files, or setting the backupCount=1
    # or even better, use the PID in the log filename, and only keep the most
    # recent ones?
    ssh = logging.getLogger("ssh")
    ssh_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logdir, "ssh.log"), mode="w", backupCount=10, maxBytes=1e6
    )
    ssh_formatter = logging.Formatter("[%(levelname)-8s %(asctime)s] %(message)s [%(name)s]")
    ssh_handler.setFormatter(ssh_formatter)
    ssh_handler.setLevel(logging.DEBUG)
    ssh.addHandler(ssh_handler)
    ssh.setLevel(logging.DEBUG)
    ssh.propagate = False
