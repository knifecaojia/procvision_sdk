class RecoverableError(Exception):
    pass


class FatalError(Exception):
    pass


class GPUOutOfMemoryError(Exception):
    pass


class ProgramError(Exception):
    pass