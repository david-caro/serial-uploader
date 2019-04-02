#!/usr/bin/env python3
import time
import getpass
from typing import Optional

import click
import serial


def _in_error(result: str) -> str:
    return "invalid" in result.lower()


def _send_line(
    handler: serial.Serial,
    line: str,
    wait: bool = True,
    allow_fail: bool = False,
    tries: int = 100,
    append_newline: bool = True,
    extra_wait: float = 0.0,
    retry_interval: float = 0.1
) -> str:
    if append_newline:
        line = line.strip() + "\r\n"

    bytes_line = line.encode()
    handler.write(bytes_line)
    if not wait:
        return

    result_bytes = b""
    tries_left = tries
    if extra_wait:
        print(f"    Waiting an extra {extra_wait} seconds...")
        time.sleep(extra_wait)

    while handler.inWaiting() or not result_bytes and tries_left:
        new_chunk = handler.read(handler.inWaiting())
        result_bytes += new_chunk
        time.sleep(retry_interval)
        tries_left -= 1

    if not tries_left:
        raise Exception(f"Unable to get response in {tries} tries.")

    result = result_bytes.decode()
    if _in_error(result):
        if not allow_fail:
            raise Exception(f"Error while sending line:\n{line}\n\nGot result:\n{result}")

    print("    OK")
    return result



def _wait_for(
    handler: serial.Serial,
    expected_string: str,
    tries: int = 10,
    debug: bool = False,
    current_result: str = "",
) -> str:
    result = current_result
    tries_left = tries
    print(f"@@@@    Waiting for {expected_string}...")
    while expected_string not in result:
        try:
            result = _send_line(handler=handler, line="", tries=10)
        except Exception as error:
            if not tries_left:
                raise Exception(
                    f"Timed out trying to wait for {expected_string}, tired "
                    f"{tries} times."
                ) from error

            if debug:
                print(f"Try #{tries - tries_left}")
                print(f"Got response:\n{result}")
            print("@@@@        Retrying...")
            tries_left -= 1

    return result


def _authenticate(
    handler: serial.Serial, user: str, password: str, current_result: str = "",
) -> str:
    print("#####  Authenticating...")
    _wait_for(
        handler=handler,
        expected_string="Username",
        current_result=current_result,
    )
    result = _send_line(handler=handler, line=user + "\n", append_newline=False)
    if "Password" not in result:
        result = _wait_for(
            handler=handler,
            expected_string="Password",
            current_result=result,
        )

    result = _send_line(handler=handler, line=password)
    if "Authentication failed" in result:
        raise Exception("Authentication failed")

    print(f"#### Authenticated :-)")
    return result


def _make_sure_we_are_in_the_first_screen(handler: serial.Serial) -> str:
    print("Exiting a bazillion times to make sure we are at the top level")
    _send_line(handler=handler, line="exit", wait=False, allow_fail=True)
    _send_line(handler=handler, line="exit", wait=False, allow_fail=True)
    _send_line(handler=handler, line="exit", wait=False, allow_fail=True)
    _send_line(handler=handler, line="exit", wait=False, allow_fail=True)
    _send_line(handler=handler, line="exit", wait=False, allow_fail=True)
    _send_line(handler=handler, line="exit", wait=False, allow_fail=True)

    print("Sending a few disable, just in case")
    _send_line(handler=handler, line="disable", wait=False, allow_fail=True)
    _send_line(handler=handler, line="disable", wait=False, allow_fail=True)
    _send_line(handler=handler, line="disable", wait=False, allow_fail=True)
    _send_line(handler=handler, line="disable", wait=False, allow_fail=True)

    print("Sending a bunch of newlines because why not")
    result = ""
    while not result:
        _send_line(handler=handler, line="", wait=False)
        _send_line(handler=handler, line="", wait=False)
        try:
            time.sleep(0.1)
            result = _send_line(handler=handler, line="", tries=10)
        except Exception:
            pass

    if "[yes/no]" in result:
        print("This seems to be an uncofigured device.")
        result = _send_line(handler=handler, line="no", tries=10)

    return result


def _open_device_config(handler: serial.Serial, user: str, password: str) -> None:
    result = _make_sure_we_are_in_the_first_screen(handler=handler)
    if "User" in result or "Password" in result or "Authentication" in result:
        print("It looks like authentication is required.")
        if not user:
            user = input("Username: ")
        if not password:
            password = getpass.getpass("Password: ")

        result = _authenticate(
            handler=handler, user=user, password=password, current_result=result,
        )
        if "Authentication failed" in result:
            raise Exception("Enable authentication failed")
    else:
        print("It looks like authentication is not needed.")

    result = _send_line(handler=handler, line="enable\n", allow_fail=True, append_newline=False)
    _send_line(handler=handler, line="configure terminal")
    _send_line(handler=handler, line="")


@click.command()
@click.option("-c", "--config-file")
@click.option("-s", "--serial-device-path", default="/dev/ttyUSB0")
@click.option("-u", "--user", default=None)
@click.option("-i", "--retry-interval", default=0.01)
@click.option(
    "--persist/--no-persist",
    help="Persist or not the running config after the upload (enabled by default).",
    default=True,
)
def upload_config(
    config_file: str,
    serial_device_path: str,
    user: Optional[str],
    retry_interval: float,
    persist: bool,
) -> None:
    start = time.time()
    click.echo(f"Uploading config {config_file} to device {serial_device_path}")
    serial_handler = serial.Serial(port=serial_device_path, baudrate=9600)
    serial_handler.bytesize = serial.EIGHTBITS
    serial_handler.parity = serial.PARITY_NONE
    serial_handler.stopbits = serial.STOPBITS_ONE
    serial_handler.timeout = 5

    password = None
    if user is not None:
        password = getpass.getpass("Password: ")

    _open_device_config(handler=serial_handler, user=user, password=password)
    next_tries = 100
    original_retry_interval = retry_interval
    next_retry_interval = retry_interval
    lines = open(config_file).readlines()
    for linenum, line in enumerate(lines):
        tries = next_tries
        retry_interval = next_retry_interval
        extra_wait = 0.0
        line = line.strip()

        if (line == "y" or line.startswith("define interface-range")):
            allow_fail = True
        else:
            allow_fail = False

        # The crypto command taske too long
        if "crypto key generate" in line:
            next_tries = 5000
            extra_wait = 2.0
            next_retry_interval = 0.1
        else:
            next_tries = 100
            next_retry_interval = original_retry_interval

        click.echo(
            f"Sending line number {linenum + 1} of {len(lines)}:\n"
            f"> {line} (will try {tries} times)"
        )
        result = _send_line(
            handler=serial_handler,
            line=line,
            allow_fail=allow_fail,
            tries=tries,
            extra_wait=extra_wait,
            retry_interval=retry_interval,
        )

        if "crypto key generate" in line:
            click.echo(
                "@@@@@@@@@@@@ NOTE: the next command might take a bit to "
                "execute, be patient!"
            )

    if persist:
        click.echo("Persisting configuration...")
        _send_line(handler=serial_handler, line="end", wait=True, allow_fail=True)
        result = _send_line(
            handler=serial_handler,
            line="copy running-config startup-config",
            allow_fail=False,
            tries=tries,
            extra_wait=extra_wait,
            retry_interval=retry_interval,
        )

    _make_sure_we_are_in_the_first_screen(handler=serial_handler)
    end = time.time()
    click.echo(f"DONE!! It took {end - start} seconds \o/")

