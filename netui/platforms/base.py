from abc import ABC, abstractmethod


class PlatformBase(ABC):
    @abstractmethod
    def get_interfaces(self) -> list[dict[str, object]]:
        ...

    @abstractmethod
    def get_routes(self) -> list[dict[str, object]]:
        ...

    @abstractmethod
    def get_wifi_info(self) -> dict[str, object]:
        ...

    @abstractmethod
    def get_open_ports(self) -> list[dict[str, object]]:
        ...

    @abstractmethod
    def get_dns_servers(self) -> list[str]:
        ...
