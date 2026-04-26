"""SSH transport layer for executing remote commands and transferring files.

Provides a thin wrapper around paramiko for establishing SSH connections,
running commands, and pushing config files to remote hosts.
"""

import io
import logging
import stat
from pathlib import Path
from typing import Optional

import paramiko

logger = logging.getLogger(__name__)


class SSHError(Exception):
    """Raised when an SSH operation fails."""
    pass


class CommandResult:
    """Result of a remote command execution."""

    def __init__(self, stdout: str, stderr: str, exit_code: int):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def __repr__(self) -> str:
        return (
            f"CommandResult(exit_code={self.exit_code}, "
            f"stdout={self.stdout!r:.60}, stderr={self.stderr!r:.60})"
        )


class SSHClient:
    """Manages an SSH connection to a single remote host."""

    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        key_path: Optional[str] = None,
        password: Optional[str] = None,
        connect_timeout: int = 10,
    ):
        self.host = host
        self.user = user
        self.port = port
        self.key_path = key_path
        self.password = password
        self.connect_timeout = connect_timeout

        self._client: Optional[paramiko.SSHClient] = None

    def connect(self) -> None:
        """Open the SSH connection. Raises SSHError on failure."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        kwargs: dict = {
            "hostname": self.host,
            "port": self.port,
            "username": self.user,
            "timeout": self.connect_timeout,
        }

        if self.key_path:
            kwargs["key_filename"] = str(Path(self.key_path).expanduser())
        if self.password:
            kwargs["password"] = self.password

        try:
            client.connect(**kwargs)
            self._client = client
            logger.debug("Connected to %s@%s:%s", self.user, self.host, self.port)
        except paramiko.AuthenticationException as exc:
            raise SSHError(f"Authentication failed for {self.user}@{self.host}") from exc
        except Exception as exc:
            raise SSHError(f"Could not connect to {self.host}:{self.port}: {exc}") from exc

    def disconnect(self) -> None:
        """Close the SSH connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.debug("Disconnected from %s", self.host)

    def run(self, command: str, timeout: int = 30) -> CommandResult:
        """Execute a command on the remote host and return its result."""
        if not self._client:
            raise SSHError("Not connected. Call connect() first.")

        logger.debug("[%s] Running: %s", self.host, command)
        try:
            _, stdout_fh, stderr_fh = self._client.exec_command(command, timeout=timeout)
            exit_code = stdout_fh.channel.recv_exit_status()
            result = CommandResult(
                stdout=stdout_fh.read().decode("utf-8", errors="replace").strip(),
                stderr=stderr_fh.read().decode("utf-8", errors="replace").strip(),
                exit_code=exit_code,
            )
        except Exception as exc:
            raise SSHError(f"Command execution failed on {self.host}: {exc}") from exc

        if not result.ok:
            logger.warning("[%s] Command exited %d: %s", self.host, exit_code, command)
        return result

    def put(self, content: str, remote_path: str, mode: int = 0o644) -> None:
        """Write a string to a file on the remote host."""
        if not self._client:
            raise SSHError("Not connected. Call connect() first.")

        sftp = self._client.open_sftp()
        try:
            with sftp.open(remote_path, "w") as remote_file:
                remote_file.write(content)
            sftp.chmod(remote_path, mode)
            logger.debug("[%s] Wrote %d bytes to %s", self.host, len(content), remote_path)
        except Exception as exc:
            raise SSHError(f"Failed to write {remote_path} on {self.host}: {exc}") from exc
        finally:
            sftp.close()

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()
