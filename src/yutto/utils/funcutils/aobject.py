from __future__ import annotations

from typing import Any


class aobject:
    """Inheriting this class allows you to define an async __ainit__.

    ### Refs

    - https://stackoverflow.com/questions/33128325/how-to-set-class-attribute-with-await-in-init

    ### Examples

    ``` python
    class MyClass(aobject):
        # pyright: reportIncompatibleMethodOverride=false
        async def __ainit__(self):
            ...

    await MyClass()
    ```
    """

    async def __new__(cls, *args: Any, **kwargs: Any):
        instance = super().__new__(cls)
        await instance.__ainit__(*args, **kwargs)
        return instance

    async def __ainit__(self, *args: Any, **kwargs: Any):
        pass
