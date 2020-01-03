#!/usr/bin/env python3
# thoth-build-analyzers
# Copyright(C) 2018, 2019, 2020 Marek Cermak
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

"""Command line interface for Thoth build-analyzers library."""

import click
import json
import sys
import time

from functools import wraps

from pathlib import Path
from prettyprinter import pformat

from thoth.analyzer import print_command_result
from thoth.build_analyzers import __title__ as analyzer_name
from thoth.build_analyzers import __version__ as analyzer_version
from thoth.build_analyzers.analysis import build_breaker_analyze
from thoth.build_analyzers.analysis import build_breaker_report
from thoth.build_analyzers.analysis import get_failed_branch
from thoth.build_analyzers.analysis import get_succesfully_installed_packages
from thoth.build_analyzers.preprocessing import build_log_to_dependency_table
from thoth.storages import BuildLogsStore


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


def _get_document(document_id: str, log: str):
    """Get the build log document from ceph and store it in required log path."""
    adapter = BuildLogsStore()
    adapter.connect()
    document = adapter.retrieve_document(document_id)

    with open(log, "w") as f:
        f.write(document.get("build_log", {}).get("log"))

    return


class AliasedGroup(click.Group):
    """Command group to handler comand aliases."""

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
    """Command line interface for Thoth build-analyzers library."""


@cli.command()
@click.pass_context
@click.argument("log", envvar="THOTH_BUILD_ANALYZER_LOG_PATH", type=click.Path())
@click.option("--limit", "-n", envvar="THOTH_BUILD_ANALYZER_LIMIT", help="Limit number of candidates.", type=int)
@click.option(
    "--handler",
    help="Handler to parse log dependencies.",
    envvar="THOTH_BUILD_ANALYZER_HANDLER",
    type=click.Choice(choices=["pip3", "pipenv"]),
    default=None,
)
@click.option(
    "--ceph-document-id",
    help="Document id of build log in ceph",
    envvar="THOTH_BUILD_LOG_DOC_ID",
    type=str,
    required=False,
)
@click.option(
    "--report-output",
    "-R",
    type=str,
    envvar="THOTH_REPORT_OUTPUT",
    required=False,
    default="-",
    help="Output directory or remote API where output reports should be posted.",
)
@click.option("--colorize/--no-colorize", default=True)
@click.option("--pretty", "-p", is_flag=True, default=False)
def report(
    click_ctx,
    log: str,
    ceph_document_id: str = None,
    limit: int = 5,
    report_output: str = "-",
    handler: str = None,
    colorize: bool = False,
    pretty: bool = False,
) -> str:
    """Analyze raw build log and produce a report."""
    start_time = time.monotonic()
    if ceph_document_id:
        _get_document(ceph_document_id, log)

    with open(log, "r") as f:
        build_log: str = f.read()

    result: dict = build_breaker_report(log=build_log, handler=handler, top=limit, colorize=colorize)

    if ceph_document_id:
        if pretty:
            result: str = pformat(result)
            click.echo(result)
            sys.exit(0)

        click.echo(json.dumps(result))
    else:
        print_command_result(
            click_ctx=click_ctx,
            result=result,
            analyzer=analyzer_name,
            analyzer_version=analyzer_version,
            output=report_output,
            duration=time.monotonic() - start_time,
            pretty=pretty,
        )
    sys.exit(0)


@cli.command()
@click.pass_context
@click.argument("log", envvar="THOTH_BUILD_ANALYZER_LOG_PATH", type=click.Path())
@click.option(
    "--output",
    "-o",
    help="Output format.",
    envvar="THOTH_BUILD_ANALYZER_OUTPUT_FORMAT",
    type=click.Choice(choices=["dict", "html", "json", "plain", "records"]),
    default="plain",
)
@click.option(
    "--ceph-document-id",
    help="Document id of build log in ceph",
    envvar="THOTH_BUILD_LOG_DOC_ID",
    type=str,
    required=False,
)
@click.option(
    "--report-output",
    "-R",
    type=str,
    envvar="THOTH_REPORT_OUTPUT",
    required=False,
    default="-",
    help="Output directory or remote API where output reports should be posted.",
)
@click.option("--pretty", "-p", is_flag=True, default=False)
def analyze(
    click_ctx,
    log: str,
    ceph_document_id: str = None,
    output: str = "plain",
    report_output: str = "-",
    pretty: bool = False,
):
    """Analyze raw build log and produce tabular output."""
    start_time = time.monotonic()
    if ceph_document_id:
        _get_document(ceph_document_id, log)

    with open(log, "r") as f:
        build_log: str = f.read()

    _, df = build_breaker_analyze(build_log)
    result = _format_table(df, output=output, pretty=pretty)

    if ceph_document_id:
        print_command_result(
            click_ctx=click_ctx,
            result=result,
            analyzer=analyzer_name,
            analyzer_version=analyzer_version,
            output=report_output,
            duration=time.monotonic() - start_time,
            pretty=pretty,
        )
    else:
        click.echo(result)
    sys.exit(0)


@cli.command()
@click.pass_context
@click.argument("log", envvar="THOTH_BUILD_ANALYZER_LOG_PATH", type=click.Path())
@click.option(
    "--output",
    "-o",
    help="Output format.",
    envvar="THOTH_BUILD_ANALYZER_OUTPUT_FORMAT",
    type=click.Choice(choices=["dict", "html", "json", "plain", "records"]),
    default="plain",
)
@click.option(
    "--ceph-document-id",
    help="Document id of build log in ceph",
    envvar="THOTH_BUILD_LOG_DOC_ID",
    type=str,
    required=False,
)
@click.option(
    "--report-output",
    "-R",
    type=str,
    envvar="THOTH_REPORT_OUTPUT",
    required=False,
    default="-",
    help="Output directory or remote API where output reports should be posted.",
)
@click.option("--pretty", "-p", is_flag=True, default=False)
def dependencies(
    click_ctx,
    log: str,
    ceph_document_id: str = None,
    output: str = "plain",
    report_output: str = "-",
    pretty: bool = False,
):
    """Process dependencies from the log file."""
    start_time = time.monotonic()
    if ceph_document_id:
        _get_document(ceph_document_id, log)

    with open(log, "r") as f:
        build_log: str = f.read()

    df = build_log_to_dependency_table(build_log)
    result = _format_table(df, output=output, pretty=pretty)

    if ceph_document_id:
        print_command_result(
            click_ctx=click_ctx,
            result=result,
            analyzer=analyzer_name,
            analyzer_version=analyzer_version,
            output=report_output,
            duration=time.monotonic() - start_time,
            pretty=pretty,
        )
    else:
        click.echo(result)
    sys.exit(0)


if __name__ == "__main__":
    cli()
