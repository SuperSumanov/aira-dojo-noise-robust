from dataclasses import dataclass

from dojo.config_dataclasses.interpreter.python import PythonInterpreterConfig


@dataclass
class ChrootPythonInterpreterConfig(PythonInterpreterConfig):
    """Configuration for the opt-in Linux chroot interpreter."""

    startup_timeout: float = 60.0
    runtime_base_dir: str = "/tmp/dojo-python-sandboxes"
    allowed_working_root: str | None = None
    uid_min: int = 200000
    uid_max: int = 299999
    private_tmp: bool = True

    def validate(self) -> None:
        super().validate()
        if self.uid_min <= 0 or self.uid_max < self.uid_min:
            raise ValueError("The sandbox UID range must contain positive IDs")
        if not self.runtime_base_dir:
            raise ValueError("runtime_base_dir must not be empty")
