"""Global package data that are valid for all of its instances.
Used to access the RsInstrument class variables."""

from datetime import datetime


class GlobalData:
    """Global package data that are valid for all of its instances."""

    bounded_class = None

    @classmethod
    def is_bounded(cls) -> bool:
        """Returns true, if the class is bounded to a global source."""
        return cls.bounded_class is not None

    @classmethod
    def set_logging_target(cls, value: datetime or None) -> None:
        """Sets the class variable to the entered value."""
        setattr(cls.bounded_class, '_global_logging_target_stream', value)

    @classmethod
    def get_logging_target(cls):
        """Returns the class variable value."""
        if not cls.is_bounded():
            return None
        return getattr(cls.bounded_class, '_global_logging_target_stream')

    @classmethod
    def set_logging_relative_timestamp(cls, value: datetime or None) -> None:
        """Sets the class variable to the entered value."""
        setattr(cls.bounded_class, '_global_logging_relative_timestamp', value)

    @classmethod
    def get_logging_relative_timestamp(cls) -> datetime or None:
        """Returns the class variable value."""
        if not cls.is_bounded():
            return None
        return getattr(cls.bounded_class, '_global_logging_relative_timestamp')
