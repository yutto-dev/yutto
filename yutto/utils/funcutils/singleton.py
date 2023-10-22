from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


class Singleton(type):
    """单例模式元类

    ### Refs

    - https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python

    ### Examples

    ``` python
    class MyClass(BaseClass, metaclass=Singleton):
        pass

    obj1 = MyClass()
    obj2 = MyClass()
    assert obj1 is obj2
    ```
    """

    _instances: dict[Any, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
