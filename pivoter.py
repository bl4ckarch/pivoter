#!/bin/env python3
# File name          : pivoter.py
# Author             : bl4ckarch

import ipaddress
import subprocess
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.progress import Progress
from rich.text import Text
import logging

# Set up rich console and simplified logger
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("Pivoter")


def display_banner():
    banner_text = Text("""
██████╗ ██╗██╗   ██╗ ██████╗ ████████╗███████╗██████╗
██╔══██╗██║██║   ██║██╔═══██╗╚══██╔══╝██╔════╝██╔══██╗
██████╔╝██║██║   ██║██║   ██║   ██║   █████╗  ██████╔╝
██╔═══╝ ██║╚██╗ ██╔╝██║   ██║   ██║   ██╔══╝  ██╔══██╗
██║     ██║ ╚████╔╝ ╚██████╔╝   ██║   ███████╗██║  ██║
╚═╝     ╚═╝  ╚═══╝   ╚═════╝    ╚═╝   ╚══════╝╚═╝  ╚═╝
    by @bl4ckarch

""", justify="center", style="bold cyan")
    console.print(banner_text)
    console.print("[bold magenta]Welcome to Pivoter - A Utility Tool![/bold magenta]\n")


def valid_cidr(cidr: str) -> bool:
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        logger.error(f"Invalid CIDR format: {cidr}. Use format like 10.10.110.0/24")
        return False


def ping_sweep(cidr: str):
    if not valid_cidr(cidr):
        return []

    network = ipaddress.ip_network(cidr, strict=False)
    live_hosts = []
    ping_processes = {}

    console.log(f"Starting ping sweep on [bold cyan]{cidr}[/bold cyan]...")

    # Launch all ping processes in parallel
    for ip in network.hosts():
        ip_str = str(ip)
        process = subprocess.Popen(
            ["ping", "-c", "1", "-W", "1", ip_str],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        ping_processes[ip_str] = process

    # Collect results as processes finish
    for ip_str, process in ping_processes.items():
        try:
            stdout, _ = process.communicate()
            if b"bytes from" in stdout:
                live_hosts.append(ip_str)
                console.log(f"[bold green]Host {ip_str} is alive.[/bold green]")
        except Exception as e:
            logger.error(f"Error processing {ip_str}: {e}")

    if live_hosts:
        console.log("[bold green]Ping sweep completed! Live hosts found.[/bold green]")
    else:
        console.log("[bold yellow]Ping sweep completed. No live hosts found.[/bold yellow]")

    return live_hosts


def display_results(live_hosts):
    if live_hosts:
        table = Table(title="Ping Sweep Results", show_header=True, header_style="bold magenta")
        table.add_column("IP Address", justify="center")
        for host in live_hosts:
            table.add_row(host)
        console.print(table)
    else:
        logger.info("No live hosts found.")


def main_menu(live_hosts):
    while True:
        console.print("\n[bold magenta]What would you like to do next?[/bold magenta]")
        console.print("1) Perform an Nmap scan on live hosts")
        console.print("2) Run netexec (nxc) scans on live hosts")
        console.print("3) Exit the script")

        choice = Prompt.ask(
            "\nEnter your choice",
            choices=["1", "2", "3"],
            default="3",
            show_choices=False,
        )

        if choice == "1":
            perform_async_nmap_scans(live_hosts)
        elif choice == "2":
            choose_and_run_netexec(live_hosts)
        elif choice == "3":
            console.log("[bold green]Exiting the script. Goodbye![/bold green]")
            break


def perform_async_nmap_scans(live_hosts):
    console.log(f"Starting Nmap scans asynchronously on [bold cyan]{len(live_hosts)}[/bold cyan] live hosts...")
    nmap_results = {}

    def run_nmap(ip):
        output_file = f"nmap_scan_{ip.replace('.', '_')}.txt"
        try:
            console.log(f"[bold blue]Running Nmap scan for {ip}...[/bold blue]")
            subprocess.run(
                ["nmap", "-sCV", "-Pn", "-T5", "-oN", output_file, ip],
                check=True
            )
            return ip, output_file
        except subprocess.CalledProcessError as e:
            logger.error(f"Nmap scan failed for {ip}: {e}")
            return ip, None

    with ThreadPoolExecutor(max_workers=len(live_hosts)) as executor:
        futures = {executor.submit(run_nmap, ip): ip for ip in live_hosts}

        for future in as_completed(futures):
            ip, output_file = future.result()
            nmap_results[ip] = output_file

    console.log("[bold green]All Nmap scans completed.[/bold green]")

    # Display results
    table = Table(title="Nmap Scan Results", show_header=True, header_style="bold magenta")
    table.add_column("IP Address", justify="center")
    table.add_column("Result File", justify="center")

    for ip, output_file in nmap_results.items():
        if output_file:
            table.add_row(ip, output_file)
        else:
            table.add_row(ip, "[red]Failed[/red]")

    console.print(table)


def choose_and_run_netexec(live_hosts):
    protocols = ["mssql", "ldap", "ftp", "wmi", "nfs", "ssh", "smb", "winrm", "vnc", "rdp"]
    console.print("\n[bold magenta]Available Protocols for netexec (nxc) Scans:[/bold magenta]")
    for idx, protocol in enumerate(protocols, start=1):
        console.print(f"{idx}) {protocol}")

    selected_protocol = Prompt.ask(
        "\nSelect a protocol to scan",
        choices=[str(i) for i in range(1, len(protocols) + 1)],
    )

    protocol = protocols[int(selected_protocol) - 1]
    console.log(f"[bold blue]Selected protocol: {protocol}[/bold blue]")

    results = []
    console.log(f"Starting netexec scans with protocol [bold magenta]{protocol}[/bold magenta] on live hosts...")

    with Progress() as progress:
        task = progress.add_task("[cyan]Scanning...", total=len(live_hosts))

        for ip in live_hosts:
            try:
                process = subprocess.run(
                    ["nxc", protocol, ip],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                output = process.stdout.strip()
                if output:
                    results.extend(output.splitlines())
            except subprocess.CalledProcessError as e:
                logger.error(f"Error running nxc for {ip} and protocol {protocol}: {e}")
            finally:
                progress.update(task, advance=1)

    # Display final results
    table = Table(title=f"Netexec Scan Results for {protocol}", show_header=True, header_style="bold magenta")
    table.add_column("Protocol", justify="center")
    table.add_column("IP Address", justify="center")
    table.add_column("Port", justify="center")
    table.add_column("Details", justify="left")

    for line in results:
        parts = line.split(maxsplit=3)
        if len(parts) == 4:
            table.add_row(parts[0], parts[1], parts[2], parts[3])

    console.print(table)


if __name__ == "__main__":
    import sys
    from concurrent.futures import ThreadPoolExecutor, as_completed

    display_banner()

    if len(sys.argv) < 2:
        console.log("[bold red]Usage: python pivoter.py <subnet1> [<subnet2> ... <subnetN>][/bold red]")
        sys.exit(1)

    for subnet in sys.argv[1:]:
        logger.info(f"Processing subnet: {subnet}")
        live_hosts = ping_sweep(subnet)
        display_results(live_hosts)
        main_menu(live_hosts)

    console.log("[bold green]All subnets processed.[/bold green]")