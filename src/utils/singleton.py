
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def has_instance(cls) -> bool:
        return cls in cls._instances

    def delete_instance(cls) -> bool:
        if cls in cls._instances:
            # Optional: Call cleanup method if it exists
            instance = cls._instances[cls]
            if hasattr(instance, 'cleanup') and callable(getattr(instance, 'cleanup')):
                try:
                    instance.cleanup()
                except Exception as e:
                    # Log the error but continue with deletion
                    print(f"Warning: Error during cleanup of {cls.__name__}: {e}")

            # Remove the instance from the registry
            del cls._instances[cls]
            return True
        return False
