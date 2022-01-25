# type: ignore
class Singleton(type):
    """单例模式元类

    @refs: https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python

    # Usage
    ```
    class MyClass(BaseClass, metaclass=Singleton):
        pass
    ```
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
