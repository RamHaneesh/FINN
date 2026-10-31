from finn.config import get_settings
from finn.storage import Store


def main():
    store = Store(get_settings().finn_data_dir)
    print(f"Database ready: {store.database}")


if __name__ == "__main__":
    main()
