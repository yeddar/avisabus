import socket

import pytest
from pytest_socket import SocketBlockedError


@pytest.mark.spec("project_scaffold.AC-05")
def test_opening_a_network_socket_fails_the_test() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


@pytest.mark.spec("project_scaffold.AC-05")
def test_ipv6_network_socket_is_blocked_too() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
