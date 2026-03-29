from textual.message import Message


class ModuleSelected(Message):
    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        super().__init__()


class InterfaceSelected(Message):
    def __init__(self, interface_name: str) -> None:
        self.interface_name = interface_name
        super().__init__()
