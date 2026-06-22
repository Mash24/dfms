from fastapi import HTTPException


class CommandError(Exception):
    def __init__(self, error_code: str, message: str, field: str | None = None, status_code: int = 422):
        self.error_code = error_code
        self.message = message
        self.field = field
        self.status_code = status_code
        super().__init__(message)


def raise_command_error(exc: CommandError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "field": exc.field,
            "details": {},
        },
    )
