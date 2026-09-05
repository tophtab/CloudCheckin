import sys

from qinglong_task import main


TARGET = "nodeseek"


if __name__ == "__main__":
    try:
        sys.exit(main(TARGET))
    except KeyboardInterrupt:
        sys.exit(0)
