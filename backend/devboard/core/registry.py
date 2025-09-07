"""Generic registry implementation for type-safe collections."""

from typing import Generic, TypeVar

T = TypeVar('T')


class Registry(Generic[T]):
    """Generic registry for managing typed collections.
    
    Provides a type-safe way to store and retrieve items by string keys.
    The registry is immutable after construction.
    """
    _items: dict[str, T]

    def __init__(self, items: list[T], key_attr: str):
        """Initialize the registry.
        
        Args:
            items: List of items to register
            key_attr: The attribute name to use as keys (required)
        """
        self._items = {getattr(item, key_attr): item for item in items}

    def get(self, key: str) -> T | None:
        """Get an item by key.
        
        Args:
            key: The key to look up
            
        Returns:
            The item if found, None otherwise
        """
        return self._items.get(key)

    def list_keys(self) -> list[str]:
        """Get all keys in the registry.
        
        Returns:
            Sorted list of all keys
        """
        return sorted(self._items.keys())

    def list_values(self) -> list[T]:
        """Get all values in the registry.
        
        Returns:
            List of all values
        """
        return list(self._items.values())

    def items(self) -> list[tuple[str, T]]:
        """Get all key-value pairs.
        
        Returns:
            List of (key, value) tuples
        """
        return list(self._items.items())


    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the registry."""
        return key in self._items

    def __len__(self) -> int:
        """Get the number of items in the registry."""
        return len(self._items)

    def __repr__(self) -> str:
        """String representation of the registry."""
        return f"Registry({len(self._items)} items: {list(self._items.keys())})"
