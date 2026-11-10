"""Singleton class that holds values reachable from anywhere in the Internal package.
The first instantiation creates the object, the consequent ones return the same object."""


class Properties(object):
    """Class holding global properties."""
    scpi_quotes = "'"

    @classmethod
    def reset(cls):
        """Sets all the variables to default."""
        cls.scpi_quotes = "'"
