from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """
    Abstract base class for all data extractors.
    """
    @abstractmethod
    def extract(self, source_info):
        """Extracts data from a source.

        Args:
            source_info (dict): A dictionary containing source details from the spec config.

        Returns:
            The extracted data.
        """
        pass
