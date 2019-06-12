#!/usr/bin/env python3
# thoth-build-analysers
# Copyright(C) 2018, 2019 Marek Cermak
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>

"""Command line interface for Thoth build-analysers library."""

import sys
import click
import json

from functools import wraps

from pathlib import Path
from prettyprinter import pformat
from typing import Union

from thoth.build_analysers.preprocessing import build_log_to_dependency_table

from thoth.build_analysers.analysis import build_breaker_analyze
from thoth.build_analysers.analysis import build_breaker_report

from thoth.build_analysers.analysis import get_failed_branch
from thoth.build_analysers.analysis import get_succesfully_installed_packages


def _format_table(df, output: str = "plain", pretty: bool = False) -> str:
    """Format pandas DataFrame for console output."""
    if output is "plain":
        result: str = pformat(df)

        return result

    elif output in ("json", "dict"):
        result: str = df.to_dict(orient="records")
    elif output is "records":
        result: list = df.to_records().tolist()
    else:
        result = eval(f"df.to_{output}()")

    if pretty:
        result: str = pformat(result)

        return result

    return json.dumps(result)


class AliasedGroup(click.Group):
    """Command group to handler comand aliases."""

    aliases = {"analyse": "analyze"}

    def get_command(self, ctx, cmd_name):
        """Get Click command by its name."""
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        for cmd, alias in self.aliases.items():
            if cmd_name == alias:
                return click.Group.get_command(self, ctx, cmd)

        return click.Group.get_command(self, ctx, cmd_name)


@click.command(cls=AliasedGroup)
def cli():
    """Command line interface for Thoth build-analysers library."""


@cli.command()
@click.argument("log", type=click.Path(exists=True))
@click.option("--limit", "-n", help="Limit number of candidates.", type=int)
@click.option(
    "--handler", help="Handler to parse log dependencies.", type=click.Choice(choices=["pip3", "pipenv"]), default=None
)
@click.option("--colorize/--no-colorize", default=True)
@click.option("--pretty", "-p", is_flag=True, default=False)
def report(
    log: Union[str, Path], limit: int = 5, handler: str = None, colorize: bool = False, pretty: bool = False
) -> str:
    """Analyze raw build log and produce a report."""
    with open(log, "r") as f:
        build_log: str = f.read()

    result: dict = build_breaker_report(log=build_log, handler=handler, top=limit, colorize=colorize)

    if pretty:
        result: str = pformat(result)

        click.echo(result)
        sys.exit(0)

    click.echo(json.dumps(result))
    sys.exit(0)


@cli.command()
@click.argument("log", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    help="Output format.",
    type=click.Choice(choices=["dict", "html", "json", "plain", "records"]),
    default="plain",
)
@click.option("--pretty", "-p", is_flag=True, default=False)
def analyse(log: Union[str, Path], output: str = "plain", pretty: bool = False) -> str:
    """Analyze raw build log and produce tabular output."""
    with open(log, "r") as f:
        build_log: str = f.read()

    _, df = build_breaker_analyze(build_log)

    click.echo(_format_table(df, output=output, pretty=pretty))
    sys.exit(0)


@cli.command()
@click.argument("log", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    help="Output format.",
    type=click.Choice(choices=["dict", "html", "json", "plain", "records"]),
    default="plain",
)
@click.option("--pretty", "-p", is_flag=True, default=False)
def dependencies(log: Union[str, Path], output: str = "plain", pretty: bool = False):
    """Process dependencies from the log file."""
    with open(log, "r") as f:
        build_log: str = f.read()

    df = build_log_to_dependency_table(build_log)

    click.echo(_format_table(df, output=output, pretty=pretty))
    sys.exit(0)


if __name__ == "__main__":
    cli()
