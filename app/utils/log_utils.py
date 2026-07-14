import traceback


def log(msg: str) -> None:
    print(msg, flush=True)


def log_error(context: str, exc: BaseException | None = None) -> None:
    log(f"[ERROR] {context}")
    if exc is not None:
        log(f"  {type(exc).__name__}: {exc}")
    traceback.print_exc()
